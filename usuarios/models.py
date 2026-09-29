from django.contrib.auth.models import AbstractUser
from django.db import models


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
