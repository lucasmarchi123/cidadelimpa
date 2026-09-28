from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import DenunciaForm


@login_required
def nova(request):
    if request.method == 'POST':
        form = DenunciaForm(request.POST, request.FILES)
        if form.is_valid():
            form.salvar(request.user)
            messages.success(request, 'Denúncia enviada. Nossa equipe vai analisá-la em breve.')
            return redirect('inicio')
    else:
        form = DenunciaForm()

    return render(request, 'denuncias/nova.html', {'form': form})
