from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

# Domínio usado no e-mail de contas excluídas. O final ".invalid" é reservado
# pela internet para endereços que não existem, então nenhum e-mail chega lá.
DOMINIO_CONTA_EXCLUIDA = 'conta-excluida.invalid'


def filtro_conta_excluida():
    """Filtro de banco que encontra as contas excluídas pelo próprio titular.

    Uma conta excluída tem as três marcas ao mesmo tempo: está inativa, não tem
    senha utilizável e usa o e-mail reservado. Uma pessoa comum não consegue
    reunir as três, porque toda conta criada pelo cadastro tem senha.
    """
    return Q(
        is_active=False,
        password__startswith=UNUSABLE_PASSWORD_PREFIX,
        email__endswith='@' + DOMINIO_CONTA_EXCLUIDA,
    )


class Usuario(AbstractUser):
    email = models.EmailField('e-mail', unique=True)
    nome_completo = models.CharField('nome completo', max_length=150)
    data_aceite_termos = models.DateTimeField(
        'data de aceite dos termos', null=True, blank=True
    )

    REQUIRED_FIELDS = ['email', 'nome_completo']

    def __str__(self):
        return self.username

    @property
    def conta_excluida(self):
        """Mesma regra de filtro_conta_excluida(), para um usuário já carregado."""
        return (
            not self.is_active
            and not self.has_usable_password()
            and self.email.endswith('@' + DOMINIO_CONTA_EXCLUIDA)
        )

    @property
    def primeiro_nome(self):
        """'Lucas Galvão Marchi' vira 'Lucas'."""
        return (self.nome_completo or self.username).split()[0]

    @property
    def iniciais(self):
        """'Lucas Galvão Marchi' vira 'LM'. Usado no círculo do menu da conta."""
        partes = (self.nome_completo or self.username).split()
        iniciais = partes[0][0]
        if len(partes) > 1:
            iniciais += partes[-1][0]
        return iniciais.upper()
