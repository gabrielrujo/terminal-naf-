"""
Terminal NAF — protótipo de terminal de suporte tecnológico
Rodando localmente no Orange Pi 5 (Linux), pensado para tela touch em modo kiosk.

Como rodar:
    pip install flask
    python app.py
Depois abra o Chromium em modo kiosk apontando para http://localhost:5000
    chromium-browser --kiosk http://localhost:5000
"""

import sqlite3
import random
import string
from datetime import datetime, date
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, jsonify, g

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "naf_terminal.db"

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Catálogo de serviços — isso viraria uma base de conhecimento maior depois
# (ver seção "Próximos passos" no README para a evolução com IA local / NPU)
# ---------------------------------------------------------------------------
SERVICOS = [
    {"codigo": "mei", "nome": "MEI", "descricao": "Abertura, baixa e regularização de MEI"},
    {"codigo": "cpf", "nome": "CPF", "descricao": "Cadastro, regularização e atualização de CPF"},
    {"codigo": "irpf", "nome": "Imposto de Renda", "descricao": "Declaração e orientação de IRPF"},
    {"codigo": "das", "nome": "DAS", "descricao": "Emissão e parcelamento de guias DAS"},
    {"codigo": "regularizacao", "nome": "Regularização", "descricao": "Pendências fiscais em geral"},
    {"codigo": "outros", "nome": "Outros", "descricao": "Dúvidas gerais não listadas acima"},
]

MATERIAIS = [
    {"titulo": "Como abrir um MEI passo a passo", "categoria": "MEI"},
    {"titulo": "O que é e para que serve o CPF", "categoria": "CPF"},
    {"titulo": "Quem precisa declarar Imposto de Renda em 2026", "categoria": "IRPF"},
    {"titulo": "Como emitir a guia do DAS pelo celular", "categoria": "DAS"},
    {"titulo": "Passo a passo para regularizar pendências no CPF/CNPJ", "categoria": "Regularização"},
]

# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS atendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocolo TEXT UNIQUE NOT NULL,
            servico_codigo TEXT NOT NULL,
            servico_nome TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            resolvido INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocolo TEXT NOT NULL,
            nota INTEGER NOT NULL,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def gerar_protocolo():
    hoje = date.today().strftime("%Y%m%d")
    sufixo = "".join(random.choices(string.digits, k=4))
    return f"NAF-{hoje}-{sufixo}"


# ---------------------------------------------------------------------------
# Rotas — telas do terminal
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/atendimento", methods=["GET", "POST"])
def atendimento():
    if request.method == "POST":
        codigo = request.form.get("servico")
        servico = next((s for s in SERVICOS if s["codigo"] == codigo), None)
        if not servico:
            return redirect(url_for("atendimento"))

        protocolo = gerar_protocolo()
        db = get_db()
        db.execute(
            "INSERT INTO atendimentos (protocolo, servico_codigo, servico_nome, criado_em) VALUES (?, ?, ?, ?)",
            (protocolo, servico["codigo"], servico["nome"], datetime.now().isoformat()),
        )
        db.commit()
        return redirect(url_for("confirmacao", protocolo=protocolo))

    return render_template("atendimento.html", servicos=SERVICOS)


@app.route("/confirmacao/<protocolo>")
def confirmacao(protocolo):
    db = get_db()
    row = db.execute(
        "SELECT * FROM atendimentos WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if row is None:
        return redirect(url_for("index"))
    return render_template("confirmacao.html", atendimento=row)


@app.route("/informacoes")
def informacoes():
    return render_template("informacoes.html", servicos=SERVICOS)


@app.route("/materiais")
def materiais():
    return render_template("materiais.html", materiais=MATERIAIS)


@app.route("/avaliacao/<protocolo>", methods=["GET", "POST"])
def avaliacao(protocolo):
    if request.method == "POST":
        nota = int(request.form.get("nota", 0))
        db = get_db()
        db.execute(
            "INSERT INTO avaliacoes (protocolo, nota, criado_em) VALUES (?, ?, ?)",
            (protocolo, nota, datetime.now().isoformat()),
        )
        db.commit()
        return render_template("avaliacao.html", protocolo=protocolo, enviado=True)

    return render_template("avaliacao.html", protocolo=protocolo, enviado=False)


@app.route("/dashboard")
def dashboard():
    db = get_db()

    total = db.execute("SELECT COUNT(*) AS n FROM atendimentos").fetchone()["n"]

    por_servico = db.execute(
        """
        SELECT servico_nome, COUNT(*) AS n
        FROM atendimentos
        GROUP BY servico_nome
        ORDER BY n DESC
        """
    ).fetchall()

    resolvidos = db.execute(
        "SELECT COUNT(*) AS n FROM atendimentos WHERE resolvido = 1"
    ).fetchone()["n"]
    taxa_resolucao = round((resolvidos / total) * 100, 1) if total else 0.0

    media_avaliacao = db.execute(
        "SELECT AVG(nota) AS media, COUNT(*) AS n FROM avaliacoes"
    ).fetchone()

    return render_template(
        "dashboard.html",
        total=total,
        por_servico=por_servico,
        taxa_resolucao=taxa_resolucao,
        media_nota=round(media_avaliacao["media"], 1) if media_avaliacao["media"] else None,
        n_avaliacoes=media_avaliacao["n"],
    )


@app.route("/api/stats")
def api_stats():
    """Endpoint JSON simples — útil se o coordenador quiser consumir os dados
    de outro lugar (ex.: um painel web separado)."""
    db = get_db()
    por_servico = db.execute(
        "SELECT servico_nome, COUNT(*) AS n FROM atendimentos GROUP BY servico_nome"
    ).fetchall()
    return jsonify([dict(row) for row in por_servico])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
