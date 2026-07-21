from .base import BaseProvider, CloudInstance


class AzureProvider(BaseProvider):
    def _clients(self):
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.network import NetworkManagementClient
        cred = ClientSecretCredential(
            tenant_id=self.credentials.get('tenant_id'),
            client_id=self.credentials.get('client_id'),
            client_secret=self.credentials.get('client_secret'),
        )
        sub = self.credentials.get('subscription_id')
        return (
            ComputeManagementClient(cred, sub),
            NetworkManagementClient(cred, sub),
        )

    @staticmethod
    def _rg_from_id(resource_id):
        # /subscriptions/xxx/resourceGroups/RG/providers/...
        parts = resource_id.split('/')
        try:
            return parts[parts.index('resourceGroups') + 1]
        except (ValueError, IndexError):
            return ''

    def _nic_ips(self, network, nic_id):
        rg = self._rg_from_id(nic_id)
        name = nic_id.split('/')[-1]
        private_ip, public_ip = '', ''
        nic = network.network_interfaces.get(rg, name)
        for ipconf in nic.ip_configurations or []:
            if ipconf.private_ip_address and not private_ip:
                private_ip = ipconf.private_ip_address
            pip = getattr(ipconf, 'public_ip_address', None)
            if pip and pip.id:
                prg = self._rg_from_id(pip.id)
                pname = pip.id.split('/')[-1]
                pub = network.public_ip_addresses.get(prg, pname)
                if pub.ip_address:
                    public_ip = pub.ip_address
        return private_ip, public_ip

    def list_instances(self):
        compute, network = self._clients()
        instances = []
        for vm in compute.virtual_machines.list_all():
            os_profile = getattr(vm, 'os_profile', None)
            os_disk = getattr(getattr(vm, 'storage_profile', None), 'os_disk', None)
            os_type = 'linux'
            if os_disk and getattr(os_disk, 'os_type', None):
                os_type = 'windows' if str(os_disk.os_type).lower() == 'windows' else 'linux'
            region = getattr(vm, 'location', '')
            if self.regions and region not in self.regions:
                continue
            private_ip, public_ip = '', ''
            nics = getattr(getattr(vm, 'network_profile', None), 'network_interfaces', None) or []
            if nics:
                try:
                    private_ip, public_ip = self._nic_ips(network, nics[0].id)
                except Exception:
                    pass
            instances.append(CloudInstance(
                instance_id=vm.vm_id or vm.id,
                name=vm.name,
                private_ip=private_ip,
                public_ip=public_ip,
                os_type=os_type,
                region=region,
                extra={'vm_size': getattr(getattr(vm, 'hardware_profile', None), 'vm_size', '')},
            ))
        return instances
