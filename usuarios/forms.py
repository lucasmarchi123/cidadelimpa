from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Usuario
from .seguranca import esta_bloqueado, limpar_falhas, registrar_falha

MENSAGEM_LOGIN_INVALIDO = 'Nome de usuário ou senha incorretos. Verifique os dados e tente novamente.'
MENSAGEM_BLOQUEIO = 'Muitas tentativas sem sucesso. Por segurança, aguarde 15 minutos e tente novamente.'


class LoginForm(AuthenticationForm):
    error_messages = {
        'invalid_login': MENSAGEM_LOGIN_INVALIDO,
        # Conta bloqueada recebe a mesma mensagem: não revelamos que a conta existe
        'inactive': MENSAGEM_LOGIN_INVALIDO,
        'bloqueado': MENSAGEM_BLOQUEIO,
    }

    def clean(self):
        username = self.cleaned_data.get('username', '')
        ip = self.request.META.get('REMOTE_ADDR', '') if self.request else ''

        # Confere o bloqueio ANTES de testar a senha
        if esta_bloqueado(username, ip):
            raise ValidationError(self.error_messages['bloqueado'], code='bloqueado')

        try:
            dados = super().clean()
        except ValidationError:
            registrar_falha(username, ip)
            raise

        limpar_falhas(username, ip)
        return dados


class CadastroForm(UserCreationForm):
    aceite_termos = forms.BooleanField(
        required=True,
        error_messages={
            'required': 'Para criar a conta, é preciso aceitar os termos de uso '
                        'e a política de privacidade.',
        },
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        # Só estes campos podem vir do formulário. Campos como is_staff
        # ficam de fora, então ninguém consegue se cadastrar como administrador.
        fields = ('nome_completo', 'username', 'email')
        labels = {
            'nome_completo': 'Nome completo',
            'username': 'Nome de usuário',
            'email': 'E-mail',
        }
        help_texts = {
            'username': 'É com ele que você vai entrar no sistema. '
                        'Use letras, números e os símbolos @ . + - _',
        }
        widgets = {
            'nome_completo': forms.TextInput(attrs={'autocomplete': 'name', 'autofocus': True}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O foco inicial fica no nome completo, primeiro campo da tela.
        self.fields['username'].widget.attrs.pop('autofocus', None)
        self.fields['password2'].label = 'Confirme a senha'
        self.fields['password2'].help_text = ''

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este e-mail já está cadastrado.')
        return email

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.data_aceite_termos = timezone.now()
        if commit:
            usuario.save()
        return usuario


def conferir_senha(request, usuario, senha):
    """Confere a senha de quem já está logado, antes de uma ação sensível.

    Usa o mesmo limite de tentativas do login: depois de 5 erros, a conferência
    fica bloqueada por 15 minutos. Assim, quem encontrar uma sessão aberta
    não consegue ficar testando senhas por aqui.
    """
    ip = request.META.get('REMOTE_ADDR', '')
    if esta_bloqueado(usuario.username, ip):
        raise ValidationError(MENSAGEM_BLOQUEIO, code='bloqueado')
    if not senha or not usuario.check_password(senha):
        registrar_falha(usuario.username, ip)
        raise ValidationError('Senha incorreta.', code='senha_incorreta')
    limpar_falhas(usuario.username, ip)


class MeusDadosForm(forms.ModelForm):
    senha_atual = forms.CharField(
        label='Senha atual',
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
        help_text='Necessária somente se você alterar o e-mail.',
    )

    class Meta:
        model = Usuario
        # Lista fechada: só nome e e-mail podem ser alterados por aqui.
        # Campos como username, is_staff e is_active ficam de fora.
        fields = ('nome_completo', 'email')
        labels = {'nome_completo': 'Nome completo', 'email': 'E-mail'}
        help_texts = {
            'email': 'É para este endereço que enviamos o link de recuperação de senha.',
        }
        widgets = {
            'nome_completo': forms.TextInput(attrs={'autocomplete': 'name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
        }

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        # Guardado antes da validação, que altera o objeto do formulário.
        self.email_original = self.instance.email

    def clean_nome_completo(self):
        nome = ' '.join(self.cleaned_data['nome_completo'].split())
        if len(nome) < 3:
            raise ValidationError('Informe seu nome completo.')
        return nome

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        repetido = Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise ValidationError('Este e-mail já está cadastrado.')
        return email

    def clean(self):
        dados = super().clean()
        email = dados.get('email')
        # Trocar o e-mail muda para onde vai o link de recuperação de senha.
        # Sem a senha, quem pegasse uma sessão aberta poderia tomar a conta.
        if email and email != self.email_original.lower():
            try:
                conferir_senha(self.request, self.instance, dados.get('senha_atual'))
            except ValidationError as erro:
                self.add_error('senha_atual', erro)
        return dados


class ExcluirContaForm(forms.Form):
    senha = forms.CharField(
        label='Sua senha',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )
    confirmacao = forms.BooleanField(
        required=True,
        error_messages={'required': 'Marque a confirmação para continuar.'},
    )

    def __init__(self, *args, request, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.usuario = usuario

    def clean_senha(self):
        senha = self.cleaned_data['senha']
        conferir_senha(self.request, self.usuario, senha)
        return senha
