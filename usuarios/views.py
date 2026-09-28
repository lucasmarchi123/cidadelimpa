from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import CadastroForm


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
