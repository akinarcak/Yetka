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
STATUS_CACHE_KEY = 'yetka:maintenance:status:v2'
STATUS_CACHE_TTL = 60 * 60 * 24 * 8
REQUEST_TIMEOUT = (3.05, 12)
YETKA_RELEASE_API = 'https://api.github.com/repos/akinarcak/Yetka/releases/latest'
UPSTREAM_RELEASE_API = 'https://api.github.com/repos/jumpserver/jumpserver/releases/latest'
OSV_BATCH_API = 'https://api.osv.dev/v1/querybatch'
MAINTENANCE_GUIDE_URL = 'https://github.com/akinarcak/Yetka/blob/main/deploy/MAINTENANCE.md'
UPSTREAM_BASE_VERSION = os.environ.get('YETKA_UPSTREAM_BASE_VERSION', 'v4.10.17')
SKIPPED_PACKAGES = {'jumpserver', 'yetka'}
RELEASE_TAG_PATTERN = re.compile(
    r'^(?:yetka-|v)?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$'
)
UPDATE_REQUEST_DIR = os.environ.get('YETKA_UPDATE_REQUEST_DIR', '')
# One queue directory, one file per action, and the root runner decides the
# command from the systemd unit that started it -- the file itself only ever
# holds a release tag.
REQUEST_NAMES = {'apply': 'request', 'plan': 'plan-request'}
RESULT_NAME = 'last-result.json'
# The runner already bounds what it writes; this bounds what a corrupted or
# tampered result file can make the web process read into memory.
RESULT_READ_LIMIT = 256 * 1024
YETKA_RELEASE_VERSION_FILE = os.environ.get(
    'YETKA_RELEASE_VERSION_FILE', '/var/lib/yetka/release-version'
)


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


def update_queue_available():
    if not UPDATE_REQUEST_DIR:
        return False
    try:
        return os.path.isdir(UPDATE_REQUEST_DIR) and not os.path.islink(UPDATE_REQUEST_DIR)
    except OSError:
        return False


def queue_action(action, version):
    """Hand a release tag to the root-side runner.

    The file carries a validated version string and nothing else: that is what
    keeps the privilege boundary from becoming a command channel. O_EXCL makes
    a second request fail rather than overwrite a pending one, and O_NOFOLLOW
    refuses to write through a symlink planted in the queue directory.
    """
    try:
        name = REQUEST_NAMES[action]
    except KeyError:
        raise ValueError('Unknown maintenance action') from None
    if not RELEASE_TAG_PATTERN.fullmatch(version or ''):
        raise ValueError('Invalid release tag')
    if not update_queue_available():
        raise RuntimeError('Host update queue is not available')

    request_path = os.path.join(UPDATE_REQUEST_DIR, name)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(request_path, flags, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(f'A {action} request is already pending') from exc
    try:
        os.write(fd, f'{version}\n'.encode('ascii'))
        os.fsync(fd)
    finally:
        os.close(fd)


def pending_action():
    """Name of the action the host has queued but not finished, if any."""
    if not update_queue_available():
        return None
    for action, name in REQUEST_NAMES.items():
        if os.path.isfile(os.path.join(UPDATE_REQUEST_DIR, name)):
            return action
    return None


def read_last_result():
    """Return the last action the host ran, or None.

    The file is written by the root runner and only read here, so treat it as
    untrusted input anyway: cap the read, and drop anything that is not the
    expected shape rather than passing it through to the GUI.
    """
    if not update_queue_available():
        return None
    result_path = os.path.join(UPDATE_REQUEST_DIR, RESULT_NAME)
    try:
        if os.path.islink(result_path):
            return None
        with open(result_path, encoding='utf-8') as stream:
            payload = json.loads(stream.read(RESULT_READ_LIMIT))
    except (OSError, UnicodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    version = payload.get('version')
    if not RELEASE_TAG_PATTERN.fullmatch(str(version or '')):
        return None
    action = payload.get('action')
    if action not in REQUEST_NAMES:
        return None
    output = payload.get('output')
    return {
        'action': action,
        'version': version,
        'started_at': payload.get('started_at'),
        'finished_at': payload.get('finished_at'),
        'exit_code': payload.get('exit_code'),
        'succeeded': payload.get('exit_code') == 0,
        'truncated': bool(payload.get('truncated')),
        'output': output if isinstance(output, str) else '',
    }


def _current_yetka_version():
    try:
        with open(YETKA_RELEASE_VERSION_FILE, encoding='ascii') as stream:
            version = stream.readline().strip()
        if RELEASE_TAG_PATTERN.fullmatch(version):
            return version
    except (OSError, UnicodeError):
        pass
    return settings.VERSION


def _installed_python_packages():
    packages = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get('Name')
        version = distribution.version
        if not name or not version or name.lower() in SKIPPED_PACKAGES:
            continue
        packages[name.lower()] = {'name': name, 'version': version}
    return [packages[name] for name in sorted(packages)]


def _fetch_release(session, api_url):
    response = session.get(
        api_url,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'Yetka-maintenance-check',
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    release = response.json()
    latest = release.get('tag_name', '')
    if not latest or not RELEASE_TAG_PATTERN.fullmatch(latest):
        raise ValueError('Release response has no valid version tag')
    return release


def _check_yetka_release(session):
    release = _fetch_release(session, YETKA_RELEASE_API)
    latest = release['tag_name']
    current = _current_yetka_version()
    current_version = _version(current)
    latest_version = _version(latest)
    # Release channels can publish rebuilds with the same numeric version
    # (for example ``ws14`` -> ``ws17``).  Comparing only numeric tuples would
    # hide those verified artifacts from the GUI update control.
    available = bool(
        latest_version
        and latest != current
        and (current_version is None or latest_version >= current_version)
    )
    result = {
        'available': available,
        'current_version': current,
        'latest_version': latest,
        'published_at': release.get('published_at'),
        'release_url': release.get('html_url'),
        'comparison_available': current_version is not None,
    }
    if available:
        result['command'] = f'sudo yetka-update apply --version {latest}'
    return result


def _check_upstream_release(session):
    release = _fetch_release(session, UPSTREAM_RELEASE_API)
    latest = release['tag_name']
    base_version = _version(UPSTREAM_BASE_VERSION)
    latest_version = _version(latest)
    return {
        'review_required': bool(
            latest_version and base_version and latest_version > base_version
        ),
        'base_version': UPSTREAM_BASE_VERSION,
        'latest_version': latest,
        'published_at': release.get('published_at'),
        'release_url': release.get('html_url'),
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
        'upstream': status.get('upstream'),
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
        status['update'] = _check_yetka_release(session)
    except Exception as exc:
        logger.warning('Yetka release check failed: %s', exc)
        if previous.get('update'):
            status['update'] = previous['update']
        status['errors'].append({'source': 'yetka_release', 'message': str(exc)[:240]})
    try:
        status['upstream'] = _check_upstream_release(session)
    except Exception as exc:
        logger.warning('Upstream review check failed: %s', exc)
        if previous.get('upstream'):
            status['upstream'] = previous['upstream']
        status['errors'].append({'source': 'upstream_release', 'message': str(exc)[:240]})
    try:
        status['vulnerabilities'] = _check_python_vulnerabilities(session)
    except Exception as exc:
        logger.warning('OSV package vulnerability check failed: %s', exc)
        if previous.get('vulnerabilities'):
            status['vulnerabilities'] = previous['vulnerabilities']
        status['errors'].append({'source': 'osv', 'message': str(exc)[:240]})

    update_available = status.get('update', {}).get('available', False)
    upstream_review = status.get('upstream', {}).get('review_required', False)
    vulnerabilities_found = status.get('vulnerabilities', {}).get('total', 0) > 0
    status['attention_required'] = bool(
        update_available or upstream_review or vulnerabilities_found or status['errors']
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
