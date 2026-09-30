from django.conf import settings

from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

admin.site.login = login_required(admin.site.login)

contato = {'email_contato': getattr(settings, 'EMAIL_CONTATO', '')}

urlpatterns = [
    path('', TemplateView.as_view(template_name='inicio.html', extra_context=contato), name='inicio'),
    path('sobre/', TemplateView.as_view(template_name='sobre.html'), name='sobre'),
    path('termos/', TemplateView.as_view(template_name='institucional/termos.html', extra_context=contato), name='termos'),
    path('privacidade/', TemplateView.as_view(template_name='institucional/privacidade.html', extra_context=contato), name='privacidade'),
    path('contas/', include('usuarios.urls')),
    path('contas/', include('django.contrib.auth.urls')),
    path('denuncias/', include('denuncias.urls')),
    path('painel/', include('painel.urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)