from django.conf import settings
from django.db import models


class Municipio(models.Model):
    nome = models.CharField(max_length=120)
    uf = models.CharField(max_length=2, default='RN')
    codigo_ibge = models.CharField(max_length=7, unique=True, null=True, blank=True)

    class Meta:
        verbose_name = 'município'
        verbose_name_plural = 'municípios'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['nome', 'uf'], name='uk_municipio_nome'),
        ]

    def __str__(self):
        return f'{self.nome}/{self.uf}'


class Local(models.Model):
    municipio = models.ForeignKey(
        Municipio, on_delete=models.PROTECT, related_name='locais'
    )
    cep = models.CharField(max_length=8, blank=True)
    logradouro = models.CharField(max_length=150)
    numero = models.CharField(max_length=20, default='S/N')
    bairro = models.CharField(max_length=100)
    ponto_referencia = models.CharField('ponto de referência', max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'local'
        verbose_name_plural = 'locais'
        constraints = [
            models.UniqueConstraint(
                fields=['municipio', 'bairro', 'logradouro', 'numero'],
                name='uk_local_endereco',
            ),
        ]

    def __str__(self):
        return f'{self.logradouro}, {self.numero} - {self.bairro}'

    @property
    def cep_formatado(self):
        """59030000 vira 59030-000."""
        if len(self.cep) == 8:
            return f'{self.cep[:5]}-{self.cep[5:]}'
        return self.cep

    @property
    def endereco_completo(self):
        """Endereço em uma linha, no formato que o Google Maps entende."""
        partes = [self.logradouro]
        if self.numero and self.numero != 'S/N':
            partes.append(self.numero)
        partes += [self.bairro, self.municipio.nome, self.municipio.uf, 'Brasil']
        return ', '.join(partes)


class Denuncia(models.Model):

    class Status(models.TextChoices):
        ENVIADA = 'ENVIADA', 'Enviada'
        ACEITA = 'ACEITA', 'Aceita'
        RESOLVIDA = 'RESOLVIDA', 'Resolvida'
        REJEITADA = 'REJEITADA', 'Rejeitada'

    local = models.ForeignKey(
        Local, on_delete=models.PROTECT, related_name='denuncias'
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='denuncias'
    )
    descricao = models.TextField('descrição')
    foto = models.ImageField(upload_to='denuncias/%Y/%m/')
    anonima = models.BooleanField('anônima', default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ENVIADA)
    data_ocorrencia = models.DateField('data da ocorrência', null=True, blank=True)
    data_registro = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    admin_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='denuncias_analisadas',
    )
    encaminhada_orgao = models.BooleanField('encaminhada ao órgão', default=False)
    data_encaminhamento = models.DateField(null=True, blank=True)
    excluida = models.BooleanField(default=False)
    data_exclusao = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'denúncia'
        verbose_name_plural = 'denúncias'
        ordering = ['-data_registro']

    def __str__(self):
        return f'Denúncia #{self.pk} - {self.get_status_display()}'

    @property
    def autor_publico(self):
        """Nome do autor como aparece para os outros usuários.

        Denúncia anônima: 'Anônimo'. As demais mostram só o primeiro nome
        e a inicial do último ('Maria S.'), para não expor o nome completo.
        Os templates públicos devem usar SEMPRE este campo, nunca o usuario.
        """
        if self.anonima:
            return 'Anônimo'
        partes = (self.usuario.nome_completo or self.usuario.username).split()
        if len(partes) > 1:
            return f'{partes[0]} {partes[-1][0]}.'
        return partes[0]


class Curtida(models.Model):
    denuncia = models.ForeignKey(
        Denuncia, on_delete=models.CASCADE, related_name='curtidas'
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='curtidas'
    )
    data_curtida = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['denuncia', 'usuario'], name='uk_curtida_unica'),
        ]

    def __str__(self):
        return f'{self.usuario} curtiu a denúncia #{self.denuncia_id}'


class HistoricoStatus(models.Model):
    denuncia = models.ForeignKey(
        Denuncia, on_delete=models.CASCADE, related_name='historico'
    )
    status_anterior = models.CharField(
        max_length=10, choices=Denuncia.Status.choices, null=True, blank=True
    )
    status_novo = models.CharField(max_length=10, choices=Denuncia.Status.choices)
    usuario_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alteracoes_status',
    )
    data_alteracao = models.DateTimeField(auto_now_add=True)
    observacao = models.CharField('observação', max_length=255, blank=True)

    class Meta:
        verbose_name = 'histórico de status'
        verbose_name_plural = 'históricos de status'
        ordering = ['-data_alteracao']

    def __str__(self):
        return f'#{self.denuncia_id}: {self.status_anterior or "-"} → {self.status_novo}'


class LogAdmin(models.Model):

    class Acao(models.TextChoices):
        LOGIN = 'LOGIN', 'Login'
        LOGOUT = 'LOGOUT', 'Logout'
        ALTERACAO_STATUS = 'ALTERACAO_STATUS', 'Alteração de status'
        EXCLUSAO_DENUNCIA = 'EXCLUSAO_DENUNCIA', 'Exclusão de denúncia'
        ENCAMINHAMENTO = 'ENCAMINHAMENTO', 'Encaminhamento'
        BLOQUEIO_USUARIO = 'BLOQUEIO_USUARIO', 'Bloqueio de usuário'
        DESBLOQUEIO_USUARIO = 'DESBLOQUEIO_USUARIO', 'Desbloqueio de usuário'
        EXCLUSAO_USUARIO = 'EXCLUSAO_USUARIO', 'Exclusão de usuário'
        OUTRO = 'OUTRO', 'Outro'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='logs',
    )
    acao = models.CharField('ação', max_length=20, choices=Acao.choices)
    entidade = models.CharField(max_length=50, blank=True)
    id_entidade = models.PositiveIntegerField(null=True, blank=True)
    descricao = models.CharField('descrição', max_length=255, blank=True)
    endereco_ip = models.GenericIPAddressField('endereço IP', null=True, blank=True)
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'log administrativo'
        verbose_name_plural = 'logs administrativos'
        ordering = ['-data_hora']

    def __str__(self):
        return f'{self.get_acao_display()} em {self.data_hora:%d/%m/%Y %H:%M}'
