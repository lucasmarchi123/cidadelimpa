from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DenunciaForm
from .models import Curtida, Denuncia, HistoricoStatus, Local, Municipio
from .utils import normalizar, normalizar_logradouro

# Status que outros usuários podem ver. Rejeitadas ficam só no histórico do autor.
STATUS_PUBLICOS = [Denuncia.Status.ENVIADA, Denuncia.Status.ACEITA, Denuncia.Status.RESOLVIDA]
VISIVEL = Q(denuncias__excluida=False, denuncias__status__in=STATUS_PUBLICOS)


def denuncias_visiveis():
    """Denúncias que podem aparecer para outros usuários."""
    return Denuncia.objects.filter(excluida=False, status__in=STATUS_PUBLICOS)


def url_do_mapa(local):
    """Monta o endereço da imagem do Google Static Maps.
    Sem chave configurada, devolve vazio e a página mostra a ilustração."""
    chave = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    if not chave:
        return ''
    if local.latitude is not None and local.longitude is not None:
        ponto = f'{local.latitude},{local.longitude}'
    else:
        ponto = local.endereco_completo
    parametros = {
        'center': ponto, 'zoom': 17, 'size': '640x400', 'scale': 2,
        'markers': f'color:0x1E7A46|{ponto}', 'key': chave,
    }
    return 'https://maps.googleapis.com/maps/api/staticmap?' + urlencode(parametros)


@login_required
def lista(request):
    busca = request.GET.get('busca', '').strip()[:100]
    municipio_id = request.GET.get('municipio', '')

    locais = (
        Local.objects.select_related('municipio')
        .annotate(
            total=Count('denuncias', filter=VISIVEL),
            ultima=Max('denuncias__data_registro', filter=VISIVEL),
        )
        .filter(total__gt=0)
        .order_by('-ultima')
    )

    if municipio_id.isdigit():
        locais = locais.filter(municipio_id=int(municipio_id))

    if busca:
        # A comparação é feita em Python para ignorar acentos e abreviações,
        # coisa que o SQLite não faz sozinho.
        termos = {normalizar(busca), normalizar_logradouro(busca)}
        ids = [
            local.pk for local in Local.objects.only('pk', 'logradouro', 'bairro')
            if any(t in normalizar_logradouro(local.logradouro) or t in normalizar(local.bairro)
                   for t in termos)
        ]
        locais = locais.filter(pk__in=ids)

    # Carrega de uma vez as denúncias visíveis de cada endereço da página
    locais = locais.prefetch_related(Prefetch(
        'denuncias',
        queryset=denuncias_visiveis().order_by('-data_registro'),
        to_attr='visiveis',
    ))

    pagina = Paginator(locais, 12).get_page(request.GET.get('pagina'))
    municipios = sorted(
        Municipio.objects.filter(locais__isnull=False).distinct(),
        key=lambda m: normalizar(m.nome),
    )
    return render(request, 'denuncias/lista.html', {
        'pagina': pagina, 'busca': busca, 'municipio_id': municipio_id,
        'municipios': municipios, 'filtrando': bool(busca or municipio_id),
    })


@login_required
def local(request, pk):
    local = get_object_or_404(Local.objects.select_related('municipio'), pk=pk)
    denuncias = list(
        denuncias_visiveis().filter(local=local)
        .select_related('usuario')
        .annotate(
            n_curtidas=Count('curtidas'),
            curtiu=Exists(Curtida.objects.filter(denuncia=OuterRef('pk'), usuario=request.user)),
        )
        .order_by('-data_registro')
    )
    # Endereço sem nenhuma denúncia visível não é exibido
    if not denuncias:
        raise Http404

    return render(request, 'denuncias/local.html', {
        'local': local,
        'denuncias': denuncias,
        'situacao': denuncias[0],
        'total_curtidas': sum(d.n_curtidas for d in denuncias),
        'mapa_url': url_do_mapa(local),
    })


@login_required
@require_POST
def curtir(request, pk):
    # Só denúncias visíveis podem ser curtidas
    denuncia = get_object_or_404(denuncias_visiveis(), pk=pk)
    # O autor não curte a própria denúncia
    if denuncia.usuario_id != request.user.pk:
        curtida, criada = Curtida.objects.get_or_create(denuncia=denuncia, usuario=request.user)
        if not criada:
            curtida.delete()   # segundo clique desfaz a curtida
    return redirect(f"{reverse('local', args=[denuncia.local_id])}#denuncia-{denuncia.pk}")


def dados_iniciais(request):
    """Quando o usuário vem do botão 'Registrar denúncia aqui',
    o formulário já chega com o endereço preenchido."""
    local_id = request.GET.get('local', '')
    if not local_id.isdigit():
        return {}
    local = (Local.objects.filter(pk=int(local_id), denuncias__in=denuncias_visiveis())
             .distinct().first())
    if not local:
        return {}
    return {
        'municipio': local.municipio_id, 'logradouro': local.logradouro,
        'numero': local.numero, 'bairro': local.bairro,
        'cep': local.cep_formatado, 'ponto_referencia': local.ponto_referencia,
    }


@login_required
def nova(request):
    if request.method == 'POST':
        form = DenunciaForm(request.POST, request.FILES)
        if form.is_valid():
            denuncia = form.salvar(request.user)
            messages.success(request, 'Denúncia enviada. Nossa equipe vai analisá-la em breve.')
            return redirect('local', pk=denuncia.local_id)
    else:
        form = DenunciaForm(initial=dados_iniciais(request))

    return render(request, 'denuncias/nova.html', {'form': form})


FILTROS_STATUS = [
    ('', 'Todas'),
    (Denuncia.Status.ENVIADA, 'Enviadas'),
    (Denuncia.Status.ACEITA, 'Aceitas'),
    (Denuncia.Status.RESOLVIDA, 'Resolvidas'),
    (Denuncia.Status.REJEITADA, 'Rejeitadas'),
]


@login_required
def minhas(request):
    # A consulta parte SEMPRE do usuário logado: ninguém vê denúncias de outra pessoa aqui.
    base = Denuncia.objects.filter(usuario=request.user, excluida=False)

    contagem = {
        linha['status']: linha['total']
        for linha in base.order_by().values('status').annotate(total=Count('pk'))
    }

    status = request.GET.get('status', '')
    if status not in Denuncia.Status.values:
        status = ''

    denuncias = base.filter(status=status) if status else base
    denuncias = (
        denuncias.select_related('local__municipio')
        .prefetch_related(Prefetch(
            'historico',
            queryset=HistoricoStatus.objects.order_by('data_alteracao'),
            to_attr='andamento',
        ))
        .order_by('-data_registro')
    )

    pagina = Paginator(denuncias, 10).get_page(request.GET.get('pagina'))
    for d in pagina:
        # Motivo da rejeição, se a equipe tiver escrito um
        d.motivo = next(
            (h.observacao for h in reversed(d.andamento)
             if h.status_novo == Denuncia.Status.REJEITADA and h.observacao),
            '',
        )

    filtros = [
        {'valor': valor, 'rotulo': rotulo, 'ativo': valor == status,
         'total': sum(contagem.values()) if not valor else contagem.get(valor, 0)}
        for valor, rotulo in FILTROS_STATUS
    ]
    return render(request, 'denuncias/minhas.html', {
        'pagina': pagina, 'filtros': filtros, 'status': status,
        'tem_denuncias': bool(contagem),
    })


@login_required
@require_POST
def excluir(request, pk):
    # Uma única operação que só funciona se TODAS as condições forem verdadeiras:
    # a denúncia existe, é do usuário logado, não foi excluída e ainda não foi analisada.
    agora = timezone.now()
    excluidas = Denuncia.objects.filter(
        pk=pk, usuario=request.user, excluida=False, status=Denuncia.Status.ENVIADA,
    ).update(excluida=True, data_exclusao=agora, data_atualizacao=agora)

    if excluidas:
        messages.success(request, 'Denúncia excluída.')
    else:
        messages.error(request, 'Esta denúncia não pode ser excluída.')
    return redirect('minhas_denuncias')
