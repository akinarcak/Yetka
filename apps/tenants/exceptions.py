class TenantContextError(Exception):
    status_code = 400
    code = 'tenant_context_invalid'


class TenantSelectionRequired(TenantContextError):
    code = 'tenant_selection_required'


class TenantAccessDenied(TenantContextError):
    status_code = 403
    code = 'tenant_access_denied'
