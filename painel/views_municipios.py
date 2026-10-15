"""CRUD de municípios no painel administrativo.

Município é uma das tabelas sem chave estrangeira do sistema. Todas as
operações exigem um usuário da equipe (is_staff) e ficam registradas no log.
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from denuncias.models import LogAdmin, Municipio
from denuncias.utils import normalizar

from .decorators import equipe_requerida
from .forms import MunicipioForm
from .utils import registrar_log


def _com_contagens(consulta):
    return consulta.annotate(
        n_locais=Count('locais', distinct=True),
        n_ruas=Count('logradouros', distinct=True),
    )


@equipe_requerida
def lista(request):
    busca = request.GET.get('busca', '').strip()[:100]
    municipios = _com_contagens(Municipio.objects.all())
    if busca:
        termo = normalizar(busca)
        ids = [m.pk for m in Municipio.objects.only('pk', 'nome', 'codigo_ibge')
               if termo in normalizar(m.nome) or termo == (m.codigo_ibge or '')]
        municipios = municipios.filter(pk__in=ids)

    # Ordena ignorando acentos: o banco colocaria "Açu" depois de "Arês"
    ordenados = sorted(municipios, key=lambda m: normalizar(m.nome))
    pagina = Paginator(ordenados, 25).get_page(request.GET.get('pagina'))
    return render(request, 'painel/municipios.html', {
        'aba': 'municipios', 'pagina': pagina, 'busca': busca,
        'total': Municipio.objects.count(),
    })


@equipe_requerida
def criar(request):
    form = MunicipioForm(request.POST if request.method == 'POST' else None, initial={'uf': 'RN'})
    if request.method == 'POST' and form.is_valid():
        municipio = form.save()
        registrar_log(request, LogAdmin.Acao.OUTRO, 'municipio', municipio.pk,
                      f'Município cadastrado: {municipio}')
        messages.success(request, f'Município {municipio.nome} cadastrado.')
        return redirect('painel_municipios')
    return render(request, 'painel/municipio_form.html', {
        'aba': 'municipios', 'form': form, 'titulo': 'Cadastrar município',
    })


@equipe_requerida
def editar(request, pk):
    municipio = get_object_or_404(_com_contagens(Municipio.objects.all()), pk=pk)
    nome_antigo = str(municipio)
    form = MunicipioForm(request.POST if request.method == 'POST' else None, instance=municipio)
    if request.method == 'POST' and form.is_valid():
        if form.has_changed():
            form.save()
            registrar_log(request, LogAdmin.Acao.OUTRO, 'municipio', municipio.pk,
                          f'Município alterado: {nome_antigo} → {municipio}')
            messages.success(request, f'Município {municipio.nome} atualizado.')
        return redirect('painel_municipios')
    return render(request, 'painel/municipio_form.html', {
        'aba': 'municipios', 'form': form, 'municipio': municipio,
        'titulo': f'Editar {municipio.nome}',
    })


@equipe_requerida
@require_POST
def excluir(request, pk):
    municipio = get_object_or_404(_com_contagens(Municipio.objects.all()), pk=pk)

    # Município com endereços de denúncias ou com ruas cadastradas não pode sair:
    # apagar quebraria denúncias existentes ou a lista de ruas do formulário.
    if municipio.n_locais or municipio.n_ruas:
        messages.error(request, f'{municipio.nome} não pode ser excluído: tem '
                                f'{municipio.n_locais} endereço(s) de denúncia e '
                                f'{municipio.n_ruas} rua(s) cadastradas.')
        return redirect('painel_municipios')

    descricao = f'Município excluído: {municipio}'
    try:
        with transaction.atomic():
            municipio.delete()
            registrar_log(request, LogAdmin.Acao.OUTRO, 'municipio', pk, descricao)
    except ProtectedError:
        # Alguém cadastrou um endereço nele entre a conferência e a exclusão
        messages.error(request, f'{municipio.nome} passou a ter endereços e não pode ser excluído.')
        return redirect('painel_municipios')

    messages.success(request, f'Município {municipio.nome} excluído.')
    return redirect('painel_municipios')
