from denuncias.models import LogAdmin


def registrar_log(request, acao, entidade='', id_entidade=None, descricao='', usuario=None):
    """Grava uma ação administrativa no log, com quem fez, quando e de qual IP."""
    LogAdmin.objects.create(
        usuario=usuario or request.user,
        acao=acao,
        entidade=entidade,
        id_entidade=id_entidade,
        descricao=descricao[:255],
        # REMOTE_ADDR é o IP da conexão. Não usamos cabeçalhos enviados
        # pelo navegador, porque qualquer um pode falsificá-los.
        endereco_ip=request.META.get('REMOTE_ADDR') or None,
    )


def pode_alterar_usuario(ator, alvo):
    """Regras para bloquear ou desbloquear uma conta."""
    if alvo.pk == ator.pk:
        return False            # ninguém bloqueia a própria conta
    if alvo.is_superuser:
        return False            # o superusuário não é alterado pelo painel
    if alvo.is_staff and not ator.is_superuser:
        return False            # só o superusuário altera administradores
    return True


def formatar_duracao(segundos):
    horas = segundos / 3600
    if horas < 1:
        return 'menos de 1 hora'
    if horas < 24:
        h = round(horas)
        return f'{h} hora' + ('s' if h != 1 else '')
    texto = f'{horas / 24:.1f}'.replace('.', ',')
    if texto.endswith(',0'):
        texto = texto[:-2]
    return f'{texto} dia' + ('' if texto == '1' else 's')
