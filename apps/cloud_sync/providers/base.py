from dataclasses import dataclass, field


@dataclass
class CloudInstance:
    instance_id: str
    name: str
    private_ip: str = ''
    public_ip: str = ''
    os_type: str = 'linux'   # linux | windows
    region: str = ''
    extra: dict = field(default_factory=dict)


class BaseProvider:
    def __init__(self, credentials: dict, regions=None):
        self.credentials = credentials or {}
        self.regions = regions or []

    def list_instances(self):
        """-> list[CloudInstance]"""
        raise NotImplementedError

    def test(self):
        """Kimlik bilgilerini dogrula; hata firlatirsa gecersiz."""
        self.list_instances()
        return True
