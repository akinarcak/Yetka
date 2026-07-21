import os
import json

from .base import BaseProvider, CloudInstance


class MockProvider(BaseProvider):
    """Test icin: credentials['instances'] ya da $CLOUD_SYNC_MOCK_FILE'dan instance listesi okur."""

    def list_instances(self):
        raw = self.credentials.get('instances')
        if not raw:
            path = os.environ.get('CLOUD_SYNC_MOCK_FILE')
            if path and os.path.exists(path):
                with open(path) as f:
                    raw = json.load(f)
        instances = []
        for d in (raw or []):
            instances.append(CloudInstance(
                instance_id=d['instance_id'],
                name=d.get('name') or d['instance_id'],
                private_ip=d.get('private_ip', ''),
                public_ip=d.get('public_ip', ''),
                os_type=d.get('os_type', 'linux'),
                region=d.get('region', ''),
            ))
        return instances
