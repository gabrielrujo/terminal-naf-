"""Catálogo inicial de serviços e materiais públicos."""

from datetime import datetime

from ..database import get_db


SERVICOS_INICIAIS = (
    ("MEI", "MEI", "Abertura, baixa e regularização de Microempreendedor Individual."),
    ("CPF", "CPF", "Inscrição, atualização e regularização cadastral do CPF."),
    ("IRPF", "Imposto de Renda", "Orientações sobre declaração de Imposto de Renda."),
    ("DAS", "DAS", "Emissão, consulta e parcelamento de guias do Simples Nacional."),
    ("REG", "Regularização", "Apoio na consulta e regularização de pendências fiscais."),
    ("OUT", "Outros", "Dúvidas contábeis e fiscais não contempladas nas opções anteriores."),
)

MATERIAIS = (
    {"categoria": "MEI", "titulo": "Primeiros passos para abrir ou regularizar um MEI"},
    {"categoria": "CPF", "titulo": "Como consultar a situação cadastral do CPF"},
    {"categoria": "IRPF", "titulo": "Documentos básicos para a declaração de Imposto de Renda"},
    {"categoria": "DAS", "titulo": "Orientações para emissão da guia DAS"},
    {"categoria": "Regularização", "titulo": "Como se preparar para regularizar pendências fiscais"},
)


def agora_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def garantir_servicos_iniciais():
    db = get_db()
    for codigo, nome, descricao in SERVICOS_INICIAIS:
        db.execute(
            """
            INSERT INTO servicos (codigo, nome, descricao, ativo, criado_em)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(codigo) DO NOTHING
            """,
            (codigo, nome, descricao, agora_iso()),
        )
    db.commit()


def listar_servicos(apenas_ativos=True):
    sql = "SELECT * FROM servicos"
    if apenas_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY id"
    return get_db().execute(sql).fetchall()
