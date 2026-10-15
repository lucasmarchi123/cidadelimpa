"""Exclusão da conta pelo próprio titular.

A conta não é apagada do banco: os dados pessoais são substituídos por
valores sem significado (anonimização). Assim:

- o histórico dos endereços continua completo, como diz a política de privacidade;
- as denúncias já analisadas continuam valendo, mas sem nenhuma identificação;
- ninguém consegue entrar de novo nessa conta.

Apagar a linha do usuário também não seria possível: as denúncias usam
on_delete=PROTECT justamente para o histórico não sumir.
"""
import uuid

from django.db import transaction
from django.utils import timezone

from denuncias.models import Denuncia, LogAdmin

from .models import DOMINIO_CONTA_EXCLUIDA


@transaction.atomic
def excluir_conta(usuario):
    """Anonimiza a conta. Tudo acontece numa única transação:
    se algo der errado no meio, nada é alterado."""
    agora = timezone.now()
    denuncias = Denuncia.objects.filter(usuario=usuario)

    # 1. Denúncias que ainda aguardam análise: o próprio usuário já poderia
    #    excluí-las, então saem de circulação (exclusão lógica, como no resto do sistema).
    denuncias.filter(excluida=False, status=Denuncia.Status.ENVIADA).update(
        excluida=True, data_exclusao=agora, data_atualizacao=agora,
    )

    # 2. As demais passam a ser anônimas: para os outros usuários, o autor
    #    aparece como "Anônimo", e não mais como um nome abreviado.
    denuncias.update(anonima=True)

    # 3. Dados pessoais da conta substituídos. O nome de usuário e o e-mail
    #    precisam continuar únicos no banco, por isso recebem um código aleatório.
    codigo = f'excluida-{uuid.uuid4().hex[:12]}'
    usuario.username = codigo
    usuario.email = f'{codigo}@{DOMINIO_CONTA_EXCLUIDA}'
    usuario.nome_completo = 'Conta excluída'
    usuario.first_name = ''
    usuario.last_name = ''
    usuario.last_login = None
    usuario.is_active = False
    usuario.set_unusable_password()  # nenhuma senha passa a funcionar
    usuario.save()
    usuario.groups.clear()
    usuario.user_permissions.clear()

    # 4. Registro para auditoria, sem nenhum dado pessoal: nem o nome antigo,
    #    nem o endereço IP (a política só registra o IP das ações da equipe).
    LogAdmin.objects.create(
        usuario=usuario,
        acao=LogAdmin.Acao.EXCLUSAO_USUARIO,
        entidade='usuario',
        id_entidade=usuario.pk,
        descricao='Conta excluída pelo próprio titular. Dados pessoais anonimizados.',
    )
