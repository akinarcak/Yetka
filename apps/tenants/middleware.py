from django.http import JsonResponse

from .context import tenant_context
from .exceptions import TenantAccessDenied, TenantContextError, TenantSelectionRequired
from .models import CustomerTenantMembership, TenantOrganization


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
