from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Dados do CidadeLimpa', {
            'fields': ('nome_completo', 'data_aceite_termos'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Dados do CidadeLimpa', {
            'fields': ('email', 'nome_completo'),
        }),
    )
    list_display = ('username', 'nome_completo', 'email', 'is_staff', 'is_active')
