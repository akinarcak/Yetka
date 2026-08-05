"""
Contract tests for the ansible engine layer (ansible 12 / ansible-core 2.19).

The foundation gate does not execute ansible anywhere else; these tests are
the only engine-boundary coverage. Three surfaces are pinned:

- the ten in-tree modules and their helpers stay importable under the
  installed ansible-core, so module-API drift surfaces here first;
- the ansible-runner fork keeps its 2.4.3 base and its single local patch
  (env sanitizing in the bubblewrap arguments) — if the dependency is ever
  swapped for plain upstream, the tripwire below fails;
- ansible-runner can drive ansible end to end inside this image, including
  an in-tree module through AnsiballZ with the production environment setup.
"""
import importlib
import importlib.metadata
import inspect
import os
import shutil
import sys
import tempfile

from django.db import models
from django.test import SimpleTestCase
from rest_framework import serializers

CUSTOM_MODULES = [
    'custom_command',
    'mongodb_ping',
    'mongodb_user',
    'mssql_script',
    'oracle_info',
    'oracle_ping',
    'oracle_user',
    'rdp_ping',
    'ssh_ping',
    'telnet_ping',
]

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

    def test_module_helpers_import(self):
        importlib.import_module('libs.ansible.modules_utils.remote_client')
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
    """Run ansible for real, through ansible-runner, inside this image."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.workdir = tempfile.mkdtemp(prefix='ansible-engine-test-')
        os.environ.setdefault('ANSIBLE_HOME', os.path.join(cls.workdir, 'home'))
        os.environ.setdefault(
            'ANSIBLE_LOCAL_TEMP', os.path.join(cls.workdir, 'home', 'tmp'))
        # Same environment production uses before every runner invocation.
        from ops.ansible.runners.base import BaseRunner
        BaseRunner.setup_env()
        os.environ['PATH'] = os.pathsep.join(
            [os.path.dirname(sys.executable), os.environ.get('PATH', '')])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.workdir, ignore_errors=True)
        super().tearDownClass()

    def _run(self, **kwargs):
        import ansible_runner
        return ansible_runner.run(
            private_data_dir=tempfile.mkdtemp(dir=self.workdir),
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
        self.assertEqual(result.status, 'successful', result.rc)
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
