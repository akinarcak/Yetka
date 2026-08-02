from contextlib import nullcontext
import sys
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import ValidationError

from .api import IDEMPOTENCY_KEY_RE
from .services import queue_sync
from .tasks import sync_cloud_execution
from .sync import quarantine_instance
from .validation import validate_custom_endpoint
from .providers.aws import AWSProvider
from .providers.azure import AzureProvider


class CloudProviderMockTests(SimpleTestCase):
    def test_aws_sdk_is_mocked_and_instances_are_normalized(self):
        regional_client = Mock()
        regional_client.get_paginator.return_value.paginate.return_value = [{
            'Reservations': [{'Instances': [
                {
                    'InstanceId': 'i-linux',
                    'State': {'Name': 'running'},
                    'Tags': [{'Key': 'Name', 'Value': 'api-01'}],
                    'PrivateIpAddress': '10.0.0.10',
                    'PublicIpAddress': '203.0.113.10',
                    'InstanceType': 't3.small',
                },
                {
                    'InstanceId': 'i-windows',
                    'State': {'Name': 'stopped'},
                    'Platform': 'windows',
                    'PrivateIpAddress': '10.0.0.11',
                },
                {
                    'InstanceId': 'i-terminated',
                    'State': {'Name': 'terminated'},
                },
            ]}]
        }]
        boto3_client = Mock(return_value=regional_client)
        boto3 = ModuleType('boto3')
        boto3.client = boto3_client
        provider = AWSProvider({
            'access_key_id': 'mock-access',
            'secret_access_key': 'mock-secret',
        }, regions=['eu-central-1'])

        with patch.dict(sys.modules, {'boto3': boto3}):
            instances = provider.list_instances()

        boto3_client.assert_called_once_with(
            'ec2',
            aws_access_key_id='mock-access',
            aws_secret_access_key='mock-secret',
            region_name='eu-central-1',
            endpoint_url=None,
        )
        regional_client.get_paginator.assert_called_once_with('describe_instances')
        self.assertEqual([item.instance_id for item in instances], ['i-linux', 'i-windows'])
        self.assertEqual(instances[0].name, 'api-01')
        self.assertEqual(instances[0].os_type, 'linux')
        self.assertEqual(instances[1].name, 'i-windows')
        self.assertEqual(instances[1].os_type, 'windows')

    @override_settings(CLOUD_SYNC_ALLOWED_ENDPOINTS=())
    def test_aws_rejects_custom_endpoint_before_sdk_call(self):
        boto3_client = Mock()
        boto3 = ModuleType('boto3')
        boto3.client = boto3_client
        provider = AWSProvider({'endpoint_url': 'https://untrusted.example.test'}, ['eu-west-1'])

        with patch.dict(sys.modules, {'boto3': boto3}), self.assertRaises(ValidationError):
            provider.list_instances()

        boto3_client.assert_not_called()

    def test_aws_region_discovery_is_mocked(self):
        discovery_client = Mock()
        discovery_client.describe_regions.return_value = {
            'Regions': [{'RegionName': 'eu-west-1'}, {'RegionName': 'eu-west-3'}]
        }
        regional_client = Mock()
        regional_client.get_paginator.return_value.paginate.return_value = []
        boto3_client = Mock(side_effect=[discovery_client, regional_client, regional_client])
        boto3 = ModuleType('boto3')
        boto3.client = boto3_client

        with patch.dict(sys.modules, {'boto3': boto3}):
            instances = AWSProvider({}, regions=[]).list_instances()

        self.assertEqual(instances, [])
        self.assertEqual(
            [call.kwargs['region_name'] for call in boto3_client.call_args_list],
            ['us-east-1', 'eu-west-1', 'eu-west-3'],
        )

    def test_azure_sdk_is_mocked_and_network_addresses_are_normalized(self):
        credential = object()
        credential_factory = Mock(return_value=credential)
        compute = Mock()
        network = Mock()
        compute_factory = Mock(return_value=compute)
        network_factory = Mock(return_value=network)
        vm = SimpleNamespace(
            vm_id='vm-guid', id='/subscriptions/sub/resourceGroups/rg/providers/vm/vm-a',
            name='vm-a', location='westeurope', os_profile=object(),
            storage_profile=SimpleNamespace(os_disk=SimpleNamespace(os_type='Windows')),
            hardware_profile=SimpleNamespace(vm_size='Standard_B2s'),
            network_profile=SimpleNamespace(network_interfaces=[SimpleNamespace(
                id='/subscriptions/sub/resourceGroups/rg-net/providers/Microsoft.Network/networkInterfaces/nic-a'
            )]),
        )
        compute.virtual_machines.list_all.return_value = [vm]
        public_ip_ref = SimpleNamespace(
            id='/subscriptions/sub/resourceGroups/rg-net/providers/Microsoft.Network/publicIPAddresses/pip-a'
        )
        network.network_interfaces.get.return_value = SimpleNamespace(ip_configurations=[
            SimpleNamespace(private_ip_address='10.1.0.4', public_ip_address=public_ip_ref)
        ])
        network.public_ip_addresses.get.return_value = SimpleNamespace(ip_address='203.0.113.40')
        modules = self._azure_modules(credential_factory, compute_factory, network_factory)
        provider = AzureProvider({
            'tenant_id': 'tenant-guid', 'client_id': 'client-guid',
            'client_secret': 'mock-secret', 'subscription_id': 'subscription-guid',
        }, regions=['westeurope'])

        with patch.dict(sys.modules, modules):
            instances = provider.list_instances()

        credential_factory.assert_called_once_with(
            tenant_id='tenant-guid', client_id='client-guid', client_secret='mock-secret'
        )
        compute_factory.assert_called_once_with(credential, 'subscription-guid')
        network_factory.assert_called_once_with(credential, 'subscription-guid')
        network.network_interfaces.get.assert_called_once_with('rg-net', 'nic-a')
        network.public_ip_addresses.get.assert_called_once_with('rg-net', 'pip-a')
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0].instance_id, 'vm-guid')
        self.assertEqual(instances[0].private_ip, '10.1.0.4')
        self.assertEqual(instances[0].public_ip, '203.0.113.40')
        self.assertEqual(instances[0].os_type, 'windows')

    def test_azure_region_filter_avoids_network_lookup(self):
        compute = Mock()
        network = Mock()
        compute.virtual_machines.list_all.return_value = [SimpleNamespace(
            vm_id='vm-guid', id='vm-id', name='vm-a', location='eastus',
            os_profile=None, storage_profile=None, hardware_profile=None,
            network_profile=SimpleNamespace(network_interfaces=[]),
        )]
        modules = self._azure_modules(Mock(), Mock(return_value=compute), Mock(return_value=network))

        with patch.dict(sys.modules, modules):
            instances = AzureProvider({}, regions=['westeurope']).list_instances()

        self.assertEqual(instances, [])
        network.network_interfaces.get.assert_not_called()

    @staticmethod
    def _azure_modules(credential_factory, compute_factory, network_factory):
        azure = ModuleType('azure')
        identity = ModuleType('azure.identity')
        identity.ClientSecretCredential = credential_factory
        mgmt = ModuleType('azure.mgmt')
        compute = ModuleType('azure.mgmt.compute')
        compute.ComputeManagementClient = compute_factory
        network = ModuleType('azure.mgmt.network')
        network.NetworkManagementClient = network_factory
        azure.identity = identity
        azure.mgmt = mgmt
        mgmt.compute = compute
        mgmt.network = network
        return {
            'azure': azure,
            'azure.identity': identity,
            'azure.mgmt': mgmt,
            'azure.mgmt.compute': compute,
            'azure.mgmt.network': network,
        }


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
