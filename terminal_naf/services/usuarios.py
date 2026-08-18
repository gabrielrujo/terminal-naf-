"""Operações relacionadas a usuários internos."""

import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from ..database import get_db
from ..models import Perfil, RegraDeNegocioError
from .catalogo import agora_iso


def autenticar(login, senha):
    row = get_db().execute(
        "SELECT * FROM usuarios WHERE login = ? AND ativo = 1",
        (login.strip().lower(),),
    ).fetchone()
    if row is None or not check_password_hash(row["senha_hash"], senha):
        return None
    return row


def criar_usuario(nome, login, senha, perfil):
    nome = nome.strip()
    login = login.strip().lower()
    perfil = perfil.strip().upper()
    if not nome or not login:
        raise RegraDeNegocioError("Informe nome e usuário.")
    if len(senha) < 8:
        raise RegraDeNegocioError("A senha deve possuir pelo menos 8 caracteres.")
    if perfil not in {Perfil.ATENDENTE.value, Perfil.ADMIN.value}:
        raise RegraDeNegocioError("Perfil inválido.")

    db = get_db()
    try:
        cursor = db.execute(
            """
            INSERT INTO usuarios (nome, login, senha_hash, perfil, ativo, criado_em)
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (nome, login, generate_password_hash(senha), perfil, agora_iso()),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        db.rollback()
        raise RegraDeNegocioError("Esse usuário já está cadastrado.") from error
    return cursor.lastrowid


def seed_demo_data(admin_password="admin123", atendente_password="atendente123"):
    db = get_db()
    demonstracao = (
        ("Administrador NAF", "admin", admin_password, Perfil.ADMIN.value),
        ("Atendente Demonstração", "atendente", atendente_password, Perfil.ATENDENTE.value),
    )
    for nome, login, senha, perfil in demonstracao:
        db.execute(
            """
            INSERT INTO usuarios (nome, login, senha_hash, perfil, ativo, criado_em)
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(login) DO UPDATE SET
                nome = excluded.nome,
                senha_hash = excluded.senha_hash,
                perfil = excluded.perfil,
                ativo = 1
            """,
            (nome, login, generate_password_hash(senha), perfil, agora_iso()),
        )
    db.commit()


def listar_usuarios():
    return get_db().execute(
        "SELECT id, nome, login, perfil, ativo, criado_em FROM usuarios ORDER BY nome"
    ).fetchall()


def alternar_usuario(usuario_id, usuario_atual_id):
    if usuario_id == usuario_atual_id:
        raise RegraDeNegocioError("Você não pode desativar o próprio usuário.")
    db = get_db()
    cursor = db.execute(
        "UPDATE usuarios SET ativo = CASE ativo WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
        (usuario_id,),
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise RegraDeNegocioError("Usuário não encontrado.")
    db.commit()
