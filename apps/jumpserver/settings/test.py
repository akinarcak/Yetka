"""Settings used for isolated Django test runs.

The production settings build ``DATABASES`` from the deployment config and
omit Django's optional ``TEST`` mapping.  Django 5 accesses that mapping
directly while preparing the test database, so keep the production connection
details but provide an explicit, isolated test-database name.
"""

from copy import deepcopy

from .base import *  # noqa: F401,F403


DATABASES = deepcopy(DATABASES)
_default_database = DATABASES["default"]
_test_name = _default_database.get("NAME")
if _test_name:
    _test_name = f"test_{_test_name}"

_default_database["TEST"] = {
    "NAME": _test_name,
}

# Tests must never send work to the live asynchronous workers.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
