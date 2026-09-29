from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista, name='lista_denuncias'),
    path('nova/', views.nova, name='nova_denuncia'),
    path('local/<int:pk>/', views.local, name='local'),
    path('<int:pk>/curtir/', views.curtir, name='curtir'),
    path('minhas/', views.minhas, name='minhas_denuncias'),
    path('<int:pk>/excluir/', views.excluir, name='excluir_denuncia'),
]
