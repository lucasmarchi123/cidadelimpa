from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def equipe_requerida(view):
    """Protege uma página do painel: exige login E is_staff.

    Quem não está logado vai para o login.
    Quem está logado mas não é da equipe recebe "acesso negado" (erro 403).
    """
    @login_required
    @wraps(view)
    def protegida(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return protegida
