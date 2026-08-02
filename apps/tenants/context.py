from contextlib import contextmanager
from contextvars import ContextVar


_current_tenant = ContextVar('yetka_customer_tenant', default=None)


def get_current_tenant():
    return _current_tenant.get()


def get_current_tenant_id():
    tenant = get_current_tenant()
    return str(tenant.id) if tenant else None


@contextmanager
def tenant_context(tenant):
    token = _current_tenant.set(tenant)
    try:
        yield tenant
    finally:
        _current_tenant.reset(token)
