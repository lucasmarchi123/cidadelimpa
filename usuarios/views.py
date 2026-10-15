from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from denuncias.models import Curtida, Denuncia

from .exclusao import excluir_conta as anonimizar_conta
from .forms import CadastroForm, ExcluirContaForm, MeusDadosForm
from .models import Usuario


def cadastro(request):
    # Quem já está logado não precisa criar outra conta.
    if request.user.is_authenticated:
        return redirect('inicio')

    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            return redirect('inicio')
    else:
        form = CadastroForm()

    return render(request, 'usuarios/cadastro.html', {'form': form})


@login_required
def meus_dados(request):
    # Não existe ID na URL: a página sempre mostra a conta de quem está logado.
    # Por isso não há como abrir ou alterar os dados de outra pessoa (IDOR).
    #
    # O formulário recebe uma cópia da conta, e não o request.user. Se o envio
    # tiver erro, a cópia fica com os valores digitados, mas o menu do topo
    # continua mostrando o nome que está salvo.
    conta = Usuario.objects.get(pk=request.user.pk)

    if request.method == 'POST':
        form = MeusDadosForm(request.POST, instance=conta, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, 'Seus dados foram atualizados.')
            return redirect('meus_dados')
    else:
        form = MeusDadosForm(instance=conta, request=request)

    minhas = Denuncia.objects.filter(usuario=request.user, excluida=False)
    return render(request, 'usuarios/meus_dados.html', {
        'form': form,
        'total_denuncias': minhas.count(),
        'total_curtidas': Curtida.objects.filter(usuario=request.user).count(),
    })


@login_required
def excluir_conta(request):
    usuario = request.user

    # Contas da equipe ficam nos registros de auditoria das análises.
    # Elas são encerradas pelo superusuário, nunca por esta página.
    if usuario.is_staff or usuario.is_superuser:
        messages.error(request, 'Contas da equipe administrativa não podem ser excluídas por esta página. '
                                'Peça o encerramento ao superusuário.')
        return redirect('meus_dados')

    pendentes = Denuncia.objects.filter(
        usuario=usuario, excluida=False, status=Denuncia.Status.ENVIADA,
    ).count()
    analisadas = Denuncia.objects.filter(usuario=usuario, excluida=False).count() - pendentes

    if request.method == 'POST':
        form = ExcluirContaForm(request.POST, request=request, usuario=usuario)
        if form.is_valid():
            anonimizar_conta(usuario)
            # logout() apaga a sessão inteira. A mensagem vem depois,
            # para ser guardada já na sessão nova.
            logout(request)
            messages.success(request, 'Sua conta foi excluída. Obrigado por ter contribuído com o CidadeLimpa.')
            return redirect('inicio')
    else:
        form = ExcluirContaForm(request=request, usuario=usuario)

    return render(request, 'usuarios/excluir_conta.html', {
        'form': form, 'pendentes': pendentes, 'analisadas': analisadas,
    })
