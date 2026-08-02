from rest_framework import serializers

from .models import CustomerTenant


class CustomerTenantSerializer(serializers.ModelSerializer):
    organization_ids = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    @staticmethod
    def get_organization_ids(obj):
        return [str(item.organization_id) for item in obj.organization_links.all()]

    def get_role(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return None
        membership = obj.memberships.filter(user=request.user).first()
        return membership.role if membership else None

    class Meta:
        model = CustomerTenant
        fields = ('id', 'name', 'slug', 'role', 'organization_ids')
