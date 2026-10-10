from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista, name='lista_denuncias'),
    path('prioridades/', views.prioridades, name='prioridades'),
    path('nova/', views.nova, name='nova_denuncia'),
    path('ruas/<int:municipio_id>/', views.ruas_do_municipio, name='ruas_municipio'),
    path('local/<int:pk>/', views.local, name='local'),
    path('<int:pk>/curtir/', views.curtir, name='curtir'),
    path('minhas/', views.minhas, name='minhas_denuncias'),
    path('<int:pk>/excluir/', views.excluir, name='excluir_denuncia'),
]
