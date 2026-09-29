"""Limite de tentativas de login.

Guarda na memória do servidor (cache) quantas vezes um login falhou.
Depois de muitas falhas, novas tentativas ficam bloqueadas por 15 minutos,
mesmo com a senha certa. Isso torna inviável testar milhares de senhas.
"""
import logging

from django.core.cache import cache

logger = logging.getLogger('cidadelimpa.seguranca')

LIMITE_POR_USUARIO = 5       # erros com o mesmo nome de usuário, vindos do mesmo IP
LIMITE_POR_IP = 20           # erros de um mesmo IP, com qualquer nome de usuário
BLOQUEIO_SEGUNDOS = 15 * 60  # 15 minutos


def _chaves(username, ip):
    nome = (username or '').strip().lower()
    return f'login:usuario:{ip}:{nome}', f'login:ip:{ip}'


def esta_bloqueado(username, ip):
    chave_usuario, chave_ip = _chaves(username, ip)
    return (cache.get(chave_usuario, 0) >= LIMITE_POR_USUARIO
            or cache.get(chave_ip, 0) >= LIMITE_POR_IP)


def registrar_falha(username, ip):
    chave_usuario, chave_ip = _chaves(username, ip)
    totais = []
    for chave in (chave_usuario, chave_ip):
        cache.add(chave, 0, BLOQUEIO_SEGUNDOS)  # cria o contador se ainda não existir
        try:
            totais.append(cache.incr(chave))
        except ValueError:                      # o contador expirou entre as duas linhas
            cache.set(chave, 1, BLOQUEIO_SEGUNDOS)
            totais.append(1)

    if totais[0] == LIMITE_POR_USUARIO or totais[1] == LIMITE_POR_IP:
        logger.warning('Login bloqueado por 15 minutos: usuário "%s", IP %s', username, ip)


def limpar_falhas(username, ip):
    """Depois de um login certo, zera o contador daquele usuário.
    O contador do IP continua, para ninguém usar uma conta própria
    para "zerar" as tentativas contra outras contas."""
    chave_usuario, _ = _chaves(username, ip)
    cache.delete(chave_usuario)
