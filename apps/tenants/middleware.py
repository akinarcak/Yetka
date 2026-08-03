from django.http import JsonResponse

from .context import tenant_context
from .exceptions import TenantAccessDenied, TenantContextError, TenantSelectionRequired
from .models import CustomerTenantMembership, TenantOrganization
from channels.db import database_sync_to_async
from channels.exceptions import DenyConnection
from common.utils import get_logger


logger = get_logger(__name__)


TENANT_HEADER = 'HTTP_X_YETKA_TENANT'
EXEMPT_API_PATHS = ('/api/v1/tenants/', '/api/health/', '/api/v1/health/')


def resolve_tenant_for_user(user, requested_id=None, organization=None):
    memberships = CustomerTenantMembership.objects.select_related('tenant').filter(
        user=user, tenant__is_active=True
    )
    if requested_id:
        try:
            membership = memberships.filter(tenant_id=requested_id).first()
        except (TypeError, ValueError):
            membership = None
        if membership is None:
            raise TenantAccessDenied('The requested customer tenant is not assigned to this user')
        return membership.tenant

    if organization is not None:
        tenant_id = TenantOrganization.objects.filter(
            organization=organization,
            tenant__memberships__user=user,
            tenant__is_active=True,
        ).values_list('tenant_id', flat=True).first()
        if tenant_id:
            membership = memberships.filter(tenant_id=tenant_id).first()
            if membership:
                return membership.tenant

    available = list(memberships[:2])
    if not available:
        return None
    if len(available) > 1:
        raise TenantSelectionRequired('X-YETKA-TENANT is required when multiple tenants are assigned')
    return available[0].tenant


def validate_organization_ownership(tenant, organization):
    if tenant is None or organization is None:
        return
    if not TenantOrganization.objects.filter(tenant=tenant, organization=organization).exists():
        raise TenantAccessDenied('The selected organization does not belong to the customer tenant')


class CustomerTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def should_resolve(request):
        return request.path.startswith('/api/') and not request.path.startswith(EXEMPT_API_PATHS)

    def __call__(self, request):
        if not self.should_resolve(request) or not request.user.is_authenticated:
            return self.get_response(request)

        try:
            tenant = resolve_tenant_for_user(
                request.user,
                request.META.get(TENANT_HEADER),
                getattr(request, 'current_org', None),
            )
            validate_organization_ownership(tenant, getattr(request, 'current_org', None))
        except TenantContextError as exc:
            return JsonResponse({'detail': str(exc), 'code': exc.code}, status=exc.status_code)

        request.customer_tenant = tenant
        with tenant_context(tenant):
            return self.get_response(request)


def _scope_value(scope, name):
    """Return a decoded ASGI header value, case-insensitively."""
    wanted = name.lower().encode()
    for key, value in scope.get('headers', []):
        if key.lower() == wanted:
            return value.decode('latin1')
    return None


def _workspace_from_cookie(scope):
    cookie = _scope_value(scope, 'cookie') or ''
    for item in cookie.split(';'):
        key, separator, value = item.strip().partition('=')
        if separator and key == 'X-JMS-ORG':
            return value or None
    return None


@database_sync_to_async
def resolve_websocket_tenant(user, requested_id=None, organization_id=None):
    organization = None
    if organization_id:
        from orgs.models import Organization
        organization = Organization.objects.filter(id=organization_id).first()
    return resolve_tenant_for_user(user, requested_id, organization)


@database_sync_to_async
def is_terminal_service_user(user):
    return hasattr(user, 'terminal')


class CustomerTenantWebSocketMiddleware:
    """Bind every authenticated websocket to an authorized customer tenant."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        user = scope.get('user')
        if not user or not user.is_authenticated:
            raise DenyConnection()
        # System administrators are not customer-tenant members, but the
        # global notification socket is not tenant-scoped. Keep tenant
        # binding mandatory for terminal and component sockets.
        if scope.get('path') == '/ws/notifications/site-msg/' and user.is_superuser:
            return await self.app(scope, receive, send)
        # Component service accounts (Koko/Lion/etc.) authenticate with a
        # signed access key and are intentionally not customer members.
        # Their terminal task channel must be available before a user tenant
        # context exists; user-facing sockets still require tenant binding.
        if await is_terminal_service_user(user):
            return await self.app(scope, receive, send)
        requested_id = _scope_value(scope, 'x-yetka-tenant')
        organization_id = _workspace_from_cookie(scope)
        try:
            tenant = await resolve_websocket_tenant(user, requested_id, organization_id)
        except Exception as exc:
            logger.warning('Websocket tenant resolution denied: %s', exc)
            raise DenyConnection()
        if tenant is None:
            raise DenyConnection()
        scope['customer_tenant'] = tenant
        with tenant_context(tenant):
            return await self.app(scope, receive, send)
