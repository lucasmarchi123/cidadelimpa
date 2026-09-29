from django.apps import AppConfig


class PainelConfig(AppConfig):
    name = 'painel'
    verbose_name = 'Painel administrativo'

    def ready(self):
        # Liga o registro de entrada e saída dos administradores no log
        from . import signals  # noqa: F401
