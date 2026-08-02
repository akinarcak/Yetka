import json
from pathlib import Path

from django.conf import settings


# BASE_DIR is the ``apps`` directory in both the source tree and the image.
# The manifest is shipped once at the application root beside ``apps``.
DEFAULT_MANIFEST = Path(settings.BASE_DIR).parent / 'supported-components.json'


def load_supported_components(path=None):
    manifest_path = Path(path or DEFAULT_MANIFEST)
    with manifest_path.open(encoding='utf-8') as manifest:
        data = json.load(manifest)
    return data['components']


def component_status(name):
    return load_supported_components().get(name, {
        'status': 'unavailable',
        'runtime': 'unknown',
        'reason': 'Component is not in the supported manifest',
    })
