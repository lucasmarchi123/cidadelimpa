from django.urls import path

from . import views

urlpatterns = [
    path('nova/', views.nova, name='nova_denuncia'),
]
