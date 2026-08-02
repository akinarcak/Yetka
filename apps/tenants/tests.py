from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from .context import get_current_tenant
from .exceptions import TenantAccessDenied, TenantSelectionRequired
from .middleware import (
    CustomerTenantMiddleware,
    resolve_tenant_for_user,
    validate_organization_ownership,
)


class FakeMemberships:
    def __init__(self, memberships):
        self.memberships = memberships

    def select_related(self, *args):
        return self

    def filter(self, **kwargs):
        tenant_id = kwargs.get('tenant_id')
        if tenant_id is None:
            return self
        return FakeMemberships([
            item for item in self.memberships if str(item.tenant.id) == str(tenant_id)
        ])

    def first(self):
        return self.memberships[0] if self.memberships else None

    def __getitem__(self, item):
        return self.memberships[item]


def membership(tenant_id):
    tenant = SimpleNamespace(id=tenant_id)
    return SimpleNamespace(tenant=tenant)


class TenantResolutionTests(SimpleTestCase):
    def test_multiple_memberships_require_explicit_header(self):
        manager = FakeMemberships([membership('tenant-a'), membership('tenant-b')])
        with patch('tenants.middleware.CustomerTenantMembership.objects', manager):
            with self.assertRaises(TenantSelectionRequired):
                resolve_tenant_for_user(SimpleNamespace(id='user-a'))

    def test_requested_tenant_must_be_assigned(self):
        manager = FakeMemberships([membership('tenant-a')])
        with patch('tenants.middleware.CustomerTenantMembership.objects', manager):
            with self.assertRaises(TenantAccessDenied):
                resolve_tenant_for_user(SimpleNamespace(id='user-a'), 'tenant-b')

    def test_requested_assigned_tenant_is_selected(self):
        manager = FakeMemberships([membership('tenant-a'), membership('tenant-b')])
        with patch('tenants.middleware.CustomerTenantMembership.objects', manager):
            tenant = resolve_tenant_for_user(SimpleNamespace(id='user-a'), 'tenant-b')
        self.assertEqual(tenant.id, 'tenant-b')

    @patch('tenants.middleware.TenantOrganization.objects')
    def test_cross_tenant_organization_is_rejected(self, objects):
        objects.filter.return_value.exists.return_value = False
        with self.assertRaises(TenantAccessDenied):
            validate_organization_ownership(
                SimpleNamespace(id='tenant-a'), SimpleNamespace(id='org-b')
            )

    @patch('tenants.middleware.validate_organization_ownership')
    @patch('tenants.middleware.resolve_tenant_for_user')
    def test_request_context_is_reset_after_response(self, resolve, validate):
        tenant = SimpleNamespace(id='tenant-a')
        resolve.return_value = tenant
        observed = []

        def response(request):
            observed.append(get_current_tenant())
            return Mock(status_code=200)

        request = RequestFactory().get('/api/v1/assets/assets/')
        request.user = SimpleNamespace(is_authenticated=True)
        request.current_org = SimpleNamespace(id='org-a')

        result = CustomerTenantMiddleware(response)(request)

        self.assertEqual(result.status_code, 200)
        self.assertIs(observed[0], tenant)
        self.assertIsNone(get_current_tenant())
        self.assertIs(request.customer_tenant, tenant)
