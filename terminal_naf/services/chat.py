"""Mensagens persistentes trocadas durante um atendimento."""

import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from ..database import get_db
from ..models import RegraDeNegocioError, StatusAtendimento
from .catalogo import agora_iso


ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_MAXIMO = 1000

ATENDIMENTO_CHAT_SELECT = """
    SELECT a.id, a.protocolo, a.senha, a.status, a.atendente_id,
           s.nome AS servico_nome, u.nome AS atendente_nome
    FROM atendimentos a
    JOIN servicos s ON s.id = a.servico_id
    LEFT JOIN usuarios u ON u.id = a.atendente_id
"""

MENSAGEM_SELECT = """
    SELECT m.id, m.atendimento_id, m.autor_tipo, m.autor_usuario_id,
           CASE
               WHEN m.autor_tipo = 'CIDADAO' THEN 'Cidadão'
               ELSE COALESCE(u.nome, 'Atendente')
           END AS autor_nome,
           m.conteudo, m.criado_em, m.lido_em
    FROM mensagens m
    LEFT JOIN usuarios u ON u.id = m.autor_usuario_id
"""


def gerar_codigo_acesso():
    """Gera um código curto sem caracteres visualmente ambíguos."""
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(8))


def hash_codigo_acesso(codigo):
    return generate_password_hash(codigo)


def obter_atendimento(atendimento_id):
    return get_db().execute(
        ATENDIMENTO_CHAT_SELECT + " WHERE a.id = ?", (atendimento_id,)
    ).fetchone()


def validar_codigo_acesso(protocolo, codigo):
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None
    registro = get_db().execute(
        ATENDIMENTO_CHAT_SELECT
        + """
        JOIN chat_acessos ca ON ca.atendimento_id = a.id
        WHERE a.protocolo = ?
        """,
        ((protocolo or "").strip().upper(),),
    ).fetchone()
    if registro is None:
        return None
    codigo_hash = get_db().execute(
        "SELECT codigo_hash FROM chat_acessos WHERE atendimento_id = ?",
        (registro["id"],),
    ).fetchone()["codigo_hash"]
    return registro if check_password_hash(codigo_hash, codigo) else None


def _mensagem_para_dict(registro):
    return {
        "id": registro["id"],
        "autor_tipo": registro["autor_tipo"],
        "autor_nome": registro["autor_nome"],
        "conteudo": registro["conteudo"],
        "criado_em": registro["criado_em"],
        "lido_em": registro["lido_em"],
    }


def listar_mensagens(atendimento_id, leitor_tipo, depois_de=0):
    if leitor_tipo not in {"CIDADAO", "ATENDENTE"}:
        raise ValueError("Tipo de leitor inválido.")
    try:
        depois_de = max(0, int(depois_de))
    except (TypeError, ValueError):
        depois_de = 0

    autor_oposto = "ATENDENTE" if leitor_tipo == "CIDADAO" else "CIDADAO"
    db = get_db()
    db.execute(
        """
        UPDATE mensagens SET lido_em = ?
        WHERE atendimento_id = ? AND autor_tipo = ? AND lido_em IS NULL
        """,
        (agora_iso(), atendimento_id, autor_oposto),
    )
    db.commit()
    registros = db.execute(
        MENSAGEM_SELECT
        + """
        WHERE m.atendimento_id = ? AND m.id > ?
        ORDER BY m.id ASC
        LIMIT 200
        """,
        (atendimento_id, depois_de),
    ).fetchall()
    return [_mensagem_para_dict(registro) for registro in registros]


def ultima_mensagem_lida(atendimento_id, autor_tipo):
    registro = get_db().execute(
        """
        SELECT COALESCE(MAX(id), 0) AS mensagem_id
        FROM mensagens
        WHERE atendimento_id = ? AND autor_tipo = ? AND lido_em IS NOT NULL
        """,
        (atendimento_id, autor_tipo),
    ).fetchone()
    return registro["mensagem_id"]


def enviar_mensagem(atendimento_id, autor_tipo, conteudo, autor_usuario_id=None):
    if autor_tipo not in {"CIDADAO", "ATENDENTE"}:
        raise RegraDeNegocioError("Autor da mensagem inválido.")
    if autor_tipo == "CIDADAO":
        autor_usuario_id = None
    elif autor_usuario_id is None:
        raise RegraDeNegocioError("O atendente precisa estar identificado.")

    conteudo = (conteudo or "").strip()
    if not conteudo:
        raise RegraDeNegocioError("Digite uma mensagem antes de enviar.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise RegraDeNegocioError(
            f"A mensagem deve ter no máximo {TAMANHO_MAXIMO} caracteres."
        )

    db = get_db()
    try:
        # O bloqueio de escrita torna a checagem de estado e a inserção atômicas.
        db.execute("BEGIN IMMEDIATE")
        atendimento = db.execute(
            "SELECT status FROM atendimentos WHERE id = ?", (atendimento_id,)
        ).fetchone()
        if atendimento is None:
            raise RegraDeNegocioError("Atendimento não encontrado.")
        if atendimento["status"] != StatusAtendimento.EM_ATENDIMENTO.value:
            raise RegraDeNegocioError(
                "Novas mensagens são permitidas apenas durante o atendimento."
            )
        cursor = db.execute(
            """
            INSERT INTO mensagens
                (atendimento_id, autor_tipo, autor_usuario_id, conteudo, criado_em)
            VALUES (?, ?, ?, ?, ?)
            """,
            (atendimento_id, autor_tipo, autor_usuario_id, conteudo, agora_iso()),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    registro = db.execute(
        MENSAGEM_SELECT + " WHERE m.id = ?", (cursor.lastrowid,)
    ).fetchone()
    return _mensagem_para_dict(registro)
