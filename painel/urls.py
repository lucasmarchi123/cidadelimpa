from django.urls import path

from . import views

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
    path('usuarios/<int:pk>/bloquear/', views.bloquear, name='painel_bloquear'),
    path('usuarios/<int:pk>/desbloquear/', views.desbloquear, name='painel_desbloquear'),
]
