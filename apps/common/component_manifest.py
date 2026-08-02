import json
from pathlib import Path

from django.conf import settings


DEFAULT_MANIFEST = Path(settings.BASE_DIR).parents[1] / 'supported-components.json'


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
