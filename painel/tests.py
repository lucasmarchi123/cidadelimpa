"""Testes do CRUD de municípios no painel administrativo.

Para rodar: python manage.py test painel
"""
from django.test import Client, TestCase
from django.urls import reverse

from denuncias.models import Local, LogAdmin, Municipio
from usuarios.models import Usuario

SENHA = 'Senha-Forte-123'


class MunicipiosTest(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            'admin', 'admin@exemplo.com', SENHA, nome_completo='Admin Teste', is_staff=True)
        self.comum = Usuario.objects.create_user(
            'ana', 'ana@exemplo.com', SENHA, nome_completo='Ana Souza')
        self.natal = Municipio.objects.get(nome='Natal')
        self.client.force_login(self.admin)

    # ---- Leitura ----
    def test_lista_mostra_os_municipios_do_rn(self):
        resposta = self.client.get(reverse('painel_municipios'), {'busca': 'natal'})
        self.assertContains(resposta, 'Natal')

    # ---- Criação ----
    def test_cria_municipio(self):
        resposta = self.client.post(reverse('painel_municipio_criar'),
                                    {'nome': '  Cidade   Teste ', 'uf': 'rn', 'codigo_ibge': ''})
        self.assertRedirects(resposta, reverse('painel_municipios'))
        criado = Municipio.objects.get(nome='Cidade Teste')
        self.assertEqual(criado.uf, 'RN')
        self.assertIsNone(criado.codigo_ibge)
        self.assertTrue(LogAdmin.objects.filter(entidade='municipio', id_entidade=criado.pk).exists())

    def test_nao_cria_municipio_repetido_mesmo_sem_acento(self):
        self.assertTrue(Municipio.objects.filter(nome='São Tomé').exists())
        resposta = self.client.post(reverse('painel_municipio_criar'), {'nome': 'sao tome', 'uf': 'RN'})
        self.assertContains(resposta, 'Já existe um município com esse nome em RN.')

    def test_valida_codigo_do_ibge(self):
        resposta = self.client.post(reverse('painel_municipio_criar'),
                                    {'nome': 'Cidade Teste', 'uf': 'RN', 'codigo_ibge': '12ab'})
        self.assertContains(resposta, 'O código do IBGE tem 7 números.')

    # ---- Atualização ----
    def test_edita_municipio(self):
        teste = Municipio.objects.create(nome='Cidade Teste', uf='RN')
        self.client.post(reverse('painel_municipio_editar', args=[teste.pk]),
                         {'nome': 'Cidade Editada', 'uf': 'RN', 'codigo_ibge': ''})
        teste.refresh_from_db()
        self.assertEqual(teste.nome, 'Cidade Editada')

    # ---- Exclusão ----
    def test_exclui_municipio_sem_uso(self):
        teste = Municipio.objects.create(nome='Cidade Teste', uf='RN')
        self.client.post(reverse('painel_municipio_excluir', args=[teste.pk]))
        self.assertFalse(Municipio.objects.filter(pk=teste.pk).exists())

    def test_nao_exclui_municipio_em_uso(self):
        Local.objects.create(municipio=self.natal, logradouro='Rua A', bairro='Centro')
        self.client.post(reverse('painel_municipio_excluir', args=[self.natal.pk]))
        self.assertTrue(Municipio.objects.filter(pk=self.natal.pk).exists())

    def test_exclusao_so_por_post(self):
        teste = Municipio.objects.create(nome='Cidade Teste', uf='RN')
        resposta = self.client.get(reverse('painel_municipio_excluir', args=[teste.pk]))
        self.assertEqual(resposta.status_code, 405)
        self.assertTrue(Municipio.objects.filter(pk=teste.pk).exists())

    # ---- Segurança ----
    def test_usuario_comum_nao_acessa_nenhuma_rota(self):
        self.client.force_login(self.comum)
        teste = Municipio.objects.create(nome='Cidade Teste', uf='RN')
        rotas = [
            ('get', reverse('painel_municipios')),
            ('get', reverse('painel_municipio_criar')),
            ('get', reverse('painel_municipio_editar', args=[teste.pk])),
            ('post', reverse('painel_municipio_excluir', args=[teste.pk])),
        ]
        for metodo, url in rotas:
            with self.subTest(url=url):
                self.assertEqual(getattr(self.client, metodo)(url).status_code, 403)
        self.assertTrue(Municipio.objects.filter(pk=teste.pk).exists())

    def test_visitante_vai_para_o_login(self):
        self.client.logout()
        resposta = self.client.get(reverse('painel_municipios'))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse('login'), resposta['Location'])

    def test_exclusao_sem_token_csrf_e_recusada(self):
        teste = Municipio.objects.create(nome='Cidade Teste', uf='RN')
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        resposta = cliente.post(reverse('painel_municipio_excluir', args=[teste.pk]))
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Municipio.objects.filter(pk=teste.pk).exists())
