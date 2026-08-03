from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from django.test import RequestFactory, SimpleTestCase
from channels.exceptions import DenyConnection

from .context import get_current_tenant
from .celery import TENANT_ORG_TASK_KEY, TENANT_TASK_KEY, TenantAwareTask
from .exceptions import TenantAccessDenied, TenantSelectionRequired
from .middleware import (
    CustomerTenantMiddleware,
    CustomerTenantWebSocketMiddleware,
    _scope_value,
    _workspace_from_cookie,
    resolve_tenant_for_user,
    validate_organization_ownership,
)
from .api import CustomerTenantListApi, TenantScopedQuerySetMixin
from .serializers import CustomerTenantSerializer


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
    def test_websocket_scope_values_are_case_insensitive(self):
        scope = {'headers': [(b'X-YETKA-TENANT', b'tenant-a')]}
        self.assertEqual(_scope_value(scope, 'x-yetka-tenant'), 'tenant-a')

    def test_websocket_workspace_is_read_from_cookie(self):
        scope = {'headers': [(b'cookie', b'foo=bar; X-JMS-ORG=org-a') ]}
        self.assertEqual(_workspace_from_cookie(scope), 'org-a')

    def test_websocket_middleware_has_explicit_tenant_contract(self):
        self.assertTrue(hasattr(CustomerTenantWebSocketMiddleware, '__call__'))


class TenantWebSocketScopeTests(IsolatedAsyncioTestCase):
    async def test_superuser_socket_does_not_require_customer_tenant(self):
        app = AsyncMock()
        middleware = CustomerTenantWebSocketMiddleware(app)
        scope = {
            'user': SimpleNamespace(is_authenticated=True, is_superuser=True),
            'headers': [],
            'path': '/ws/notifications/site-msg/',
        }

        with patch('tenants.middleware.resolve_websocket_tenant', new=AsyncMock()) as resolve:
            await middleware(scope, Mock(), Mock())

        resolve.assert_not_awaited()
        app.assert_awaited_once()

    async def test_websocket_scope_receives_verified_tenant(self):
        tenant = SimpleNamespace(id='tenant-a')
        app = AsyncMock()
        middleware = CustomerTenantWebSocketMiddleware(app)
        scope = {
            'user': SimpleNamespace(is_authenticated=True),
            'headers': [(b'x-yetka-tenant', b'tenant-a')],
        }
        with patch('tenants.middleware.resolve_websocket_tenant', new=AsyncMock(return_value=tenant)):
            await middleware(scope, Mock(), Mock())

        self.assertIs(scope['customer_tenant'], tenant)
        app.assert_awaited_once()

    async def test_websocket_scope_denies_unverified_tenant(self):
        middleware = CustomerTenantWebSocketMiddleware(AsyncMock())
        scope = {
            'user': SimpleNamespace(is_authenticated=True),
            'headers': [(b'x-yetka-tenant', b'tenant-attacker')],
        }
        with patch('tenants.middleware.resolve_websocket_tenant', new=AsyncMock(return_value=None)):
            with self.assertRaises(DenyConnection):
                await middleware(scope, Mock(), Mock())

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
    def test_workspace_mapping_selects_assigned_tenant_for_bootstrap(self, organizations):
        organizations.filter.return_value.values_list.return_value.first.return_value = 'tenant-b'
        manager = FakeMemberships([membership('tenant-a'), membership('tenant-b')])
        with patch('tenants.middleware.CustomerTenantMembership.objects', manager):
            tenant = resolve_tenant_for_user(
                SimpleNamespace(id='user-a'),
                organization=SimpleNamespace(id='org-b'),
            )

        self.assertEqual(tenant.id, 'tenant-b')
        organizations.filter.assert_called_once()

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


class FakeViewSetBase:
    def get_queryset(self):
        return self.base_queryset


class TenantScopedViewSet(TenantScopedQuerySetMixin, FakeViewSetBase):
    pass


class TenantScopedQuerySetTests(SimpleTestCase):
    def test_queryset_is_explicitly_filtered_by_verified_tenant(self):
        tenant = SimpleNamespace(id='tenant-a')
        view = TenantScopedViewSet()
        view.request = SimpleNamespace(customer_tenant=tenant)
        view.base_queryset = Mock()

        result = view.get_queryset()

        view.base_queryset.filter.assert_called_once_with(tenant=tenant)
        self.assertIs(result, view.base_queryset.filter.return_value)

    def test_queryset_is_empty_without_verified_tenant(self):
        view = TenantScopedViewSet()
        view.request = SimpleNamespace()
        view.base_queryset = Mock()

        result = view.get_queryset()

        view.base_queryset.none.assert_called_once_with()
        self.assertIs(result, view.base_queryset.none.return_value)


class CrossTenantApiContractTests(SimpleTestCase):
    def setUp(self):
        self.tenant_a = SimpleNamespace(id='tenant-a', name='Tenant A')
        self.tenant_b = SimpleNamespace(id='tenant-b', name='Tenant B')
        self.org_a = SimpleNamespace(id='org-a')
        self.org_b = SimpleNamespace(id='org-b')

    def test_tenant_list_is_membership_scoped(self):
        queryset = Mock()
        active = queryset.filter.return_value
        active.prefetch_related.return_value.distinct.return_value = ['tenant-a']
        view = CustomerTenantListApi()
        view.request = SimpleNamespace(user=SimpleNamespace(id='user-a'))

        with patch('tenants.api.CustomerTenant.objects', queryset):
            result = view.get_queryset()

        queryset.filter.assert_called_once_with(
            is_active=True, memberships__user=view.request.user
        )
        self.assertEqual(result, ['tenant-a'])

    @patch('tenants.middleware.TenantOrganization.objects')
    def test_two_workspace_fixture_mapping_rejects_cross_tenant_pair(self, organizations):
        organizations.filter.side_effect = lambda **kwargs: SimpleNamespace(
            exists=lambda: (
                kwargs['tenant'] is self.tenant_a
                and kwargs['organization'] is self.org_a
            )
        )
        validate_organization_ownership(self.tenant_a, self.org_a)
        with self.assertRaises(TenantAccessDenied):
            validate_organization_ownership(self.tenant_a, self.org_b)


class CustomerTenantSerializerTests(SimpleTestCase):
    def test_tenant_switch_payload_contains_only_mapping_and_current_role(self):
        links = Mock()
        links.all.return_value = [
            SimpleNamespace(organization_id='org-a'),
            SimpleNamespace(organization_id='org-b'),
        ]
        memberships = Mock()
        memberships.filter.return_value.first.return_value = SimpleNamespace(role='admin')
        tenant = SimpleNamespace(
            id='tenant-a', name='Tenant A', slug='tenant-a',
            organization_links=links, memberships=memberships,
        )
        user = SimpleNamespace(is_authenticated=True)

        data = CustomerTenantSerializer(
            tenant, context={'request': SimpleNamespace(user=user)}
        ).data

        self.assertEqual(data['organization_ids'], ['org-a', 'org-b'])
        self.assertEqual(data['role'], 'admin')
        memberships.filter.assert_called_once_with(user=user)


class ExampleTenantTask(TenantAwareTask):
    name = 'tenants.tests.example'

    def run(self, value):
        return value, get_current_tenant()


class FailingTenantTask(TenantAwareTask):
    name = 'tenants.tests.failing'

    def run(self):
        raise RuntimeError('boom')


def example_tenant_task():
    from ops.celery import app

    task = ExampleTenantTask()
    task.bind(app)
    return task


class TenantCeleryContextTests(SimpleTestCase):
    @patch('ops.signal_handlers.get_current_org_id', return_value='org-a')
    @patch('ops.signal_handlers.get_current_tenant_id', return_value='tenant-a')
    def test_publish_overwrites_forged_internal_context(self, tenant_id, org_id):
        from ops.signal_handlers import before_task_publish

        task_kwargs = {
            TENANT_TASK_KEY: 'tenant-attacker',
            TENANT_ORG_TASK_KEY: 'org-attacker',
        }
        before_task_publish(body=((), task_kwargs, {}))

        self.assertEqual(task_kwargs[TENANT_TASK_KEY], 'tenant-a')
        self.assertEqual(task_kwargs[TENANT_ORG_TASK_KEY], 'org-a')

    @patch('tenants.models.TenantOrganization.objects')
    @patch('tenants.models.CustomerTenant.objects')
    def test_task_runs_in_verified_tenant_and_resets_context(self, tenants, organizations):
        tenant = SimpleNamespace(id='tenant-a')
        tenants.filter.return_value.first.return_value = tenant
        organizations.filter.return_value.exists.return_value = True

        value, observed_tenant = example_tenant_task()(
            'ok',
            **{TENANT_TASK_KEY: 'tenant-a', TENANT_ORG_TASK_KEY: 'org-a'},
        )

        self.assertEqual(value, 'ok')
        self.assertIs(observed_tenant, tenant)
        self.assertIsNone(get_current_tenant())

    @patch('tenants.models.TenantOrganization.objects')
    @patch('tenants.models.CustomerTenant.objects')
    def test_cross_tenant_task_organization_is_rejected(self, tenants, organizations):
        tenants.filter.return_value.first.return_value = SimpleNamespace(id='tenant-a')
        organizations.filter.return_value.exists.return_value = False

        with self.assertRaises(TenantAccessDenied):
            example_tenant_task()(
                'unsafe',
                **{TENANT_TASK_KEY: 'tenant-a', TENANT_ORG_TASK_KEY: 'org-b'},
            )

    @patch('tenants.models.CustomerTenant.objects')
    def test_task_context_is_reset_when_task_raises(self, tenants):
        tenants.filter.return_value.first.return_value = SimpleNamespace(id='tenant-a')
        task = FailingTenantTask()
        from ops.celery import app
        task.bind(app)

        with self.assertRaises(RuntimeError):
            task(**{TENANT_TASK_KEY: 'tenant-a'})
        self.assertIsNone(get_current_tenant())
