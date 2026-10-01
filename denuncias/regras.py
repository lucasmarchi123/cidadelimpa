"""Regras de negócio compartilhadas pelo site e pelo painel."""
from django.db.models import Count, IntegerField, OuterRef, Subquery
from django.db.models.functions import Coalesce

from .models import Curtida, Denuncia

# Status que outros usuários podem ver. Rejeitadas ficam só no histórico do autor.
STATUS_PUBLICOS = [Denuncia.Status.ENVIADA, Denuncia.Status.ACEITA, Denuncia.Status.RESOLVIDA]

# Curtidas que um endereço precisa somar para virar "Prioridade da comunidade".
# Para testar no seu computador, você pode baixar este número temporariamente.
META_PRIORIDADE = 1


def curtidas_do_endereco(campo_local='local'):
    """Subconsulta: total de curtidas nas denúncias visíveis de um endereço.

    campo_local diz onde está o endereço na consulta principal:
    'local' quando a consulta é de denúncias, 'pk' quando é de endereços.
    """
    total = (
        Curtida.objects
        .filter(denuncia__local=OuterRef(campo_local),
                denuncia__excluida=False,
                denuncia__status__in=STATUS_PUBLICOS)
        .order_by()
        .values('denuncia__local')
        .annotate(n=Count('pk'))
        .values('n')
    )
    return Coalesce(Subquery(total, output_field=IntegerField()), 0)


def e_prioridade(curtidas, status_atual):
    """Endereço resolvido não precisa mais do selo."""
    return curtidas >= META_PRIORIDADE and status_atual != Denuncia.Status.RESOLVIDA
