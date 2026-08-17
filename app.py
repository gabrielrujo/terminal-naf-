"""Terminal NAF — terminal, fila de atendimento e painel de coordenação."""

import os
import random
import sqlite3
import string
from datetime import date, datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "naf_terminal.db"

app = Flask(__name__)
app.config.from_mapping(
    DATABASE=DB_PATH,
    SECRET_KEY=os.environ.get("NAF_SECRET_KEY", "desenvolvimento-troque-em-producao"),
)

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


def get_db():
    """Abre uma conexão por requisição e a guarda no contexto do Flask."""
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Cria o banco e migra instalações da primeira versão do protótipo."""
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            login TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            perfil TEXT NOT NULL CHECK (perfil IN ('atendente', 'coordenador')),
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS atendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocolo TEXT UNIQUE NOT NULL,
            servico_codigo TEXT NOT NULL,
            servico_nome TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            resolvido INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'aguardando',
            atendente_id INTEGER REFERENCES usuarios(id),
            iniciado_em TEXT,
            concluido_em TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocolo TEXT NOT NULL,
            nota INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),
            criado_em TEXT NOT NULL
        )
        """
    )

    # Migração simples para o banco criado pela versão anterior.
    colunas = {row[1] for row in conn.execute("PRAGMA table_info(atendimentos)")}
    status_foi_adicionado = "status" not in colunas
    migracoes = {
        "status": "ALTER TABLE atendimentos ADD COLUMN status TEXT NOT NULL DEFAULT 'aguardando'",
        "atendente_id": "ALTER TABLE atendimentos ADD COLUMN atendente_id INTEGER REFERENCES usuarios(id)",
        "iniciado_em": "ALTER TABLE atendimentos ADD COLUMN iniciado_em TEXT",
        "concluido_em": "ALTER TABLE atendimentos ADD COLUMN concluido_em TEXT",
    }
    for coluna, comando in migracoes.items():
        if coluna not in colunas:
            conn.execute(comando)

    if status_foi_adicionado:
        conn.execute(
            """
            UPDATE atendimentos
            SET status = CASE WHEN resolvido = 1 THEN 'concluido' ELSE 'aguardando' END,
                concluido_em = CASE WHEN resolvido = 1 THEN criado_em ELSE NULL END
            """
        )

    # O SQLite não permite alterar um DEFAULT diretamente. Bancos da v1 são
    # reconstruídos uma única vez para remover o antigo DEFAULT 1.
    info_resolvido = next(
        row for row in conn.execute("PRAGMA table_info(atendimentos)") if row[1] == "resolvido"
    )
    if str(info_resolvido[4]).strip("'\"") != "0":
        conn.execute("ALTER TABLE atendimentos RENAME TO atendimentos_v1")
        conn.execute(
            """
            CREATE TABLE atendimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                protocolo TEXT UNIQUE NOT NULL,
                servico_codigo TEXT NOT NULL,
                servico_nome TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                resolvido INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'aguardando',
                atendente_id INTEGER REFERENCES usuarios(id),
                iniciado_em TEXT,
                concluido_em TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO atendimentos
                (id, protocolo, servico_codigo, servico_nome, criado_em, resolvido,
                 status, atendente_id, iniciado_em, concluido_em)
            SELECT id, protocolo, servico_codigo, servico_nome, criado_em, resolvido,
                   status, atendente_id, iniciado_em, concluido_em
            FROM atendimentos_v1
            """
        )
        conn.execute("DROP TABLE atendimentos_v1")

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS avaliacao_por_protocolo ON avaliacoes(protocolo)"
    )
    conn.commit()
    conn.close()


def agora_iso():
    return datetime.now().isoformat(timespec="seconds")


def gerar_protocolo():
    hoje = date.today().strftime("%Y%m%d")
    sufixo = "".join(random.choices(string.digits, k=4))
    return f"NAF-{hoje}-{sufixo}"


@app.before_request
def carregar_usuario():
    usuario_id = session.get("usuario_id")
    g.usuario = None
    if usuario_id is not None:
        g.usuario = get_db().execute(
            "SELECT id, nome, login, perfil, ativo FROM usuarios WHERE id = ?",
            (usuario_id,),
        ).fetchone()
        if g.usuario is None or not g.usuario["ativo"]:
            session.clear()
            g.usuario = None


def login_obrigatorio(view):
    @wraps(view)
    def protegida(*args, **kwargs):
        if g.usuario is None:
            flash("Entre com seu usuário para acessar essa área.", "erro")
            return redirect(url_for("login", proximo=request.path))
        return view(*args, **kwargs)

    return protegida


def coordenador_obrigatorio(view):
    @wraps(view)
    @login_obrigatorio
    def protegida(*args, **kwargs):
        if g.usuario["perfil"] != "coordenador":
            flash("Esta área é exclusiva da coordenação.", "erro")
            return redirect(url_for("fila"))
        return view(*args, **kwargs)

    return protegida


# ---------------------------------------------------------------------------
# Acesso da equipe
# ---------------------------------------------------------------------------


@app.route("/configuracao-inicial", methods=["GET", "POST"])
def configuracao_inicial():
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0:
        return redirect(url_for("login"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        login_usuario = request.form.get("login", "").strip().lower()
        senha = request.form.get("senha", "")
        if not nome or not login_usuario or len(senha) < 6:
            flash("Preencha todos os campos e use uma senha com pelo menos 6 caracteres.", "erro")
        else:
            cursor = db.execute(
                """
                INSERT INTO usuarios (nome, login, senha_hash, perfil, criado_em)
                VALUES (?, ?, ?, 'coordenador', ?)
                """,
                (nome, login_usuario, generate_password_hash(senha), agora_iso()),
            )
            db.commit()
            session.clear()
            session["usuario_id"] = cursor.lastrowid
            flash("Coordenador criado. Agora você já pode cadastrar atendentes.", "sucesso")
            return redirect(url_for("fila"))

    return render_template("configuracao_inicial.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
        return redirect(url_for("configuracao_inicial"))

    if request.method == "POST":
        login_usuario = request.form.get("login", "").strip().lower()
        senha = request.form.get("senha", "")
        usuario = db.execute(
            "SELECT * FROM usuarios WHERE login = ? AND ativo = 1", (login_usuario,)
        ).fetchone()
        if usuario is None or not check_password_hash(usuario["senha_hash"], senha):
            flash("Usuário ou senha inválidos.", "erro")
        else:
            session.clear()
            session["usuario_id"] = usuario["id"]
            return redirect(url_for("fila"))

    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/usuarios", methods=["GET", "POST"])
@coordenador_obrigatorio
def usuarios():
    db = get_db()
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        login_usuario = request.form.get("login", "").strip().lower()
        senha = request.form.get("senha", "")
        perfil = request.form.get("perfil", "atendente")
        if not nome or not login_usuario or len(senha) < 6:
            flash("Preencha os campos e use uma senha com pelo menos 6 caracteres.", "erro")
        elif perfil not in {"atendente", "coordenador"}:
            flash("Perfil inválido.", "erro")
        else:
            try:
                db.execute(
                    """
                    INSERT INTO usuarios (nome, login, senha_hash, perfil, criado_em)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (nome, login_usuario, generate_password_hash(senha), perfil, agora_iso()),
                )
                db.commit()
                flash("Usuário cadastrado.", "sucesso")
                return redirect(url_for("usuarios"))
            except sqlite3.IntegrityError:
                flash("Esse login já está em uso.", "erro")

    lista = db.execute(
        "SELECT id, nome, login, perfil, ativo, criado_em FROM usuarios ORDER BY nome"
    ).fetchall()
    return render_template("usuarios.html", usuarios=lista)


@app.post("/usuarios/<int:usuario_id>/alternar")
@coordenador_obrigatorio
def alternar_usuario(usuario_id):
    if usuario_id == g.usuario["id"]:
        flash("Você não pode desativar o próprio usuário.", "erro")
        return redirect(url_for("usuarios"))
    db = get_db()
    db.execute(
        "UPDATE usuarios SET ativo = CASE ativo WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
        (usuario_id,),
    )
    db.commit()
    flash("Situação do usuário atualizada.", "sucesso")
    return redirect(url_for("usuarios"))


# ---------------------------------------------------------------------------
# Área do cidadão
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
            flash("Escolha um serviço válido.", "erro")
            return redirect(url_for("atendimento"))

        db = get_db()
        # A escolha cria uma senha na fila; ainda não é atendimento concluído.
        for _ in range(5):
            protocolo = gerar_protocolo()
            try:
                db.execute(
                    """
                    INSERT INTO atendimentos
                        (protocolo, servico_codigo, servico_nome, criado_em, resolvido, status)
                    VALUES (?, ?, ?, ?, 0, 'aguardando')
                    """,
                    (protocolo, servico["codigo"], servico["nome"], agora_iso()),
                )
                db.commit()
                return redirect(url_for("confirmacao", protocolo=protocolo))
            except sqlite3.IntegrityError:
                continue
        flash("Não foi possível gerar o protocolo. Tente novamente.", "erro")
        return redirect(url_for("atendimento"))

    return render_template("atendimento.html", servicos=SERVICOS)


@app.route("/confirmacao/<protocolo>")
def confirmacao(protocolo):
    atendimento_registrado = get_db().execute(
        "SELECT * FROM atendimentos WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if atendimento_registrado is None:
        return redirect(url_for("index"))
    return render_template("confirmacao.html", atendimento=atendimento_registrado)


@app.route("/informacoes")
def informacoes():
    return render_template("informacoes.html", servicos=SERVICOS)


@app.route("/materiais")
def materiais():
    return render_template("materiais.html", materiais=MATERIAIS)


@app.route("/avaliacao/<protocolo>", methods=["GET", "POST"])
def avaliacao(protocolo):
    db = get_db()
    atendimento_registrado = db.execute(
        "SELECT * FROM atendimentos WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if atendimento_registrado is None:
        flash("Protocolo não encontrado.", "erro")
        return redirect(url_for("index"))
    if atendimento_registrado["status"] != "concluido":
        flash("A avaliação é liberada depois da conclusão do atendimento.", "erro")
        return redirect(url_for("confirmacao", protocolo=protocolo))

    existente = db.execute(
        "SELECT nota FROM avaliacoes WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if request.method == "POST" and existente is None:
        try:
            nota = int(request.form.get("nota", 0))
        except ValueError:
            nota = 0
        if nota not in range(1, 6):
            flash("Escolha uma nota de 1 a 5.", "erro")
        else:
            db.execute(
                "INSERT INTO avaliacoes (protocolo, nota, criado_em) VALUES (?, ?, ?)",
                (protocolo, nota, agora_iso()),
            )
            db.commit()
            return render_template("avaliacao.html", protocolo=protocolo, enviado=True)

    return render_template(
        "avaliacao.html", protocolo=protocolo, enviado=existente is not None
    )


# ---------------------------------------------------------------------------
# Fila, atendimento e coordenação
# ---------------------------------------------------------------------------


@app.route("/fila")
@login_obrigatorio
def fila():
    registros = get_db().execute(
        """
        SELECT a.*, u.nome AS atendente_nome
        FROM atendimentos a
        LEFT JOIN usuarios u ON u.id = a.atendente_id
        WHERE a.status IN ('aguardando', 'em_atendimento')
        ORDER BY CASE a.status WHEN 'em_atendimento' THEN 0 ELSE 1 END, a.criado_em
        """
    ).fetchall()
    return render_template("fila.html", atendimentos=registros)


@app.post("/atendimentos/<int:atendimento_id>/iniciar")
@login_obrigatorio
def iniciar_atendimento(atendimento_id):
    db = get_db()
    cursor = db.execute(
        """
        UPDATE atendimentos
        SET status = 'em_atendimento', atendente_id = ?, iniciado_em = ?
        WHERE id = ? AND status = 'aguardando'
        """,
        (g.usuario["id"], agora_iso(), atendimento_id),
    )
    db.commit()
    flash(
        "Atendimento iniciado." if cursor.rowcount else "Essa senha não está mais aguardando.",
        "sucesso" if cursor.rowcount else "erro",
    )
    return redirect(url_for("fila"))


@app.post("/atendimentos/<int:atendimento_id>/concluir")
@login_obrigatorio
def concluir_atendimento(atendimento_id):
    db = get_db()
    registro = db.execute(
        "SELECT * FROM atendimentos WHERE id = ?", (atendimento_id,)
    ).fetchone()
    if registro is None or registro["status"] != "em_atendimento":
        flash("Esse atendimento não está em andamento.", "erro")
        return redirect(url_for("fila"))
    if registro["atendente_id"] != g.usuario["id"] and g.usuario["perfil"] != "coordenador":
        flash("Somente o atendente responsável ou a coordenação pode concluir.", "erro")
        return redirect(url_for("fila"))

    db.execute(
        """
        UPDATE atendimentos
        SET status = 'concluido', resolvido = 1, concluido_em = ?
        WHERE id = ?
        """,
        (agora_iso(), atendimento_id),
    )
    db.commit()
    flash("Atendimento concluído. A avaliação já está liberada.", "sucesso")
    return redirect(url_for("avaliacao", protocolo=registro["protocolo"]))


@app.route("/dashboard")
@coordenador_obrigatorio
def dashboard():
    db = get_db()
    totais = db.execute(
        """
        SELECT
            COUNT(*) AS solicitados,
            SUM(CASE WHEN status = 'aguardando' THEN 1 ELSE 0 END) AS aguardando,
            SUM(CASE WHEN status = 'em_atendimento' THEN 1 ELSE 0 END) AS em_atendimento,
            SUM(CASE WHEN status = 'concluido' THEN 1 ELSE 0 END) AS concluidos
        FROM atendimentos
        """
    ).fetchone()
    por_servico = db.execute(
        """
        SELECT servico_nome, COUNT(*) AS n
        FROM atendimentos
        WHERE status = 'concluido'
        GROUP BY servico_nome
        ORDER BY n DESC
        """
    ).fetchall()
    solicitados = totais["solicitados"] or 0
    concluidos = totais["concluidos"] or 0
    taxa_resolucao = round((concluidos / solicitados) * 100, 1) if solicitados else 0.0
    media_avaliacao = db.execute(
        "SELECT AVG(nota) AS media, COUNT(*) AS n FROM avaliacoes"
    ).fetchone()

    return render_template(
        "dashboard.html",
        totais=totais,
        por_servico=por_servico,
        taxa_resolucao=taxa_resolucao,
        media_nota=round(media_avaliacao["media"], 1) if media_avaliacao["media"] else None,
        n_avaliacoes=media_avaliacao["n"],
    )


@app.route("/api/stats")
@coordenador_obrigatorio
def api_stats():
    por_servico = get_db().execute(
        """
        SELECT servico_nome, COUNT(*) AS n
        FROM atendimentos
        WHERE status = 'concluido'
        GROUP BY servico_nome
        """
    ).fetchall()
    return jsonify([dict(row) for row in por_servico])


# Garante que a aplicação também funcione via `flask --app app run`.
with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
