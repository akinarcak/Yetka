from .base import BaseProvider, CloudInstance


class AWSProvider(BaseProvider):
    def _session(self, region=None):
        import boto3
        return boto3.client(
            'ec2',
            aws_access_key_id=self.credentials.get('access_key_id'),
            aws_secret_access_key=self.credentials.get('secret_access_key'),
            region_name=region,
        )

    def _all_regions(self):
        if self.regions:
            return self.regions
        client = self._session(region='us-east-1')
        resp = client.describe_regions()
        return [r['RegionName'] for r in resp.get('Regions', [])]

    @staticmethod
    def _name_from_tags(tags):
        for t in tags or []:
            if t.get('Key') == 'Name' and t.get('Value'):
                return t['Value']
        return ''

    def list_instances(self):
        instances = []
        for region in self._all_regions():
            client = self._session(region=region)
            paginator = client.get_paginator('describe_instances')
            for page in paginator.paginate():
                for reservation in page.get('Reservations', []):
                    for inst in reservation.get('Instances', []):
                        state = inst.get('State', {}).get('Name')
                        if state in ('terminated', 'shutting-down'):
                            continue
                        platform = (inst.get('Platform') or '').lower()
                        os_type = 'windows' if platform == 'windows' else 'linux'
                        name = self._name_from_tags(inst.get('Tags')) or inst['InstanceId']
                        instances.append(CloudInstance(
                            instance_id=inst['InstanceId'],
                            name=name,
                            private_ip=inst.get('PrivateIpAddress', ''),
                            public_ip=inst.get('PublicIpAddress', ''),
                            os_type=os_type,
                            region=region,
                            extra={'state': state, 'instance_type': inst.get('InstanceType')},
                        ))
        return instances
