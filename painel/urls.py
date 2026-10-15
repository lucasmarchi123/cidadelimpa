from django.urls import path

from . import views, views_municipios

urlpatterns = [
    path('', views.visao_geral, name='painel'),
    path('denuncias/', views.denuncias, name='painel_denuncias'),
    path('denuncias/<int:pk>/', views.analise, name='painel_analise'),
    path('denuncias/<int:pk>/aceitar/', views.aceitar, name='painel_aceitar'),
    path('denuncias/<int:pk>/rejeitar/', views.rejeitar, name='painel_rejeitar'),
    path('denuncias/<int:pk>/encaminhar/', views.encaminhar, name='painel_encaminhar'),
    path('denuncias/<int:pk>/resolver/', views.resolver, name='painel_resolver'),
    path('denuncias/<int:pk>/excluir/', views.excluir, name='painel_excluir'),
    path('usuarios/', views.usuarios, name='painel_usuarios'),
    path('municipios/', views_municipios.lista, name='painel_municipios'),
    path('municipios/novo/', views_municipios.criar, name='painel_municipio_criar'),
    path('municipios/<int:pk>/editar/', views_municipios.editar, name='painel_municipio_editar'),
    path('municipios/<int:pk>/excluir/', views_municipios.excluir, name='painel_municipio_excluir'),
    path('usuarios/<int:pk>/bloquear/', views.bloquear, name='painel_bloquear'),
    path('usuarios/<int:pk>/desbloquear/', views.desbloquear, name='painel_desbloquear'),
]
