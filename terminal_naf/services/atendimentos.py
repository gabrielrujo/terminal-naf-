"""Regras de criação, fila e transição dos atendimentos."""

import sqlite3
from datetime import date

from ..database import get_db
from ..models import Perfil, RegraDeNegocioError, StatusAtendimento
from .catalogo import agora_iso


ATENDIMENTO_SELECT = """
    SELECT a.*, s.codigo AS servico_codigo, s.nome AS servico_nome,
           s.descricao AS servico_descricao, u.nome AS atendente_nome,
           av.nota AS avaliacao_nota
    FROM atendimentos a
    JOIN servicos s ON s.id = a.servico_id
    LEFT JOIN usuarios u ON u.id = a.atendente_id
    LEFT JOIN avaliacoes av ON av.atendimento_id = a.id
"""


def _por_id(atendimento_id):
    return get_db().execute(
        ATENDIMENTO_SELECT + " WHERE a.id = ?", (atendimento_id,)
    ).fetchone()


def obter_por_protocolo(protocolo):
    protocolo = protocolo.strip().upper()
    return get_db().execute(
        ATENDIMENTO_SELECT + " WHERE a.protocolo = ?", (protocolo,)
    ).fetchone()


def criar_atendimento(servico_id):
    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        servico = db.execute(
            "SELECT id FROM servicos WHERE id = ? AND ativo = 1", (servico_id,)
        ).fetchone()
        if servico is None:
            raise RegraDeNegocioError("O serviço selecionado não está disponível.")

        data_atual = date.today().isoformat()
        db.execute(
            """
            INSERT INTO sequencias (data, ultimo_numero) VALUES (?, 1)
            ON CONFLICT(data) DO UPDATE SET ultimo_numero = ultimo_numero + 1
            """,
            (data_atual,),
        )
        numero = db.execute(
            "SELECT ultimo_numero FROM sequencias WHERE data = ?", (data_atual,)
        ).fetchone()["ultimo_numero"]
        senha = f"A{numero:03d}"
        protocolo = f"NAF-{date.today().strftime('%Y%m%d')}-{numero:04d}"
        cursor = db.execute(
            """
            INSERT INTO atendimentos
                (senha, protocolo, servico_id, status, criado_em)
            VALUES (?, ?, ?, 'AGUARDANDO', ?)
            """,
            (senha, protocolo, servico_id, agora_iso()),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _por_id(cursor.lastrowid)


def listar_fila():
    return get_db().execute(
        ATENDIMENTO_SELECT
        + """
        WHERE a.status IN ('AGUARDANDO', 'EM_ATENDIMENTO')
        ORDER BY a.criado_em ASC, a.id ASC
        """
    ).fetchall()


def chamar_atendimento(atendimento_id, usuario):
    atendimento = _por_id(atendimento_id)
    if atendimento is None:
        raise RegraDeNegocioError("Atendimento não encontrado.")
    if atendimento["status"] != StatusAtendimento.AGUARDANDO.value:
        raise RegraDeNegocioError("Somente uma senha aguardando pode ser chamada.")
    if atendimento["atendente_id"] not in (None, usuario.id) and usuario.perfil != Perfil.ADMIN:
        raise RegraDeNegocioError("Esta senha já foi chamada por outro atendente.")

    outro = get_db().execute(
        """
        SELECT id FROM atendimentos
        WHERE atendente_id = ?
          AND id != ?
          AND (status = 'EM_ATENDIMENTO' OR (status = 'AGUARDANDO' AND chamado_em IS NOT NULL))
        """,
        (usuario.id, atendimento_id),
    ).fetchone()
    if outro:
        raise RegraDeNegocioError("Finalize a senha já chamada antes de chamar outra.")

    db = get_db()
    db.execute(
        """
        UPDATE atendimentos
        SET atendente_id = ?, chamado_em = COALESCE(chamado_em, ?)
        WHERE id = ? AND status = 'AGUARDANDO'
        """,
        (usuario.id, agora_iso(), atendimento_id),
    )
    db.commit()


def iniciar_atendimento(atendimento_id, usuario):
    atendimento = _por_id(atendimento_id)
    if atendimento is None:
        raise RegraDeNegocioError("Atendimento não encontrado.")
    if atendimento["status"] != StatusAtendimento.AGUARDANDO.value:
        raise RegraDeNegocioError("Somente uma senha aguardando pode ser iniciada.")
    if atendimento["atendente_id"] not in (None, usuario.id) and usuario.perfil != Perfil.ADMIN:
        raise RegraDeNegocioError("Esta senha pertence a outro atendente.")

    em_curso = get_db().execute(
        """
        SELECT id FROM atendimentos
        WHERE atendente_id = ? AND status = 'EM_ATENDIMENTO' AND id != ?
        """,
        (usuario.id, atendimento_id),
    ).fetchone()
    if em_curso:
        raise RegraDeNegocioError("Conclua ou cancele seu atendimento atual antes de iniciar outro.")

    db = get_db()
    cursor = db.execute(
        """
        UPDATE atendimentos
        SET status = 'EM_ATENDIMENTO', atendente_id = ?,
            chamado_em = COALESCE(chamado_em, ?), iniciado_em = ?
        WHERE id = ? AND status = 'AGUARDANDO'
        """,
        (usuario.id, agora_iso(), agora_iso(), atendimento_id),
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise RegraDeNegocioError("A senha mudou de estado. Atualize a fila.")
    db.commit()


def concluir_atendimento(atendimento_id, usuario):
    atendimento = _por_id(atendimento_id)
    if atendimento is None:
        raise RegraDeNegocioError("Atendimento não encontrado.")
    if atendimento["status"] != StatusAtendimento.EM_ATENDIMENTO.value:
        raise RegraDeNegocioError("O atendimento precisa ser iniciado antes da conclusão.")
    if atendimento["atendente_id"] != usuario.id and usuario.perfil != Perfil.ADMIN:
        raise RegraDeNegocioError("Somente o responsável ou um administrador pode concluir.")

    db = get_db()
    cursor = db.execute(
        """
        UPDATE atendimentos SET status = 'CONCLUIDO', concluido_em = ?
        WHERE id = ? AND status = 'EM_ATENDIMENTO'
        """,
        (agora_iso(), atendimento_id),
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise RegraDeNegocioError("O atendimento mudou de estado. Atualize a página.")
    db.commit()


def cancelar_atendimento(atendimento_id, usuario, motivo=""):
    atendimento = _por_id(atendimento_id)
    if atendimento is None:
        raise RegraDeNegocioError("Atendimento não encontrado.")
    if atendimento["status"] not in {
        StatusAtendimento.AGUARDANDO.value,
        StatusAtendimento.EM_ATENDIMENTO.value,
    }:
        raise RegraDeNegocioError("Este atendimento não pode mais ser cancelado.")
    if (
        atendimento["atendente_id"] is not None
        and atendimento["atendente_id"] != usuario.id
        and usuario.perfil != Perfil.ADMIN
    ):
        raise RegraDeNegocioError("Somente o responsável ou um administrador pode cancelar.")

    db = get_db()
    cursor = db.execute(
        """
        UPDATE atendimentos
        SET status = 'CANCELADO', cancelado_em = ?, motivo_cancelamento = ?
        WHERE id = ? AND status IN ('AGUARDANDO', 'EM_ATENDIMENTO')
        """,
        (agora_iso(), motivo.strip()[:200] or None, atendimento_id),
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise RegraDeNegocioError("O atendimento mudou de estado. Atualize a página.")
    db.commit()


def registrar_avaliacao(protocolo, nota):
    try:
        nota = int(nota)
    except (TypeError, ValueError) as error:
        raise RegraDeNegocioError("Escolha uma nota de 1 a 5.") from error
    if nota not in range(1, 6):
        raise RegraDeNegocioError("Escolha uma nota de 1 a 5.")

    atendimento = obter_por_protocolo(protocolo)
    if atendimento is None:
        raise RegraDeNegocioError("Protocolo não encontrado.")
    if atendimento["status"] != StatusAtendimento.CONCLUIDO.value:
        raise RegraDeNegocioError("A avaliação só é liberada após a conclusão.")
    if atendimento["avaliacao_nota"] is not None:
        raise RegraDeNegocioError("Este atendimento já foi avaliado.")

    db = get_db()
    try:
        db.execute(
            "INSERT INTO avaliacoes (atendimento_id, nota, criado_em) VALUES (?, ?, ?)",
            (atendimento["id"], nota, agora_iso()),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        db.rollback()
        raise RegraDeNegocioError("Este atendimento já foi avaliado.") from error


def listar_atendimentos(limite=200, atendente_id=None):
    params = []
    where = ""
    if atendente_id is not None:
        where = " WHERE a.atendente_id = ?"
        params.append(atendente_id)
    return get_db().execute(
        ATENDIMENTO_SELECT + where + " ORDER BY a.criado_em DESC LIMIT ?",
        (*params, limite),
    ).fetchall()
