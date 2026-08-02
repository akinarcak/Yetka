"""Django test runner safeguards for the deployment database backend."""

from django.db import connections
from django.test.runner import DiscoverRunner


class IsolatedDiscoverRunner(DiscoverRunner):
    """Ensure Django 5 sees an explicit isolated TEST mapping."""

    def setup_databases(self, **kwargs):
        for connection in connections.all():
            test_settings = connection.settings_dict.setdefault("TEST", {})
            test_settings.setdefault("CHARSET", None)
            test_settings.setdefault("COLLATION", None)
            test_settings.setdefault("MIGRATE", True)
            test_settings.setdefault("MIRROR", None)
            if test_settings.get("NAME") is None:
                database_name = connection.settings_dict.get("NAME")
                if database_name:
                    test_settings["NAME"] = f"test_{database_name}"
        return super().setup_databases(**kwargs)
