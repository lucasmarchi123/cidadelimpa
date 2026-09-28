import re

from django import forms
from django.db import transaction
from django.utils import timezone

from .models import Denuncia, HistoricoStatus, Local, Municipio
from .utils import normalizar, normalizar_logradouro, processar_foto


class DenunciaForm(forms.Form):
    # 1. Onde fica o problema
    municipio = forms.ModelChoiceField(
        queryset=Municipio.objects.all(), label='Município',
        error_messages={'required': 'Selecione o município.'},
    )
    logradouro = forms.CharField(
        label='Rua', max_length=150,
        widget=forms.TextInput(attrs={'autocomplete': 'address-line1'}),
    )
    numero = forms.CharField(
        label='Número', max_length=20, required=False,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'placeholder': 'S/N'}),
    )
    bairro = forms.CharField(label='Bairro', max_length=100)
    cep = forms.CharField(
        label='CEP', max_length=9, required=False,
        widget=forms.TextInput(attrs={
            'inputmode': 'numeric', 'autocomplete': 'postal-code', 'placeholder': '59000-000',
        }),
    )
    ponto_referencia = forms.CharField(
        label='Ponto de referência', max_length=255, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Ex.: em frente à escola municipal'}),
    )

    # 2. Foto
    foto = forms.ImageField(
        label='Foto',
        help_text='Formatos JPG, PNG ou WEBP, com até 5 MB. '
                  'Enquadre o esgoto de forma que apareça com clareza.',
        widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}),
        error_messages={'required': 'Envie uma foto do problema.'},
    )

    # 3. Descrição
    descricao = forms.CharField(
        label='O que está acontecendo?', max_length=2000,
        help_text='Conte desde quando ocorre, se há mau cheiro e se atinge casas, escolas ou comércios.',
        widget=forms.Textarea(attrs={'rows': 5}),
    )
    data_ocorrencia = forms.DateField(
        label='Quando você percebeu o problema?', required=False,
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
    )

    # 4. Privacidade
    anonima = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O banco ordena mal nomes com acento (Açu depois de Arês).
        # Por isso a lista é ordenada aqui, ignorando os acentos.
        municipios = sorted(Municipio.objects.all(), key=lambda m: normalizar(m.nome))
        self.fields['municipio'].choices = (
            [('', 'Selecione o município')] + [(m.pk, m.nome) for m in municipios]
        )

    # ---------- validações de cada campo ----------

    def clean_logradouro(self):
        return ' '.join(self.cleaned_data['logradouro'].split())

    def clean_bairro(self):
        return ' '.join(self.cleaned_data['bairro'].split())

    def clean_numero(self):
        numero = self.cleaned_data['numero'].strip()
        if normalizar(numero).replace(' ', '') in ('', 's/n', 'sn'):
            return 'S/N'
        return numero

    def clean_cep(self):
        cep = re.sub(r'\D', '', self.cleaned_data['cep'])
        if cep and len(cep) != 8:
            raise forms.ValidationError('O CEP deve ter 8 números. Exemplo: 59000-000.')
        return cep

    def clean_foto(self):
        return processar_foto(self.cleaned_data['foto'])

    def clean_descricao(self):
        descricao = self.cleaned_data['descricao'].strip()
        if len(descricao) < 20:
            raise forms.ValidationError(
                'Descreva o problema com um pouco mais de detalhes (pelo menos 20 caracteres).'
            )
        return descricao

    def clean_data_ocorrencia(self):
        data = self.cleaned_data['data_ocorrencia']
        if data and data > timezone.localdate():
            raise forms.ValidationError('A data não pode estar no futuro.')
        return data

    # ---------- gravação ----------

    def _obter_local(self):
        """Procura o endereço entre os já cadastrados no município.
        Se existir, a denúncia entra no histórico dele. Se não, cria um novo."""
        dados = self.cleaned_data
        chave = (
            normalizar_logradouro(dados['logradouro']),
            normalizar(dados['bairro']),
            normalizar(dados['numero']),
        )
        for local in Local.objects.filter(municipio=dados['municipio']):
            if (normalizar_logradouro(local.logradouro), normalizar(local.bairro),
                    normalizar(local.numero)) == chave:
                return local

        return Local.objects.create(
            municipio=dados['municipio'],
            logradouro=dados['logradouro'],
            numero=dados['numero'],
            bairro=dados['bairro'],
            cep=dados['cep'],
            ponto_referencia=dados['ponto_referencia'],
        )

    def salvar(self, usuario):
        dados = self.cleaned_data
        # Tudo ou nada: se algo falhar no meio, nada fica gravado pela metade.
        with transaction.atomic():
            denuncia = Denuncia.objects.create(
                local=self._obter_local(),
                usuario=usuario,
                descricao=dados['descricao'],
                foto=dados['foto'],
                anonima=dados['anonima'],
                data_ocorrencia=dados['data_ocorrencia'],
            )
            HistoricoStatus.objects.create(
                denuncia=denuncia,
                status_novo=Denuncia.Status.ENVIADA,
                observacao='Denúncia registrada',
            )
        return denuncia
