from .aws import AWSProvider
from .azure import AzureProvider
from .mock import MockProvider

PROVIDERS = {
    'aws': AWSProvider,
    'azure': AzureProvider,
    'mock': MockProvider,
}


def get_provider(account):
    cls = PROVIDERS.get(account.provider)
    if not cls:
        raise ValueError(f'Unsupported provider: {account.provider}')
    return cls(account.credentials, account.regions)
