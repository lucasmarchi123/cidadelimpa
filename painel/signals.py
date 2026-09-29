from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from denuncias.models import LogAdmin

from .utils import registrar_log


@receiver(user_logged_in)
def registrar_entrada(sender, request, user, **kwargs):
    if user.is_staff:
        registrar_log(request, LogAdmin.Acao.LOGIN, 'usuario', user.pk,
                      'Entrada no sistema', usuario=user)


@receiver(user_logged_out)
def registrar_saida(sender, request, user, **kwargs):
    if user is not None and user.is_staff:
        registrar_log(request, LogAdmin.Acao.LOGOUT, 'usuario', user.pk,
                      'Saída do sistema', usuario=user)
