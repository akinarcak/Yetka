from rest_framework import filters


class AuthKeyQueryDeclaration(filters.BaseFilterBackend):
    # Declared as a filter backend on the SSO login action purely so the
    # `authkey` query parameter appeared in the CoreAPI schema. DRF 3.17
    # removed coreapi, and drf-spectacular -- what this project actually
    # generates OpenAPI with -- never called get_schema_fields, so the
    # declaration documented nothing. It defines no filter_queryset and never
    # did, so removing the body changes no behaviour.
    #
    # Kept rather than deleted because authentication/api/sso.py still names
    # it. Removing both is a separate change to an authentication endpoint.
    pass
