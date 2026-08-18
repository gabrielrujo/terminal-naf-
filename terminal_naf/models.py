"""Entidades e constantes de domínio do Terminal NAF."""

from dataclasses import dataclass
from enum import StrEnum


class Perfil(StrEnum):
    ATENDENTE = "ATENDENTE"
    ADMIN = "ADMIN"


class StatusAtendimento(StrEnum):
    AGUARDANDO = "AGUARDANDO"
    EM_ATENDIMENTO = "EM_ATENDIMENTO"
    CONCLUIDO = "CONCLUIDO"
    CANCELADO = "CANCELADO"


STATUS_FINAIS = {StatusAtendimento.CONCLUIDO, StatusAtendimento.CANCELADO}


@dataclass(frozen=True)
class Usuario:
    id: int
    nome: str
    login: str
    perfil: str
    ativo: bool

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            nome=row["nome"],
            login=row["login"],
            perfil=row["perfil"],
            ativo=bool(row["ativo"]),
        )


class RegraDeNegocioError(ValueError):
    """Erro esperado ao tentar executar uma operação inválida do domínio."""
