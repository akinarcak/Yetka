from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import ValidationError

from .api import IDEMPOTENCY_KEY_RE
from .services import queue_sync
from .tasks import sync_cloud_execution
from .sync import quarantine_instance
from .validation import validate_custom_endpoint


class CloudSyncQueueTests(SimpleTestCase):
    @override_settings(CLOUD_SYNC_ALLOWED_ENDPOINTS=('https://ec2.example.test',))
    def test_custom_endpoint_requires_exact_https_allowlist_origin(self):
        self.assertEqual(
            validate_custom_endpoint('https://ec2.example.test/'),
            'https://ec2.example.test',
        )
        for endpoint in (
            'http://ec2.example.test',
            'https://ec2.example.test.attacker.invalid',
            'https://169.254.169.254',
            'https://localhost',
            'https://user:secret@ec2.example.test',
            'https://ec2.example.test/path',
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValidationError):
                validate_custom_endpoint(endpoint)

    def test_idempotency_key_rejects_unsafe_values(self):
        self.assertIsNone(IDEMPOTENCY_KEY_RE.fullmatch('short'))
        self.assertIsNone(IDEMPOTENCY_KEY_RE.fullmatch('unsafe key;rm'))
        self.assertIsNotNone(IDEMPOTENCY_KEY_RE.fullmatch('request-20260802-0001'))

    @patch('cloud_sync.services.transaction.on_commit')
    @patch('cloud_sync.services.transaction.atomic', return_value=nullcontext())
    @patch('cloud_sync.services.CloudSyncExecution.objects')
    def test_new_idempotency_key_queues_once(self, objects, atomic, on_commit):
        execution = SimpleNamespace(id='execution-a')
        objects.get_or_create.return_value = (execution, True)
        account = SimpleNamespace(id='account-a', org_id='org-a')
        tenant = SimpleNamespace(id='tenant-a')

        result, created = queue_sync(account, tenant, 'request-0001')

        self.assertIs(result, execution)
        self.assertTrue(created)
        on_commit.assert_called_once()

    @patch('cloud_sync.services.transaction.on_commit')
    @patch('cloud_sync.services.transaction.atomic', return_value=nullcontext())
    @patch('cloud_sync.services.CloudSyncExecution.objects')
    def test_replayed_idempotency_key_does_not_queue_again(self, objects, atomic, on_commit):
        execution = SimpleNamespace(id='execution-a')
        objects.get_or_create.return_value = (execution, False)

        result, created = queue_sync(
            SimpleNamespace(org_id='org-a'),
            SimpleNamespace(id='tenant-a'),
            'request-0001',
        )

        self.assertIs(result, execution)
        self.assertFalse(created)
        on_commit.assert_not_called()

    @patch('cloud_sync.tasks.tmp_to_root_org', return_value=nullcontext())
    @patch('cloud_sync.tasks.CloudSyncExecution.objects')
    def test_worker_queries_execution_and_account_by_same_tenant(self, objects, root_org):
        objects.select_related.return_value.filter.return_value.first.return_value = None

        result = sync_cloud_execution.run('execution-a', 'tenant-a')

        self.assertIsNone(result)
        objects.select_related.return_value.filter.assert_called_once_with(
            id='execution-a',
            tenant_id='tenant-a',
            account__tenant_id='tenant-a',
        )

    @patch('cloud_sync.sync.CloudSyncQuarantine.objects')
    def test_quarantine_records_only_bounded_non_secret_observation(self, objects):
        account = SimpleNamespace(tenant='tenant-a', org_id='org-a')
        execution = SimpleNamespace(id='execution-a')
        instance = SimpleNamespace(
            instance_id='instance-a', name='host-a', private_ip='', public_ip='',
            region='eu-test-1', os_type='linux', extra={'secret': 'must-not-persist'},
        )

        quarantine_instance(account, execution, instance, 'missing_address')

        defaults = objects.update_or_create.call_args.kwargs['defaults']
        self.assertNotIn('secret', defaults['observed'])
        self.assertEqual(defaults['tenant'], 'tenant-a')
        self.assertEqual(defaults['reason_code'], 'missing_address')
