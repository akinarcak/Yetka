import logging
import os
import sys

from django.conf import settings

from jumpserver.const import CONFIG

try:
    from jumpserver import const

    __version__ = const.VERSION
except ImportError as e:
    print("Not found __version__: {}".format(e))
    print("Python is: ")
    logging.info(sys.executable)
    __version__ = 'Unknown'
    sys.exit(1)

HTTP_HOST = CONFIG.HTTP_BIND_HOST or '127.0.0.1'
HTTP_PORT = CONFIG.HTTP_LISTEN_PORT or 8080
WS_PORT = CONFIG.WS_LISTEN_PORT or 8082
DEBUG = CONFIG.DEBUG or False
BASE_DIR = os.path.dirname(settings.BASE_DIR)
LOG_DIR = os.path.join(BASE_DIR, 'data', 'logs')
APPS_DIR = os.path.join(BASE_DIR, 'apps')
TMP_DIR = os.path.join(BASE_DIR, 'tmp')
# Service PID files are written here. The directory is deliberately untracked so
# it cannot be mistaken for a package, and bare-metal installs never create it,
# so a fresh deployment would otherwise crash-loop on a missing gunicorn.pid.
# In the container image this path is a symlink to /tmp/yetka. If that target is
# missing -- which is what --tmpfs /tmp does, by masking the image's /tmp -- the
# symlink dangles and exist_ok does NOT accept it: makedirs sees the link, gets
# EEXIST, finds isdir() false and re-raises. The entrypoint therefore creates
# the symlink target before anything imports this module.
os.makedirs(TMP_DIR, exist_ok=True)
CELERY_WORKER_COUNT = CONFIG.CELERY_WORKER_COUNT or 10
