from celery import Task

from .context import tenant_context
from .exceptions import TenantAccessDenied
from .models import CustomerTenant, TenantOrganization


TENANT_TASK_KEY = '__customer_tenant_id'
TENANT_ORG_TASK_KEY = '__customer_tenant_org_id'


class TenantAwareTask(Task):
    abstract = True

    def __call__(self, *args, **kwargs):
        tenant_id = kwargs.get(TENANT_TASK_KEY)
        org_id = kwargs.get(TENANT_ORG_TASK_KEY)
        task_kwargs = dict(kwargs)
        task_kwargs.pop(TENANT_TASK_KEY, None)
        task_kwargs.pop(TENANT_ORG_TASK_KEY, None)

        if not tenant_id:
            return super().__call__(*args, **task_kwargs)

        try:
            tenant = CustomerTenant.objects.filter(id=tenant_id, is_active=True).first()
        except (TypeError, ValueError):
            tenant = None
        if tenant is None:
            raise TenantAccessDenied('Celery task customer tenant is missing or inactive')
        if org_id and not TenantOrganization.objects.filter(
            tenant=tenant, organization_id=org_id
        ).exists():
            raise TenantAccessDenied('Celery task organization belongs to another customer tenant')

        with tenant_context(tenant):
            return super().__call__(*args, **task_kwargs)
