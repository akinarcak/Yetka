from django.conf import settings
from django.db import models

from common.db.models import JMSBaseModel


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        if tenant is None:
            raise ValueError('An explicit customer tenant is required')
        tenant_id = getattr(tenant, 'id', tenant)
        return self.filter(tenant_id=tenant_id)


class CustomerTenant(JMSBaseModel):
    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class CustomerTenantMembership(JMSBaseModel):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Owner'
        ADMIN = 'admin', 'Admin'
        MEMBER = 'member', 'Member'

    tenant = models.ForeignKey(
        CustomerTenant, on_delete=models.CASCADE, related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_tenant_memberships'
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('tenant', 'user'), name='uniq_customer_tenant_user'),
        ]


class TenantOrganization(JMSBaseModel):
    tenant = models.ForeignKey(
        CustomerTenant, on_delete=models.PROTECT, related_name='organization_links'
    )
    organization = models.OneToOneField(
        'orgs.Organization', on_delete=models.PROTECT, related_name='customer_tenant_link'
    )


class CustomerTenantOwnedModel(JMSBaseModel):
    tenant = models.ForeignKey(CustomerTenant, on_delete=models.PROTECT)

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True
