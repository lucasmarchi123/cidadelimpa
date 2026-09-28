import unicodedata
import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

TAMANHO_MAXIMO_FOTO = 5 * 1024 * 1024   # 5 MB
FORMATOS_ACEITOS = {'JPEG', 'PNG', 'WEBP'}
LADO_MAXIMO_FOTO = 1920                 # pixels

ABREVIACOES = {'r': 'rua', 'av': 'avenida', 'tv': 'travessa', 'trav': 'travessa'}


def normalizar(texto):
    """Deixa o texto num formato padrão para comparação:
    sem acentos, minúsculo e com espaços simples.
    'São  José' e 'sao jose' viram o mesmo texto."""
    texto = unicodedata.normalize('NFKD', texto or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return ' '.join(texto.casefold().split())


def normalizar_logradouro(texto):
    """Além de normalizar, troca abreviações: 'R. das Flores' vira 'rua das flores'."""
    palavras = normalizar(texto).replace('.', ' ').split()
    if palavras and palavras[0] in ABREVIACOES:
        palavras[0] = ABREVIACOES[palavras[0]]
    return ' '.join(palavras)


def processar_foto(arquivo):
    """Confere se o arquivo é mesmo uma imagem e gera uma cópia limpa dela.

    A cópia é redesenhada do zero pelo Pillow. Isso descarta qualquer coisa
    escondida no arquivo original, remove os metadados (como a localização GPS
    que o celular grava na foto) e reduz o tamanho para economizar espaço.
    """
    if arquivo.size > TAMANHO_MAXIMO_FOTO:
        raise ValidationError('A foto deve ter no máximo 5 MB.')

    try:
        imagem = Image.open(arquivo)
        formato = imagem.format
        imagem.verify()                      # confere se o arquivo não está corrompido
        arquivo.seek(0)
        imagem = Image.open(arquivo)         # depois do verify é preciso abrir de novo
        imagem = ImageOps.exif_transpose(imagem)  # mantém a foto em pé
        imagem = imagem.convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError('O arquivo enviado não é uma imagem válida.')

    if formato not in FORMATOS_ACEITOS:
        raise ValidationError('Envie uma foto nos formatos JPG, PNG ou WEBP.')

    imagem.thumbnail((LADO_MAXIMO_FOTO, LADO_MAXIMO_FOTO))
    saida = BytesIO()
    imagem.save(saida, format='JPEG', quality=85, optimize=True)

    # Nome aleatório: não expõe o nome original do arquivo
    # e impede que uma foto substitua outra.
    return ContentFile(saida.getvalue(), name=f'{uuid.uuid4().hex}.jpg')
