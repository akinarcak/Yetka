from django.urls import path

from .api import CustomerTenantListApi


app_name = 'tenants'

urlpatterns = [
    path('', CustomerTenantListApi.as_view(), name='tenant-list'),
]
