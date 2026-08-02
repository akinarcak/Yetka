from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from .models import CustomerTenant
from .serializers import CustomerTenantSerializer


class CustomerTenantListApi(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = CustomerTenantSerializer

    def get_queryset(self):
        return CustomerTenant.objects.filter(
            is_active=True, memberships__user=self.request.user
        ).distinct()
