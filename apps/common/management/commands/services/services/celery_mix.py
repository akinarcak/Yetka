from .celery_base import CeleryBaseService

__all__ = ['CeleryMixService']


class CeleryMixService(CeleryBaseService):

    def __init__(self, **kwargs):
        kwargs['queue'] = 'celery,ansible'
        super().__init__(**kwargs)

    def start_other(self):
        from terminal.startup import CeleryTerminal
        celery_terminal = CeleryTerminal()
        celery_terminal.start_heartbeat_thread()

