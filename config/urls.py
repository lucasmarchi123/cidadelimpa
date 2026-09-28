from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path('', TemplateView.as_view(template_name='inicio.html'), name='inicio'),
    path('contas/', include('usuarios.urls')),
    path('contas/', include('django.contrib.auth.urls')),
    path('admin/', admin.site.urls),
]