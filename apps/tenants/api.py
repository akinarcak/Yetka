from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from .models import CustomerTenant
from .serializers import CustomerTenantSerializer


class TenantScopedQuerySetMixin:
    tenant_field = 'tenant'

    def get_customer_tenant(self):
        return getattr(self.request, 'customer_tenant', None)

    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = self.get_customer_tenant()
        if tenant is None:
            return queryset.none()
        return queryset.filter(**{self.tenant_field: tenant})

    def perform_create(self, serializer):
        tenant = self.get_customer_tenant()
        if tenant is None:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('A verified customer tenant is required')
        serializer.save(**{self.tenant_field: tenant})


class CustomerTenantListApi(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CustomerTenantSerializer

    def get_queryset(self):
        return CustomerTenant.objects.filter(
            is_active=True, memberships__user=self.request.user
        ).distinct()
