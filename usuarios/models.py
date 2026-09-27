from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    email = models.EmailField('e-mail', unique=True)
    nome_completo = models.CharField('nome completo', max_length=150)
    telefone = models.CharField(max_length=20, blank=True)
    data_aceite_termos = models.DateTimeField(
        'data de aceite dos termos', null=True, blank=True
    )

    REQUIRED_FIELDS = ['email', 'nome_completo']

    def __str__(self):
        return self.username