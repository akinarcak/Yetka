from rest_framework import serializers

from .models import CustomerTenant


class CustomerTenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerTenant
        fields = ('id', 'name', 'slug')
