PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    login TEXT NOT NULL UNIQUE COLLATE NOCASE,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL CHECK (perfil IN ('ATENDENTE', 'ADMIN')),
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS servicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE COLLATE NOCASE,
    nome TEXT NOT NULL,
    descricao TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sequencias (
    data TEXT PRIMARY KEY,
    ultimo_numero INTEGER NOT NULL CHECK (ultimo_numero > 0)
);

CREATE TABLE IF NOT EXISTS atendimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    senha TEXT NOT NULL,
    protocolo TEXT NOT NULL UNIQUE,
    servico_id INTEGER NOT NULL REFERENCES servicos(id),
    status TEXT NOT NULL DEFAULT 'AGUARDANDO'
        CHECK (status IN ('AGUARDANDO', 'EM_ATENDIMENTO', 'CONCLUIDO', 'CANCELADO')),
    atendente_id INTEGER REFERENCES usuarios(id),
    criado_em TEXT NOT NULL,
    chamado_em TEXT,
    iniciado_em TEXT,
    concluido_em TEXT,
    cancelado_em TEXT,
    motivo_cancelamento TEXT
);

CREATE TABLE IF NOT EXISTS chat_acessos (
    atendimento_id INTEGER PRIMARY KEY
        REFERENCES atendimentos(id) ON DELETE CASCADE,
    codigo_hash TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atendimento_id INTEGER NOT NULL
        REFERENCES atendimentos(id) ON DELETE CASCADE,
    autor_tipo TEXT NOT NULL
        CHECK (autor_tipo IN ('CIDADAO', 'ATENDENTE')),
    autor_usuario_id INTEGER REFERENCES usuarios(id),
    conteudo TEXT NOT NULL CHECK (length(conteudo) BETWEEN 1 AND 1000),
    criado_em TEXT NOT NULL,
    lido_em TEXT,
    CHECK (
        (autor_tipo = 'CIDADAO' AND autor_usuario_id IS NULL)
        OR (autor_tipo = 'ATENDENTE' AND autor_usuario_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS avaliacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atendimento_id INTEGER NOT NULL UNIQUE REFERENCES atendimentos(id) ON DELETE CASCADE,
    nota INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),
    criado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_atendimentos_status_criado
    ON atendimentos(status, criado_em);
CREATE INDEX IF NOT EXISTS idx_atendimentos_atendente_status
    ON atendimentos(atendente_id, status);
CREATE INDEX IF NOT EXISTS idx_atendimentos_servico
    ON atendimentos(servico_id);
CREATE INDEX IF NOT EXISTS idx_mensagens_atendimento_id
    ON mensagens(atendimento_id, id);
CREATE INDEX IF NOT EXISTS idx_mensagens_nao_lidas
    ON mensagens(atendimento_id, autor_tipo, lido_em);
