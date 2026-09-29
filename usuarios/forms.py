from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Usuario
from .seguranca import esta_bloqueado, limpar_falhas, registrar_falha

MENSAGEM_LOGIN_INVALIDO = 'Nome de usuário ou senha incorretos. Verifique os dados e tente novamente.'


class LoginForm(AuthenticationForm):
    error_messages = {
        'invalid_login': MENSAGEM_LOGIN_INVALIDO,
        # Conta bloqueada recebe a mesma mensagem: não revelamos que a conta existe
        'inactive': MENSAGEM_LOGIN_INVALIDO,
        'bloqueado': 'Muitas tentativas sem sucesso. Por segurança, aguarde 15 minutos e tente novamente.',
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
