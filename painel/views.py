from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Min, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from denuncias.models import Denuncia, HistoricoStatus, Local, LogAdmin, Municipio
from denuncias.regras import META_PRIORIDADE, curtidas_do_endereco
from denuncias.utils import normalizar, normalizar_logradouro

from .decorators import equipe_requerida
from .utils import formatar_duracao, pode_alterar_usuario, registrar_log

Usuario = get_user_model()
S = Denuncia.Status
PUBLICOS = [S.ENVIADA, S.ACEITA, S.RESOLVIDA]


# =====================================================================
# Visão geral
# =====================================================================

@equipe_requerida
def visao_geral(request):
    agora = timezone.now()
    ativas = Denuncia.objects.filter(excluida=False)

    por_status = {
        linha['status']: linha['n']
        for linha in ativas.order_by().values('status').annotate(n=Count('pk'))
    }
    total = sum(por_status.values())
    enviadas = por_status.get(S.ENVIADA, 0)
    aceitas = por_status.get(S.ACEITA, 0)
    resolvidas = por_status.get(S.RESOLVIDA, 0)
    rejeitadas = por_status.get(S.REJEITADA, 0)
    analisadas = aceitas + resolvidas + rejeitadas

    mais_antiga = ativas.filter(status=S.ENVIADA).aggregate(m=Min('data_registro'))['m']

    # Tempo médio entre o envio e a primeira decisão da equipe
    duracoes, vistas = [], set()
    primeiras = (
        HistoricoStatus.objects
        .filter(status_anterior=S.ENVIADA, denuncia__excluida=False)
        .order_by('data_alteracao')
        .values_list('denuncia_id', 'data_alteracao', 'denuncia__data_registro')
    )
    for denuncia_id, alteracao, registro in primeiras:
        if denuncia_id not in vistas:
            vistas.add(denuncia_id)
            duracoes.append((alteracao - registro).total_seconds())

    publicas = ativas.filter(status__in=PUBLICOS)
    municipios = list(
        publicas.order_by().values('local__municipio__nome')
        .annotate(n=Count('pk')).order_by('-n')[:5]
    )
    maior = municipios[0]['n'] if municipios else 1
    for m in municipios:
        m['largura'] = round(m['n'] * 100 / maior)

    enderecos = (
        Local.objects.select_related('municipio')
        .annotate(n=Count('denuncias', filter=Q(denuncias__excluida=False,
                                                denuncias__status__in=PUBLICOS)))
        .filter(n__gt=0).order_by('-n')[:5]
    )

    fila = list(
        ativas.filter(status=S.ENVIADA).select_related('local__municipio')
        .annotate(curtidas_local=curtidas_do_endereco())
        .order_by('data_registro')[:5]
    )
    for d in fila:
        d.espera = (agora - d.data_registro).days

    return render(request, 'painel/visao_geral.html', {
        'aba': 'geral',
        'enviadas': enviadas, 'aceitas': aceitas,
        'resolvidas': resolvidas, 'rejeitadas': rejeitadas,
        'espera_max': (agora - mais_antiga).days if mais_antiga else None,
        'nao_encaminhadas': ativas.filter(status=S.ACEITA, encaminhada_orgao=False).count(),
        'pct_resolvidas': round(resolvidas * 100 / total) if total else 0,
        'pct_rejeitadas': round(rejeitadas * 100 / analisadas) if analisadas else 0,
        'ultimos_30': ativas.filter(data_registro__gte=agora - timedelta(days=30)).count(),
        'tempo_medio': formatar_duracao(sum(duracoes) / len(duracoes)) if duracoes else None,
        'total_usuarios': Usuario.objects.count(),
        'municipios': municipios, 'enderecos': enderecos, 'fila': fila,
        'meta': META_PRIORIDADE,
    })


# =====================================================================
# Denúncias: fila e análise
# =====================================================================

FILTROS_DENUNCIAS = [
    (S.ENVIADA, 'Aguardando análise'),
    (S.ACEITA, 'Aceitas'),
    (S.RESOLVIDA, 'Resolvidas'),
    (S.REJEITADA, 'Rejeitadas'),
    ('TODAS', 'Todas'),
]


@equipe_requerida
def denuncias(request):
    ativas = Denuncia.objects.filter(excluida=False)
    contagem = {
        linha['status']: linha['n']
        for linha in ativas.order_by().values('status').annotate(n=Count('pk'))
    }

    status = request.GET.get('status', S.ENVIADA)
    if status not in dict(FILTROS_DENUNCIAS):
        status = S.ENVIADA
    lista = ativas if status == 'TODAS' else ativas.filter(status=status)

    busca = request.GET.get('busca', '').strip()[:100]
    if busca:
        numero = busca.lstrip('#nº ')
        if numero.isdigit():
            lista = lista.filter(pk=int(numero))
        else:
            termos = {normalizar(busca), normalizar_logradouro(busca)}
            ids = [
                local.pk for local in Local.objects.only('pk', 'logradouro', 'bairro')
                if any(t in normalizar_logradouro(local.logradouro) or t in normalizar(local.bairro)
                       for t in termos)
            ]
            lista = lista.filter(local_id__in=ids)

    municipio_id = request.GET.get('municipio', '')
    if municipio_id.isdigit():
        lista = lista.filter(local__municipio_id=int(municipio_id))

    # Prioridade da comunidade: endereço com muitas curtidas e ainda não resolvido
    lista = lista.annotate(curtidas_local=curtidas_do_endereco()).annotate(
        prioridade=Case(
            When(curtidas_local__gte=META_PRIORIDADE, status__in=[S.ENVIADA, S.ACEITA], then=Value(1)),
            default=Value(0), output_field=IntegerField(),
        )
    )
    # Na fila de análise, as prioridades vêm primeiro; depois, quem espera há mais tempo
    if status == S.ENVIADA:
        ordem = ['-prioridade', 'data_registro']
    else:
        ordem = ['-data_registro']
    lista = lista.select_related('local__municipio', 'usuario').order_by(*ordem)
    pagina = Paginator(lista, 20).get_page(request.GET.get('pagina'))

    filtros = [
        {'valor': valor, 'rotulo': rotulo, 'ativo': valor == status,
         'total': sum(contagem.values()) if valor == 'TODAS' else contagem.get(valor, 0)}
        for valor, rotulo in FILTROS_DENUNCIAS
    ]
    municipios = sorted(
        Municipio.objects.filter(locais__denuncias__excluida=False).distinct(),
        key=lambda m: normalizar(m.nome),
    )
    return render(request, 'painel/denuncias.html', {
        'aba': 'denuncias', 'pagina': pagina, 'filtros': filtros, 'status': status,
        'busca': busca, 'municipio_id': municipio_id, 'municipios': municipios,
    })


@equipe_requerida
def analise(request, pk):
    d = get_object_or_404(
        Denuncia.objects.select_related('local__municipio', 'usuario')
        .annotate(curtidas_local=curtidas_do_endereco()),
        pk=pk, excluida=False,
    )
    outras = (Denuncia.objects.filter(local=d.local, excluida=False)
              .exclude(pk=d.pk).order_by('-data_registro'))
    do_autor = Denuncia.objects.filter(usuario=d.usuario, excluida=False)

    return render(request, 'painel/analise.html', {
        'aba': 'denuncias',
        'd': d,
        'historico': d.historico.select_related('usuario_responsavel').order_by('data_alteracao'),
        'outras_total': outras.count(),
        'outra_recente': outras.first(),
        'espera': (timezone.now() - d.data_registro).days,
        'autor_total': do_autor.count(),
        'autor_rejeitadas': do_autor.filter(status=S.REJEITADA).count(),
        'hoje': timezone.localdate(),
        'meta': META_PRIORIDADE,
    })


def _alterar_status(request, pk, de, para, observacao='', extras=None, descricao=''):
    """Muda o status SOMENTE se a denúncia ainda estiver no status esperado.

    A condição fica dentro da própria operação no banco. Se dois administradores
    clicarem ao mesmo tempo, só o primeiro consegue; o segundo recebe um aviso.
    """
    agora = timezone.now()
    campos = {'status': para, 'admin_responsavel': request.user, 'data_atualizacao': agora}
    campos.update(extras or {})
    with transaction.atomic():
        alteradas = (Denuncia.objects
                     .filter(pk=pk, excluida=False, status=de)
                     .update(**campos))
        if alteradas:
            HistoricoStatus.objects.create(
                denuncia_id=pk, status_anterior=de, status_novo=para,
                usuario_responsavel=request.user, observacao=observacao[:255],
            )
            registrar_log(request, LogAdmin.Acao.ALTERACAO_STATUS, 'denuncia', pk,
                          descricao or f'Status alterado para {S(para).label}')
    return bool(alteradas)


def _resultado(request, pk, sucesso, mensagem):
    if sucesso:
        messages.success(request, mensagem)
        return redirect('painel_analise', pk=pk)
    messages.error(request, 'Esta ação não pode ser feita: a denúncia já mudou de situação '
                            'ou não está mais disponível.')
    return redirect('painel_denuncias')


@equipe_requerida
@require_POST
def aceitar(request, pk):
    encaminhada = request.POST.get('encaminhada') == 'on'
    extras = {}
    descricao = 'Denúncia aceita'
    if encaminhada:
        extras = {'encaminhada_orgao': True, 'data_encaminhamento': timezone.localdate()}
        descricao += ' e encaminhada à prefeitura'
    ok = _alterar_status(request, pk, S.ENVIADA, S.ACEITA, extras=extras, descricao=descricao)
    return _resultado(request, pk, ok, 'Denúncia aceita.')


@equipe_requerida
@require_POST
def rejeitar(request, pk):
    motivo = request.POST.get('motivo', '').strip()
    ok = _alterar_status(request, pk, S.ENVIADA, S.REJEITADA, observacao=motivo,
                         descricao='Denúncia rejeitada')
    return _resultado(request, pk, ok, 'Denúncia rejeitada.')


@equipe_requerida
@require_POST
def resolver(request, pk):
    ok = _alterar_status(request, pk, S.ACEITA, S.RESOLVIDA, descricao='Denúncia marcada como resolvida')
    return _resultado(request, pk, ok, 'Denúncia marcada como resolvida.')


@equipe_requerida
@require_POST
def encaminhar(request, pk):
    try:
        data = parse_date(request.POST.get('data', '')) or timezone.localdate()
    except ValueError:
        data = None
    if data is None or data > timezone.localdate():
        messages.error(request, 'Informe uma data válida, que não esteja no futuro.')
        return redirect('painel_analise', pk=pk)

    with transaction.atomic():
        ok = (Denuncia.objects
              .filter(pk=pk, excluida=False, status=S.ACEITA, encaminhada_orgao=False)
              .update(encaminhada_orgao=True, data_encaminhamento=data,
                      admin_responsavel=request.user, data_atualizacao=timezone.now()))
        if ok:
            registrar_log(request, LogAdmin.Acao.ENCAMINHAMENTO, 'denuncia', pk,
                          f'Encaminhada à prefeitura em {data:%d/%m/%Y}')
    return _resultado(request, pk, ok, 'Encaminhamento registrado.')


@equipe_requerida
@require_POST
def excluir(request, pk):
    agora = timezone.now()
    with transaction.atomic():
        ok = (Denuncia.objects.filter(pk=pk, excluida=False)
              .update(excluida=True, data_exclusao=agora, data_atualizacao=agora))
        if ok:
            registrar_log(request, LogAdmin.Acao.EXCLUSAO_DENUNCIA, 'denuncia', pk,
                          'Denúncia excluída pela equipe')
    if ok:
        messages.success(request, f'Denúncia nº {pk} excluída.')
    else:
        messages.error(request, 'Esta denúncia não está mais disponível.')
    return redirect('painel_denuncias')


# =====================================================================
# Usuários
# =====================================================================

FILTROS_USUARIOS = [
    ('todos', 'Todos'), ('ativos', 'Ativos'),
    ('bloqueados', 'Bloqueados'), ('admins', 'Administradores'),
]
ORDENS = {
    'recentes': ('-date_joined', 'Cadastro mais recente'),
    'denuncias': ('-n_denuncias', 'Mais denúncias'),
    'rejeitadas': ('-n_rejeitadas', 'Mais rejeitadas'),
}


@equipe_requerida
def usuarios(request):
    base = Usuario.objects.all()
    grupos = {
        'todos': base,
        'ativos': base.filter(is_active=True),
        'bloqueados': base.filter(is_active=False),
        'admins': base.filter(is_staff=True),
    }
    filtro = request.GET.get('filtro', 'todos')
    if filtro not in grupos:
        filtro = 'todos'
    lista = grupos[filtro]

    busca = request.GET.get('busca', '').strip()[:100]
    if busca:
        termo = normalizar(busca.lstrip('@'))
        ids = [
            u.pk for u in Usuario.objects.only('pk', 'username', 'nome_completo')
            if termo in normalizar(u.nome_completo) or termo in normalizar(u.username)
        ]
        lista = lista.filter(pk__in=ids)

    ordem = request.GET.get('ordem', 'recentes')
    if ordem not in ORDENS:
        ordem = 'recentes'
    lista = lista.annotate(
        n_denuncias=Count('denuncias', filter=Q(denuncias__excluida=False)),
        n_rejeitadas=Count('denuncias', filter=Q(denuncias__excluida=False,
                                                 denuncias__status=S.REJEITADA)),
    ).order_by(ORDENS[ordem][0], '-date_joined')

    pagina = Paginator(lista, 20).get_page(request.GET.get('pagina'))
    for u in pagina:
        u.pode_alterar = pode_alterar_usuario(request.user, u)

    filtros = [
        {'valor': valor, 'rotulo': rotulo, 'ativo': valor == filtro, 'total': grupos[valor].count()}
        for valor, rotulo in FILTROS_USUARIOS
    ]
    return render(request, 'painel/usuarios.html', {
        'aba': 'usuarios', 'pagina': pagina, 'filtros': filtros, 'filtro': filtro,
        'busca': busca, 'ordem': ordem,
        'ordens': [(chave, rotulo) for chave, (_, rotulo) in ORDENS.items()],
    })


@equipe_requerida
@require_POST
def bloquear(request, pk):
    alvo = get_object_or_404(Usuario, pk=pk)
    if not pode_alterar_usuario(request.user, alvo):
        raise PermissionDenied
    motivo = request.POST.get('motivo', '').strip()[:200]
    if not motivo:
        messages.error(request, 'Informe o motivo do bloqueio.')
    elif alvo.is_active:
        alvo.is_active = False
        alvo.save(update_fields=['is_active'])
        registrar_log(request, LogAdmin.Acao.BLOQUEIO_USUARIO, 'usuario', alvo.pk,
                      f'Bloqueio de @{alvo.username}: {motivo}')
        messages.success(request, f'A conta @{alvo.username} foi bloqueada.')
    return redirect('painel_usuarios')


@equipe_requerida
@require_POST
def desbloquear(request, pk):
    alvo = get_object_or_404(Usuario, pk=pk)
    if not pode_alterar_usuario(request.user, alvo):
        raise PermissionDenied
    if not alvo.is_active:
        alvo.is_active = True
        alvo.save(update_fields=['is_active'])
        registrar_log(request, LogAdmin.Acao.DESBLOQUEIO_USUARIO, 'usuario', alvo.pk,
                      f'Desbloqueio de @{alvo.username}')
        messages.success(request, f'A conta @{alvo.username} foi desbloqueada.')
    return redirect('painel_usuarios')
