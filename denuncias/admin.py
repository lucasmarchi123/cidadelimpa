from django.contrib import admin

from .models import Curtida, Denuncia, HistoricoStatus, Local, LogAdmin, Municipio


@admin.register(Municipio)
class MunicipioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'uf', 'codigo_ibge')
    search_fields = ('nome',)


@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ('logradouro', 'numero', 'bairro', 'municipio')
    search_fields = ('logradouro', 'bairro', 'cep')


@admin.register(Denuncia)
class DenunciaAdmin(admin.ModelAdmin):
    list_display = ('id', 'local', 'usuario', 'status', 'anonima', 'data_registro', 'excluida')
    list_filter = ('status', 'anonima', 'encaminhada_orgao', 'excluida')
    search_fields = ('descricao', 'local__logradouro', 'local__bairro')


@admin.register(Curtida)
class CurtidaAdmin(admin.ModelAdmin):
    list_display = ('denuncia', 'usuario', 'data_curtida')


@admin.register(HistoricoStatus)
class HistoricoStatusAdmin(admin.ModelAdmin):
    list_display = ('denuncia', 'status_anterior', 'status_novo', 'usuario_responsavel', 'data_alteracao')
    list_filter = ('status_novo',)


@admin.register(LogAdmin)
class LogAdminAdmin(admin.ModelAdmin):
    list_display = ('data_hora', 'acao', 'usuario', 'entidade', 'id_entidade', 'endereco_ip')
    list_filter = ('acao',)

    