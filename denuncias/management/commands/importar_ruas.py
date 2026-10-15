r"""Importa as ruas dos municípios do RN a partir do CNEFE (IBGE, Censo 2022).

Primeira vez, com o arquivo baixado do IBGE (CSV ou ZIP):
    python manage.py importar_ruas C:\caminho\para\o\arquivo.zip

Depois disso, o comando também gera o arquivo denuncias/dados/ruas_rn.csv,
pequeno, que vai para o GitHub. Nos outros computadores basta rodar:
    python manage.py importar_ruas
"""
import csv
import gzip
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from denuncias.models import Logradouro, Municipio
from denuncias.utils import normalizar, normalizar_logradouro

ARQUIVO_COMPACTO = Path(__file__).resolve().parents[2] / 'dados' / 'ruas_rn.csv'
ARQUIVO_MUNICIPIOS = Path(__file__).resolve().parents[2] / 'dados' / 'municipios_rn.csv'
URL_MUNICIPIOS_RN = 'https://servicodados.ibge.gov.br/api/v1/localidades/estados/24/municipios'

COLUNAS = ['COD_MUNICIPIO', 'NOM_TIPO_SEGLOGR', 'NOM_TITULO_SEGLOGR', 'NOM_SEGLOGR']
MINUSCULAS = {'a', 'as', 'o', 'os', 'da', 'das', 'de', 'do', 'dos', 'e', 'em', 'na', 'nas', 'no', 'nos'}
ROMANO = re.compile(r'^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$')
SEM_NOME = {'', 'sem denominacao', 'sem nome', 'nao identificado', 'projetada'}

# Municípios que o IBGE escreve de outro jeito: nosso nome -> nome do IBGE
APELIDOS_IBGE = {
    'ares': 'arez',     # Arês
    'acu': 'assu',      # Açu
}


def chave_municipio(nome):
    """'Olho-d'Água do Borges' e 'Olho d'Agua do Borges' viram a mesma chave."""
    return re.sub(r'[^a-z0-9]', '', normalizar(nome))


def formatar(texto):
    """Nomes em maiúsculas viram 'Rua das Flores'. Nomes já formatados ficam como estão."""
    texto = ' '.join(texto.split())
    if not texto.isupper():
        return texto
    palavras = []
    for i, palavra in enumerate(texto.split(' ')):
        if palavra and ROMANO.match(palavra):
            palavras.append(palavra)                 # XV de Novembro
        elif i > 0 and palavra.lower() in MINUSCULAS:
            palavras.append(palavra.lower())
        else:
            palavras.append(palavra.capitalize())
    return ' '.join(palavras)


def abrir_csv(caminho):
    """Abre um CSV (ou o primeiro CSV de um ZIP) descobrindo codificação e separador."""
    if caminho.suffix.lower() == '.zip':
        arquivo_zip = zipfile.ZipFile(caminho)
        nomes = [n for n in arquivo_zip.namelist() if n.lower().endswith('.csv')]
        if not nomes:
            raise CommandError('O arquivo ZIP não contém nenhum CSV.')
        bruto = arquivo_zip.open(nomes[0])
    else:
        bruto = open(caminho, 'rb')

    inicio = bruto.read(65536)
    try:
        inicio.decode('utf-8')
        codificacao = 'utf-8-sig'
    except UnicodeDecodeError as erro:
        codificacao = 'utf-8-sig' if erro.start >= len(inicio) - 4 else 'latin-1'
    bruto.seek(0)

    texto = io.TextIOWrapper(bruto, encoding=codificacao, newline='')
    primeira = texto.readline()
    separador = ';' if primeira.count(';') >= primeira.count(',') else ','
    cabecalho = [c.strip().upper() for c in next(csv.reader([primeira], delimiter=separador))]
    return cabecalho, csv.reader(texto, delimiter=separador)


class Command(BaseCommand):
    help = 'Importa as ruas dos municípios do RN a partir do CNEFE do IBGE.'

    def add_arguments(self, parser):
        parser.add_argument('arquivo', nargs='?', help='CSV ou ZIP do CNEFE baixado do IBGE')

    def handle(self, *args, **opcoes):
        if opcoes['arquivo']:
            ruas = self.ler_cnefe(Path(opcoes['arquivo']))
            self.salvar_compacto(ruas)
        elif ARQUIVO_COMPACTO.exists():
            self.stdout.write(f'Usando o arquivo {ARQUIVO_COMPACTO.name}, já pronto.')
            ruas = self.ler_compacto()
        else:
            raise CommandError('Informe o caminho do arquivo do CNEFE. '
                               'Exemplo: python manage.py importar_ruas C:\\Downloads\\24_RN.zip')

        self.preencher_codigos_ibge()
        self.gravar(ruas)

    # ------------------------------------------------------------------ leitura

    def ler_cnefe(self, caminho):
        if not caminho.exists():
            raise CommandError(f'Arquivo não encontrado: {caminho}')
        self.stdout.write(f'Lendo {caminho.name}. Arquivos grandes podem levar alguns minutos...')

        cabecalho, linhas = abrir_csv(caminho)
        faltando = [c for c in COLUNAS if c not in cabecalho]
        if faltando:
            raise CommandError(f'Colunas não encontradas: {", ".join(faltando)}. '
                               f'Colunas do arquivo: {", ".join(cabecalho[:20])}')
        i_mun, i_tipo, i_titulo, i_nome = (cabecalho.index(c) for c in COLUNAS)

        ruas = set()
        for numero, linha in enumerate(linhas, start=1):
            if len(linha) <= max(i_mun, i_tipo, i_titulo, i_nome):
                continue
            partes = [linha[i_tipo].strip(), linha[i_titulo].strip(), linha[i_nome].strip()]
            nome = formatar(' '.join(p for p in partes if p))
            if normalizar(linha[i_nome]) in SEM_NOME:
                continue
            ruas.add((linha[i_mun].strip(), nome))
            if numero % 250000 == 0:
                self.stdout.write(f'  {numero:,} endereços lidos...'.replace(',', '.'))
        self.stdout.write(f'{len(ruas):,} ruas diferentes encontradas.'.replace(',', '.'))
        return ruas

    def salvar_compacto(self, ruas):
        ARQUIVO_COMPACTO.parent.mkdir(exist_ok=True)
        with open(ARQUIVO_COMPACTO, 'w', encoding='utf-8', newline='') as saida:
            escritor = csv.writer(saida, delimiter=';')
            escritor.writerow(['codigo_ibge', 'nome'])
            escritor.writerows(sorted(ruas))
        self.stdout.write(f'Lista compacta salva em {ARQUIVO_COMPACTO}.')

    def ler_compacto(self):
        with open(ARQUIVO_COMPACTO, encoding='utf-8', newline='') as entrada:
            leitor = csv.reader(entrada, delimiter=';')
            next(leitor)
            return {(codigo, nome) for codigo, nome in leitor}

    # ------------------------------------------------------------------ municípios

    def preencher_codigos_ibge(self):
        """Nosso cadastro de municípios não tinha os códigos do IBGE. Busca uma vez."""
        sem_codigo = Municipio.objects.filter(Q(codigo_ibge__isnull=True) | Q(codigo_ibge=''))
        if not sem_codigo.exists():
            return
        if ARQUIVO_MUNICIPIOS.exists():
            # Os códigos já foram buscados uma vez e estão no projeto: não precisa de internet
            self.stdout.write(f'Usando os códigos de {ARQUIVO_MUNICIPIOS.name}, já pronto.')
            with open(ARQUIVO_MUNICIPIOS, encoding='utf-8', newline='') as entrada:
                leitor = csv.reader(entrada, delimiter=';')
                next(leitor)
                dados = [{'id': codigo, 'nome': nome} for codigo, nome in leitor]
        else:
            dados = self.buscar_no_ibge()
            ARQUIVO_MUNICIPIOS.parent.mkdir(exist_ok=True)
            with open(ARQUIVO_MUNICIPIOS, 'w', encoding='utf-8', newline='') as saida:
                escritor = csv.writer(saida, delimiter=';')
                escritor.writerow(['codigo_ibge', 'nome'])
                escritor.writerows(sorted((str(m['id']), m['nome']) for m in dados))
            self.stdout.write(f'Códigos salvos em {ARQUIVO_MUNICIPIOS}. Envie esse arquivo ao '
                              'GitHub: os outros computadores não vão precisar consultar o IBGE.')

        por_nome = {chave_municipio(m['nome']): str(m['id']) for m in dados}
        nao_encontrados = []
        for municipio in sem_codigo:
            chave = chave_municipio(municipio.nome)
            codigo = por_nome.get(chave) or por_nome.get(APELIDOS_IBGE.get(chave, ''))
            if codigo:
                municipio.codigo_ibge = codigo
                municipio.save(update_fields=['codigo_ibge'])
            else:
                nao_encontrados.append(municipio.nome)
        if nao_encontrados:
            self.stdout.write(self.style.WARNING(
                'Municípios sem código (as ruas deles não serão importadas): '
                + ', '.join(nao_encontrados)))

    def buscar_no_ibge(self):
        self.stdout.write('Buscando os códigos dos municípios no IBGE...')
        # Redes de instituições costumam usar um certificado próprio, que o Windows
        # conhece mas o Python não. A biblioteca truststore faz o Python usar os
        # certificados do Windows.
        try:
            import truststore
            truststore.inject_into_ssl()
        except ImportError:
            pass
        try:
            pedido = urllib.request.Request(URL_MUNICIPIOS_RN, headers={'Accept-Encoding': 'identity'})
            with urllib.request.urlopen(pedido, timeout=30) as resposta:
                conteudo = resposta.read()
            # O servidor do IBGE às vezes responde compactado (gzip), mesmo sem pedirmos.
            # Arquivos gzip sempre começam com os bytes 1F 8B.
            if conteudo[:2] == b'\x1f\x8b':
                conteudo = gzip.decompress(conteudo)
            return json.loads(conteudo.decode('utf-8'))
        except Exception as erro:
            dica = ''
            if 'CERTIFICATE_VERIFY_FAILED' in str(erro):
                dica = (' A rede usa um certificado próprio. Rode "pip install truststore" '
                        'e tente de novo.')
            raise CommandError(f'Não foi possível consultar o IBGE.{dica} ({erro})')

    # ------------------------------------------------------------------ gravação

    def gravar(self, ruas):
        municipios = {m.codigo_ibge: m for m in Municipio.objects.exclude(codigo_ibge__isnull=True)}
        novos, vistos = [], set()
        for codigo, nome in ruas:
            municipio = municipios.get(codigo)
            if not municipio:
                continue
            busca = normalizar_logradouro(nome)
            if (municipio.pk, busca) in vistos:
                continue
            vistos.add((municipio.pk, busca))
            novos.append(Logradouro(municipio=municipio, nome=nome[:150], nome_busca=busca[:150]))

        with transaction.atomic():
            Logradouro.objects.all().delete()
            Logradouro.objects.bulk_create(novos, batch_size=2000)

        cidades = len({l.municipio_id for l in novos})
        self.stdout.write(self.style.SUCCESS(
            f'Pronto: {len(novos):,} ruas importadas em {cidades} municípios.'.replace(',', '.')))
