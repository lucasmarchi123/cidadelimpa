from django.conf import settings
from django.utils import timezone
from django.views.generic import TemplateView

# Média diária de esgoto sem tratamento lançado na natureza no Brasil,
# em piscinas olímpicas. Fonte: Instituto Trata Brasil, esgotômetro (base SINISA 2024).
PISCINAS_POR_DIA = 5442


class InicioView(TemplateView):
    template_name = 'inicio.html'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)

        # Quanto do dia já passou, de 0 (meia-noite) a 1 (fim do dia)
        agora = timezone.localtime()
        meia_noite = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        fracao_do_dia = (agora - meia_noite).total_seconds() / 86400

        piscinas = max(1, round(PISCINAS_POR_DIA * fracao_do_dia))
        contexto['piscinas_hoje'] = f'{piscinas:,}'.replace(',', '.')   # 3120 vira 3.120
        contexto['email_contato'] = getattr(settings, 'EMAIL_CONTATO', '')
        return contexto
