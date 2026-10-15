"""Testes da conta do usuário: Meus dados e Excluir minha conta.

Para rodar: python manage.py test usuarios
"""
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from denuncias.models import Curtida, Denuncia, Local, LogAdmin, Municipio

from .models import Usuario

SENHA = 'Senha-Forte-123'


def criar_usuario(username, **extra):
    dados = {'email': f'{username}@exemplo.com', 'nome_completo': f'{username.title()} da Silva'}
    dados.update(extra)
    return Usuario.objects.create_user(username=username, password=SENHA, **dados)


class BaseContaTest(TestCase):
    def setUp(self):
        cache.clear()  # zera o limite de tentativas de senha entre um teste e outro
        self.ana = criar_usuario('ana')
        self.bruno = criar_usuario('bruno')
        self.client.force_login(self.ana)


class MeusDadosTest(BaseContaTest):
    url = reverse('meus_dados')

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(self.url)
        self.assertRedirects(resposta, f"{reverse('login')}?next={self.url}")

    def test_mostra_apenas_os_dados_de_quem_esta_logado(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '@ana')
        self.assertContains(resposta, 'ana@exemplo.com')
        self.assertNotContains(resposta, 'bruno@exemplo.com')

    def test_altera_o_nome_sem_pedir_senha(self):
        resposta = self.client.post(self.url, {'nome_completo': '  Ana   Maria  Souza ', 'email': 'ana@exemplo.com'})
        self.assertRedirects(resposta, self.url)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.nome_completo, 'Ana Maria Souza')

    def test_trocar_email_exige_a_senha(self):
        resposta = self.client.post(self.url, {'nome_completo': 'Ana', 'email': 'nova@exemplo.com'})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Senha incorreta.')
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.email, 'ana@exemplo.com')

    def test_troca_email_com_a_senha_certa(self):
        self.client.post(self.url, {'nome_completo': 'Ana Souza', 'email': 'Nova@Exemplo.com',
                                    'senha_atual': SENHA})
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.email, 'nova@exemplo.com')

    def test_nao_aceita_email_de_outra_conta(self):
        resposta = self.client.post(self.url, {'nome_completo': 'Ana', 'email': 'BRUNO@exemplo.com',
                                               'senha_atual': SENHA})
        self.assertContains(resposta, 'Este e-mail já está cadastrado.')

    def test_ignora_campos_que_nao_estao_no_formulario(self):
        # Tentativa de virar administrador ou trocar o username pela requisição
        self.client.post(self.url, {'nome_completo': 'Ana Souza', 'email': 'ana@exemplo.com',
                                    'is_staff': 'on', 'is_superuser': 'on', 'username': 'bruno'})
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.is_staff)
        self.assertFalse(self.ana.is_superuser)
        self.assertEqual(self.ana.username, 'ana')

    def test_formulario_sem_token_csrf_e_recusado(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.ana)
        resposta = cliente.post(self.url, {'nome_completo': 'Invasor', 'email': 'ana@exemplo.com'})
        self.assertEqual(resposta.status_code, 403)
        self.ana.refresh_from_db()
        self.assertNotEqual(self.ana.nome_completo, 'Invasor')


class ExcluirContaTest(BaseContaTest):
    url = reverse('excluir_conta')

    def setUp(self):
        super().setUp()
        natal = Municipio.objects.get(nome='Natal')
        local = Local.objects.create(municipio=natal, logradouro='Rua das Flores', bairro='Alecrim')
        criar = lambda status: Denuncia.objects.create(  # noqa: E731
            local=local, usuario=self.ana, descricao='Esgoto na calçada',
            foto='denuncias/teste.jpg', status=status,
        )
        self.pendente = criar(Denuncia.Status.ENVIADA)
        self.aceita = criar(Denuncia.Status.ACEITA)
        self.curtida = Curtida.objects.create(denuncia=self.aceita, usuario=self.ana)

    def confirmar(self, senha=SENHA, confirmacao='on'):
        return self.client.post(self.url, {'senha': senha, 'confirmacao': confirmacao})

    def test_exige_login(self):
        self.client.logout()
        resposta = self.client.get(self.url)
        self.assertRedirects(resposta, f"{reverse('login')}?next={self.url}")

    def test_get_nao_exclui_nada(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Excluir minha conta')
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)

    def test_senha_errada_nao_exclui(self):
        resposta = self.confirmar(senha='errada')
        self.assertContains(resposta, 'Senha incorreta.')
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.username, 'ana')

    def test_sem_marcar_a_confirmacao_nao_exclui(self):
        resposta = self.confirmar(confirmacao='')
        self.assertContains(resposta, 'Marque a confirmação para continuar.')
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)

    def test_bloqueia_depois_de_muitas_senhas_erradas(self):
        for _ in range(5):
            self.confirmar(senha='errada')
        resposta = self.confirmar()  # agora com a senha certa
        self.assertContains(resposta, 'aguarde 15 minutos')
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)

    def test_exclusao_anonimiza_a_conta(self):
        id_ana = self.ana.pk
        resposta = self.confirmar()
        self.assertRedirects(resposta, reverse('inicio'))

        ana = Usuario.objects.get(pk=id_ana)
        self.assertTrue(ana.conta_excluida)
        self.assertFalse(ana.is_active)
        self.assertFalse(ana.has_usable_password())
        self.assertEqual(ana.nome_completo, 'Conta excluída')
        self.assertNotIn('ana', ana.username)
        self.assertNotIn('ana', ana.email)

        # A sessão foi encerrada
        self.assertNotIn('_auth_user_id', self.client.session)
        # E ninguém consegue entrar de novo com os dados antigos
        self.assertFalse(self.client.login(username='ana', password=SENHA))

    def test_exclusao_trata_as_denuncias_e_as_curtidas(self):
        self.confirmar()
        self.pendente.refresh_from_db()
        self.aceita.refresh_from_db()
        self.assertTrue(self.pendente.excluida)     # aguardava análise: sai de circulação
        self.assertFalse(self.aceita.excluida)      # analisada: continua no histórico
        self.assertTrue(self.aceita.anonima)
        self.assertEqual(self.aceita.autor_publico, 'Anônimo')
        self.assertTrue(Curtida.objects.filter(pk=self.curtida.pk).exists())

    def test_exclusao_fica_registrada_sem_dados_pessoais(self):
        self.confirmar()
        log = LogAdmin.objects.get(acao=LogAdmin.Acao.EXCLUSAO_USUARIO, id_entidade=self.ana.pk)
        self.assertIsNone(log.endereco_ip)
        self.assertNotIn('Ana', log.descricao)
        self.assertNotIn('ana@exemplo.com', log.descricao)

    def test_so_exclui_a_propria_conta(self):
        # Não existe ID na URL. Mesmo enviando o ID de outra pessoa, só a Ana é afetada.
        self.client.post(self.url, {'senha': SENHA, 'confirmacao': 'on', 'pk': self.bruno.pk,
                                    'usuario': self.bruno.pk})
        self.bruno.refresh_from_db()
        self.assertTrue(self.bruno.is_active)
        self.assertEqual(self.bruno.username, 'bruno')

    def test_conta_da_equipe_nao_pode_ser_excluida_por_aqui(self):
        admin = criar_usuario('admin', is_staff=True)
        self.client.force_login(admin)
        resposta = self.client.post(self.url, {'senha': SENHA, 'confirmacao': 'on'})
        self.assertRedirects(resposta, reverse('meus_dados'))
        admin.refresh_from_db()
        self.assertTrue(admin.is_active)

    def test_formulario_sem_token_csrf_e_recusado(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.ana)
        resposta = cliente.post(self.url, {'senha': SENHA, 'confirmacao': 'on'})
        self.assertEqual(resposta.status_code, 403)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.is_active)


class ContaExcluidaNoPainelTest(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = criar_usuario('admin', is_staff=True)
        self.ana = criar_usuario('ana')
        self.client.force_login(self.ana)
        self.client.post(reverse('excluir_conta'), {'senha': SENHA, 'confirmacao': 'on'})
        self.client.force_login(self.admin)

    def test_aparece_no_filtro_de_contas_excluidas(self):
        resposta = self.client.get(reverse('painel_usuarios'), {'filtro': 'excluidas'})
        self.assertContains(resposta, 'Conta excluída')
        resposta = self.client.get(reverse('painel_usuarios'), {'filtro': 'bloqueados'})
        self.assertNotContains(resposta, 'Conta excluída')

    def test_nao_pode_ser_desbloqueada(self):
        resposta = self.client.post(reverse('painel_desbloquear', args=[self.ana.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.is_active)
