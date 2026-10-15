from django import forms

from denuncias.models import Municipio
from denuncias.utils import normalizar


class MunicipioForm(forms.ModelForm):
    class Meta:
        model = Municipio
        # Só estes campos podem vir do formulário
        fields = ('nome', 'uf', 'codigo_ibge')
        labels = {'nome': 'Nome do município', 'uf': 'UF', 'codigo_ibge': 'Código do IBGE'}
        help_texts = {
            'codigo_ibge': 'Sete números. É usado para ligar o município à lista de ruas do IBGE.',
        }
        widgets = {
            'nome': forms.TextInput(attrs={'autofocus': True}),
            'uf': forms.TextInput(attrs={'maxlength': 2, 'autocapitalize': 'characters'}),
            'codigo_ibge': forms.TextInput(attrs={'inputmode': 'numeric', 'maxlength': 7}),
        }

    def clean_nome(self):
        nome = ' '.join(self.cleaned_data['nome'].split())
        if len(nome) < 2:
            raise forms.ValidationError('Informe o nome do município.')
        return nome

    def clean_uf(self):
        uf = self.cleaned_data['uf'].strip().upper()
        if len(uf) != 2 or not uf.isalpha():
            raise forms.ValidationError('A UF tem duas letras. Exemplo: RN.')
        return uf

    def clean_codigo_ibge(self):
        codigo = (self.cleaned_data.get('codigo_ibge') or '').strip()
        if not codigo:
            return None            # vazio vira nulo, para não bater na regra de código único
        if len(codigo) != 7 or not codigo.isdigit():
            raise forms.ValidationError('O código do IBGE tem 7 números. Exemplo: 2408102.')
        return codigo

    def clean(self):
        dados = super().clean()
        nome, uf = dados.get('nome'), dados.get('uf')
        if nome and uf:
            # "Sao Jose" e "São José" contam como o mesmo município
            outros = Municipio.objects.filter(uf=uf)
            if self.instance.pk:
                outros = outros.exclude(pk=self.instance.pk)
            if any(normalizar(m.nome) == normalizar(nome) for m in outros):
                self.add_error('nome', f'Já existe um município com esse nome em {uf}.')
        return dados
