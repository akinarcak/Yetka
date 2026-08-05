"""
Contract tests for the ansible engine layer (ansible 12 / ansible-core 2.19).

The foundation gate does not execute ansible anywhere else; these tests are
the only engine-boundary coverage. Three surfaces are pinned:

- the in-tree modules and their helpers stay importable under the installed
  ansible-core, so module-API drift surfaces here first;
- the ansible-runner fork keeps its 2.4.3 base and its single local patch
  (env sanitizing in the bubblewrap arguments) — if the dependency is ever
  swapped for plain upstream, the tripwire below fails;
- ansible-runner can drive ansible end to end inside this image, including
  an in-tree module through AnsiballZ with the production environment setup.
  This also pins the image's locale ENV: ansible refuses to start when
  LANG/LC_ALL name a locale the runtime image does not carry.
"""
import glob
import importlib
import importlib.metadata
import importlib.util
import inspect
import os
import re
import shutil
import sys
import tempfile
import unittest

import yaml

# The gate runs this suite in a read-only container where HOME is not
# writable. Importing ansible (and the collection loader) wants to create
# ANSIBLE_HOME, so it must point at scratch space before the first ansible
# import anywhere in this module's tests.
_ANSIBLE_SCRATCH = tempfile.mkdtemp(prefix='ansible-engine-tests-')
os.environ['ANSIBLE_HOME'] = os.path.join(_ANSIBLE_SCRATCH, 'home')
os.environ['ANSIBLE_LOCAL_TEMP'] = os.path.join(_ANSIBLE_SCRATCH, 'home', 'tmp')
# With the local connection the "remote" side shares this filesystem, so its
# tmp must leave the unwritable HOME as well.
os.environ['ANSIBLE_REMOTE_TMP'] = os.path.join(_ANSIBLE_SCRATCH, 'home', 'tmp')

from django.conf import settings
from django.db import models
from django.test import SimpleTestCase
from rest_framework import serializers

CUSTOM_MODULES = [
    'custom_command',
    'mongodb_ping',
    'mongodb_user',
    'mssql_script',
    'rdp_ping',
    'ssh_ping',
    'telnet_ping',
]

# oracledb ships in the xpack dependency group; the foundation image is
# built without xpack, so the oracle modules can only import in xpack builds.
ORACLE_MODULES = ['oracle_info', 'oracle_ping', 'oracle_user']
HAS_ORACLEDB = importlib.util.find_spec('oracledb') is not None

MONGODB_COMMON_SYMBOLS = [
    'mongodb_common_argument_spec',
    'mongo_auth',
    'get_mongodb_client',
    'missing_required_lib',
    'PYMONGO_IMP_ERR',
    'pymongo_found',
]


class ModuleImportContractTest(SimpleTestCase):
    def test_custom_modules_import(self):
        for name in CUSTOM_MODULES:
            with self.subTest(module=name):
                importlib.import_module('libs.ansible.modules.%s' % name)

    @unittest.skipUnless(HAS_ORACLEDB, 'oracledb is xpack-only; not in this build')
    def test_oracle_modules_import(self):
        for name in ORACLE_MODULES:
            with self.subTest(module=name):
                importlib.import_module('libs.ansible.modules.%s' % name)

    def test_module_helpers_import(self):
        importlib.import_module('libs.ansible.modules_utils.remote_client')
        if HAS_ORACLEDB:
            importlib.import_module('libs.ansible.modules_utils.oracle_common')

    def test_mongodb_module_utils_contract(self):
        mongodb_common = importlib.import_module(
            'ansible_collections.community.mongodb.plugins.module_utils.mongodb_common'
        )
        for symbol in MONGODB_COMMON_SYMBOLS:
            with self.subTest(symbol=symbol):
                self.assertTrue(
                    hasattr(mongodb_common, symbol),
                    'community.mongodb mongodb_common no longer provides %r' % symbol,
                )


class BareConditionalLintTest(SimpleTestCase):
    """No playbook may gate a task on a bare non-boolean variable.

    ansible-core 2.19 rejects conditionals whose result is not a boolean.
    A bare `when: params.sudo` passed silently under 2.16 and raises
    "Conditionals must have a boolean result" under 2.19 — params.sudo is a
    str in the manifests. Only names known to be boolean may appear bare;
    anything else needs an explicit test (`| length > 0`, `.exists`, `== x`).
    """

    # Each entry is a bool at its producer: check_conn_after_change is a
    # BooleanField, RDS_Licensing a BooleanField serializer field,
    # params.modify_sudo is declared `type: bool` in the manifests, and
    # account.become.ansible_become is set to True/False in
    # Account.get_ansible_become_auth.
    KNOWN_BOOLEAN = {
        'check_conn_after_change',
        'params.modify_sudo',
        'RDS_Licensing',
        'rds_install.reboot_required',
        'account.become.ansible_become',
    }
    BARE_REFERENCE = re.compile(r'^[A-Za-z_][\w.]*$')

    def _conditionals(self, playbook):
        """Yield every `when` expression in a playbook, as strings."""
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == 'when':
                        if isinstance(value, (list, tuple)):
                            for item in value:
                                yield item
                        else:
                            yield value
                    else:
                        yield from walk(value)
            elif isinstance(node, list):
                for item in node:
                    yield from walk(item)

        with open(playbook, encoding='utf-8') as handle:
            try:
                loaded = yaml.safe_load(handle)
            except yaml.YAMLError:
                return  # jinja-templated manifests are not playbooks
        yield from walk(loaded)

    def test_no_bare_non_boolean_conditionals(self):
        automations = os.path.join(settings.APPS_DIR)
        offenders = []
        for playbook in glob.glob(
                os.path.join(automations, '*', 'automations', '**', 'main.yml'),
                recursive=True):
            for condition in self._conditionals(playbook):
                if not isinstance(condition, str):
                    continue
                expression = condition.strip()
                if not self.BARE_REFERENCE.match(expression):
                    continue
                if expression in self.KNOWN_BOOLEAN:
                    continue
                offenders.append(
                    '%s: when: %s' % (os.path.relpath(playbook, automations), expression))
        self.assertEqual(
            offenders, [],
            'bare conditionals on names not known to be boolean; ansible-core '
            '2.19 requires a boolean result:\n  ' + '\n  '.join(offenders),
        )


class RunnerForkTripwireTest(SimpleTestCase):
    def test_runner_is_rebased_fork_line(self):
        version = importlib.metadata.version('ansible-runner')
        self.assertTrue(
            version.startswith('2.4.3'),
            'ansible-runner is %s, expected the 2.4.3-based fork line' % version,
        )

    def test_env_sanitizing_patch_present(self):
        runner_config = importlib.import_module('ansible_runner.config.runner')
        source = inspect.getsource(runner_config)
        self.assertIn(
            "'--unsetenv'", source,
            'bubblewrap env sanitizing (fix: disable env) is missing from '
            'ansible-runner — the fork was likely replaced by plain upstream',
        )
        self.assertIn("'--ro-bind', '/lib'", source)


class ConditionalTypeContractTest(SimpleTestCase):
    """ansible-core 2.19 requires conditionals to evaluate to booleans.

    These fields feed bare `when:` expressions in the automation playbooks
    (`when: check_conn_after_change`, `when: RDS_Licensing`), so their types
    must stay boolean all the way into the generated inventory/extravars.
    """

    def test_check_conn_after_change_is_boolean_field(self):
        from accounts.models import ChangeSecretAutomation
        field = ChangeSecretAutomation._meta.get_field('check_conn_after_change')
        self.assertIsInstance(field, models.BooleanField)

    def test_rds_licensing_is_boolean_serializer_field(self):
        from terminal.serializers.applet_host import DeployOptionsSerializer
        field = DeployOptionsSerializer().fields['RDS_Licensing']
        self.assertIsInstance(field, serializers.BooleanField)


class RunnerExecutionSmokeTest(SimpleTestCase):
    """Run ansible for real, through ansible-runner, inside this image.

    Deliberately no locale override here: BaseRunner.setup_env() is exactly
    what production exports, so a runtime image whose LANG/LC_ALL name an
    unavailable locale fails this test ("could not initialize the preferred
    locale") instead of failing in production automations.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Same environment production uses before every runner invocation.
        from ops.ansible.runners.base import BaseRunner
        BaseRunner.setup_env()
        os.environ['PATH'] = os.pathsep.join(
            [os.path.dirname(sys.executable), os.environ.get('PATH', '')])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_ANSIBLE_SCRATCH, ignore_errors=True)
        super().tearDownClass()

    def _run(self, **kwargs):
        import ansible_runner
        return ansible_runner.run(
            private_data_dir=tempfile.mkdtemp(dir=_ANSIBLE_SCRATCH),
            host_pattern='localhost',
            inventory={'all': {'hosts': {'localhost': {
                'ansible_connection': 'local',
                'ansible_python_interpreter': sys.executable,
            }}}},
            quiet=True,
            **kwargs,
        )

    def test_local_ping_succeeds(self):
        result = self._run(module='ping', module_args='')
        stdout = ''
        if result.status != 'successful':
            try:
                stdout = result.stdout.read()
            except Exception:  # noqa: BLE001 - diagnostics only
                pass
        self.assertEqual(result.status, 'successful', stdout[:1000])
        events = [e for e in result.events if e.get('event') == 'runner_on_ok']
        self.assertTrue(events, 'no runner_on_ok event received')
        res = events[-1].get('event_data', {}).get('res', {})
        self.assertEqual(res.get('ping'), 'pong')

    def test_in_tree_module_runs_under_ansiballz(self):
        # Port 9 (discard) is closed; ssh_ping must fail in its own connect
        # logic. An import-time failure would surface as ModuleNotFoundError
        # in the module output instead, which is what this guards against.
        result = self._run(
            module='ssh_ping',
            module_args=(
                'login_host=127.0.0.1 login_port=9 '
                'login_user=nobody login_password=x recv_timeout=5'
            ),
        )
        self.assertEqual(result.status, 'failed')
        events = [e for e in result.events if e.get('event') == 'runner_on_failed']
        self.assertTrue(events, 'no runner_on_failed event received')
        res = events[-1].get('event_data', {}).get('res', {})
        blob = str(res)
        for marker in ('ModuleNotFoundError', 'ImportError'):
            self.assertNotIn(
                marker, blob,
                'ssh_ping failed at import time inside AnsiballZ: %s' % blob[:500],
            )
