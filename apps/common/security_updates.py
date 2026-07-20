import hashlib
import json
import logging
import os
import re
from importlib import metadata

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


logger = logging.getLogger(__name__)
STATUS_CACHE_KEY = 'yetka:maintenance:status:v1'
STATUS_CACHE_TTL = 60 * 60 * 24 * 8
REQUEST_TIMEOUT = (3.05, 12)
UPSTREAM_RELEASE_API = 'https://api.github.com/repos/jumpserver/jumpserver/releases/latest'
OSV_BATCH_API = 'https://api.osv.dev/v1/querybatch'
MAINTENANCE_GUIDE_URL = 'https://github.com/akinarcak/Yetka/blob/dev/deploy/MAINTENANCE.md'
SKIPPED_PACKAGES = {'jumpserver', 'yetka'}


def maintenance_checks_enabled():
    value = os.environ.get('YETKA_MAINTENANCE_CHECK_ENABLED', 'true')
    return value.strip().lower() not in {'0', 'false', 'no', 'off'}


def _version(value):
    match = re.search(r'\d+(?:\.\d+){1,3}', str(value or ''))
    if not match:
        return None
    try:
        return tuple(int(part) for part in match.group(0).split('.'))
    except ValueError:
        return None


def _installed_python_packages():
    packages = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get('Name')
        version = distribution.version
        if not name or not version or name.lower() in SKIPPED_PACKAGES:
            continue
        packages[name.lower()] = {'name': name, 'version': version}
    return [packages[name] for name in sorted(packages)]


def _check_upstream_release(session):
    response = session.get(
        UPSTREAM_RELEASE_API,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'Yetka-maintenance-check',
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    release = response.json()
    latest = release.get('tag_name', '')
    if not latest or _version(latest) is None:
        raise ValueError('Upstream release response has no valid version tag')
    current = settings.VERSION
    current_version = _version(current)
    latest_version = _version(latest)
    available = bool(
        latest_version and (
            current_version is None or latest_version > current_version
        )
    )
    return {
        'available': available,
        'current_version': current,
        'latest_version': latest,
        'published_at': release.get('published_at'),
        'release_url': release.get('html_url'),
        'comparison_available': current_version is not None,
    }


def _check_python_vulnerabilities(session):
    packages = _installed_python_packages()
    if not packages:
        return {
            'total': 0, 'affected_packages': 0, 'items': [],
            'truncated': False, 'database_url': 'https://osv.dev/list',
        }
    queries = [
        {
            'package': {'ecosystem': 'PyPI', 'name': package['name']},
            'version': package['version'],
        }
        for package in packages
    ]
    response = session.post(
        OSV_BATCH_API,
        json={'queries': queries},
        headers={'User-Agent': 'Yetka-maintenance-check'},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    results = response.json().get('results', [])
    if len(results) != len(packages):
        raise ValueError('OSV response did not match the submitted package list')
    findings = []
    vulnerability_ids = set()
    for package, result in zip(packages, results):
        ids = sorted({item.get('id') for item in result.get('vulns', []) if item.get('id')})
        if not ids:
            continue
        vulnerability_ids.update(ids)
        findings.append({
            'package': package['name'],
            'version': package['version'],
            'ids': ids[:10],
        })
    return {
        'total': len(vulnerability_ids),
        'affected_packages': len(findings),
        'items': findings[:20],
        'truncated': len(findings) > 20,
        'database_url': 'https://osv.dev/list',
    }


def _fingerprint(status):
    relevant = {
        'update': status.get('update'),
        'vulnerabilities': status.get('vulnerabilities'),
        'error_sources': sorted(item.get('source', '') for item in status.get('errors', [])),
    }
    payload = json.dumps(relevant, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def refresh_maintenance_status(session=None):
    if not maintenance_checks_enabled():
        status = {
            'enabled': False,
            'attention_required': False,
            'checked_at': timezone.now().isoformat(),
            'guide_url': MAINTENANCE_GUIDE_URL,
        }
        cache.set(STATUS_CACHE_KEY, status, STATUS_CACHE_TTL)
        return status

    session = session or requests.Session()
    status = {
        'enabled': True,
        'checked_at': timezone.now().isoformat(),
        'guide_url': MAINTENANCE_GUIDE_URL,
        'errors': [],
    }
    previous = cache.get(STATUS_CACHE_KEY) or {}
    try:
        status['update'] = _check_upstream_release(session)
    except Exception as exc:
        logger.warning('Upstream maintenance release check failed: %s', exc)
        if previous.get('update'):
            status['update'] = previous['update']
        status['errors'].append({'source': 'release', 'message': str(exc)[:240]})
    try:
        status['vulnerabilities'] = _check_python_vulnerabilities(session)
    except Exception as exc:
        logger.warning('OSV package vulnerability check failed: %s', exc)
        if previous.get('vulnerabilities'):
            status['vulnerabilities'] = previous['vulnerabilities']
        status['errors'].append({'source': 'osv', 'message': str(exc)[:240]})

    update_available = status.get('update', {}).get('available', False)
    vulnerabilities_found = status.get('vulnerabilities', {}).get('total', 0) > 0
    status['attention_required'] = bool(
        update_available or vulnerabilities_found or status['errors']
    )
    status['fingerprint'] = _fingerprint(status)
    cache.set(STATUS_CACHE_KEY, status, STATUS_CACHE_TTL)
    return status


def get_maintenance_status():
    status = cache.get(STATUS_CACHE_KEY)
    if status:
        return status
    return {
        'enabled': maintenance_checks_enabled(),
        'attention_required': False,
        'pending': True,
        'checked_at': None,
        'guide_url': MAINTENANCE_GUIDE_URL,
    }
