from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

urlpatterns = [
    # Esta rota vem antes das rotas prontas do Django, então substitui o login padrão
    path('login/', auth_views.LoginView.as_view(authentication_form=LoginForm), name='login'),
    path('cadastro/', views.cadastro, name='cadastro'),
]
