# Terminal NAF V2

Sistema de triagem, fila e acompanhamento de atendimentos do NAF — Núcleo de
Apoio Contábil e Fiscal. A V2 foi preparada para demonstrações com coordenadores
e para futura execução em um Orange Pi ou Raspberry Pi com Chromium em modo
kiosk.

O projeto possui duas experiências independentes:

- **terminal público:** triagem, emissão de senha, acompanhamento do protocolo,
  chat com o atendente e avaliação pelo cidadão;
- **área interna:** login, fila operacional, chat, painel do atendente, dashboard
  e cadastros administrativos.

## Estado da V2

O cenário principal está implementado e validado:

```text
selecionar serviço
      ↓
confirmar seleção
      ↓
AGUARDANDO
      ↓
EM_ATENDIMENTO
      ↕
chat cidadão ↔ atendente
      ↓
CONCLUIDO
      ↓
avaliação pública pelo protocolo
```

Um atendimento também pode passar de `AGUARDANDO` ou `EM_ATENDIMENTO` para
`CANCELADO`. Estados finais não retornam ao fluxo normal.

A senha emitida nunca é tratada como atendimento realizado. Dashboard e banco
diferenciam senhas emitidas, aguardando, em atendimento, concluídas e canceladas.

## Funcionalidades

### Cidadão

- consulta serviços e materiais sem login;
- escolhe e confirma o serviço antes da criação do atendimento;
- recebe uma senha sequencial amigável, como `A001`;
- recebe um protocolo único, como `NAF-20260818-0001`;
- recebe um código aleatório de oito caracteres que protege o chat;
- acompanha o status por uma página que consulta o servidor automaticamente;
- troca mensagens de texto com o atendente enquanto o estado é
  `EM_ATENDIMENTO` e vê a confirmação de leitura;
- consulta as mensagens depois da conclusão ou do cancelamento, sem poder enviar
  novas mensagens;
- avalia de 1 a 5 somente depois da conclusão;
- não consegue avaliar protocolo inexistente, não concluído ou já avaliado;
- retorna ao início após 60 segundos sem interação nas páginas públicas; a
  página autorizada do chat permanece aberta enquanto aguarda ou realiza o
  atendimento.

### Atendente

- acessa o painel próprio em `/atendente`;
- visualiza resumo, fila por ordem de chegada e atendimento atual;
- chama, inicia, conclui ou cancela conforme o estado permitido;
- conversa com o cidadão no painel durante o atendimento e vê a confirmação de
  leitura;
- visualiza o histórico dos próprios atendimentos;
- não pode concluir uma senha que nunca foi iniciada;
- não pode assumir/cancelar um atendimento atribuído a outro atendente;
- não é redirecionado para a avaliação do cidadão.

### Administrador

- acessa o dashboard em `/admin`;
- filtra indicadores por hoje, últimos 7 dias, mês, total ou período
  personalizado;
- consulta senhas emitidas, estados, avaliações e tempos médios;
- consulta atendimentos e avaliações;
- cria, ativa e desativa usuários;
- cria, ativa e desativa serviços;
- pode acessar a fila operacional sem perder o layout interno.

## Tecnologias

- Python 3.11 ou superior;
- Flask 3;
- SQLite com chaves estrangeiras e restrições no schema;
- Jinja, CSS e JavaScript locais, sem framework, CDN ou serviço externo de chat;
- `unittest` para testes automatizados.

A V2 usa diretamente a biblioteca `sqlite3` do Python. Isso mantém a instalação
leve e sem dependências de banco adicionais, importante para hardware compacto e
operação sem internet.

## Arquitetura

```text
terminal-naf/
├── terminal_naf/
│   ├── __init__.py              # application factory
│   ├── config.py                # configuração por ambiente
│   ├── database.py              # conexão e inicialização SQLite
│   ├── schema.sql               # tabelas, relações e índices
│   ├── models.py                # perfis, estados e erros de domínio
│   ├── security.py              # sessão, autorização e CSRF
│   ├── cli.py                   # seed e reset de demonstração
│   ├── routes/
│   │   ├── public.py            # terminal e avaliação
│   │   ├── auth.py              # login e logout
│   │   ├── atendente.py         # fila e ações operacionais
│   │   └── admin.py             # dashboard e cadastros
│   ├── services/
│   │   ├── atendimentos.py      # transições e geração de protocolo
│   │   ├── chat.py              # acesso, mensagens e recibos de leitura
│   │   ├── catalogo.py          # serviços e materiais iniciais
│   │   ├── indicadores.py       # métricas e filtros
│   │   └── usuarios.py          # contas e autenticação
│   ├── templates/
│   │   ├── public/
│   │   ├── auth/
│   │   ├── atendente/
│   │   ├── admin/
│   │   ├── components/
│   │   └── errors/
│   └── static/
│       ├── css/app.css
│       └── js/app.js
├── instance/                    # banco V2 local, ignorado pelo Git
├── backups/                     # backups locais, ignorados pelo Git
├── tests/
│   ├── test_fluxo.py            # testes preservados da V1
│   └── test_v2_fluxo.py         # regras críticas da V2
├── run.py                       # execução da V2
├── app.py                       # aplicação V1 preservada
├── requirements.txt
└── README.md
```

### Banco de dados

O banco V2 fica em `instance/terminal_naf_v2.db` e é criado automaticamente. Ele
não substitui o banco antigo `naf_terminal.db`.

Entidades:

- `usuarios`: funcionários e coordenadores, nunca cidadãos;
- `servicos`: catálogo utilizado pela triagem pública;
- `atendimentos`: senha, protocolo, serviço, estado, responsável e horários;
- `chat_acessos`: hash do código aleatório vinculado ao atendimento;
- `mensagens`: texto, autor, horário e confirmação de leitura do chat;
- `avaliacoes`: uma nota por atendimento concluído;
- `sequencias`: numeração diária das senhas sem sorteio aleatório.

Não existem campos cadastrais para CPF, renda, endereço ou documentos do
cidadão. Como as mensagens são texto livre e persistem no banco, a interface
orienta os dois participantes a não enviarem dados pessoais, senhas, documentos
ou dados bancários.

## Instalação

Na raiz do repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Defina uma chave de sessão própria:

```bash
export NAF_SECRET_KEY="troque-por-uma-chave-longa-e-aleatoria"
```

Sem essa variável, a aplicação utiliza uma chave conhecida apenas para
desenvolvimento local.

## Dados de demonstração

Prepare os serviços e usuários com:

```bash
flask --app run.py seed-demo
```

Contas locais padrão:

| Perfil | Usuário | Senha de desenvolvimento |
| --- | --- | --- |
| Administrador | `admin` | `admin123` |
| Atendente | `atendente` | `atendente123` |

Essas credenciais são exclusivas para demonstração. É possível trocar as senhas
do seed sem alterar o código:

```bash
export NAF_DEMO_ADMIN_PASSWORD="outra-senha-segura"
export NAF_DEMO_ATENDENTE_PASSWORD="outra-senha-segura"
flask --app run.py seed-demo
```

Executar o seed novamente restaura as contas de demonstração, seus perfis e suas
senhas configuradas.

## Iniciar a V2

```bash
python run.py
```

Abra `http://localhost:5000`.

- terminal público: `http://localhost:5000/`;
- login da equipe: `http://localhost:5000/login`;
- painel do atendente após login: `http://localhost:5000/atendente`;
- dashboard administrativo após login: `http://localhost:5000/admin`.

O modo debug fica desativado por padrão. Para desenvolvimento local explícito:

```bash
export NAF_DEBUG=1
python run.py
```

## Demonstração completa

Use duas janelas, de preferência deixando o terminal público em uma janela
anônima.

1. No terminal público, clique em **Iniciar atendimento**.
2. Escolha **MEI**, revise a seleção e confirme.
3. Anote a senha `A001`, o protocolo e o código do chat; mantenha a página aberta.
4. Em outra janela, entre com `atendente` / `atendente123`.
5. Na fila, chame ou inicie a senha.
6. Envie uma mensagem pela página pública e responda no painel do atendente.
7. Observe o indicador **Lida** depois que a outra janela consultar a conversa.
8. Conclua o atendimento; o chat continuará visível, mas ficará somente leitura.
9. Volte à página pública e registre a avaliação com nota 5.
10. Tente abrir a avaliação novamente para verificar o bloqueio de duplicidade.
11. Entre com `admin` / `admin123` e abra o dashboard em **Total geral**.

O resultado esperado é uma senha emitida, um atendimento concluído, média 5,0 e
MEI com uma conclusão.

## Reset da demonstração

O reset cria um backup do banco antes de remover dados:

```bash
flask --app run.py reset-demo
```

Para automação sem confirmação interativa:

```bash
flask --app run.py reset-demo --yes
```

O comando remove atendimentos, avaliações, mensagens, acessos de chat e
sequências. Mensagens e acessos saem em cascata com o atendimento; usuários e
serviços são preservados. O caminho do backup é exibido no terminal e os arquivos
ficam em `backups/`.

Não existe botão público para apagar dados.

## Testes

```bash
python -m unittest discover -s tests -v
```

Os testes da V2 cobrem:

- confirmação de serviço sem criação prematura;
- estado inicial `AGUARDANDO`;
- numeração sequencial;
- transição para `EM_ATENDIMENTO` com responsável e horário;
- proibição de `AGUARDANDO → CONCLUIDO`;
- cancelamento;
- avaliação apenas após conclusão;
- avaliação única;
- bloqueio de avaliação por uma sessão da equipe;
- autenticação e separação de perfis;
- indicadores administrativos;
- troca de mensagens entre cidadão e atendente;
- código de acesso obrigatório em outro navegador;
- isolamento entre atendentes;
- bloqueio de mensagens antes do início e depois do encerramento;
- validação do tamanho e confirmação de leitura;
- proteção CSRF.

Cada teste utiliza um banco temporário e não altera os dados da demonstração.

## Configuração por ambiente

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `NAF_SECRET_KEY` | chave apenas de desenvolvimento | Assinatura segura da sessão |
| `NAF_DATABASE` | `instance/terminal_naf_v2.db` | Caminho do banco V2 |
| `NAF_BACKUP_DIR` | `backups/` | Destino dos backups de reset |
| `NAF_HOST` | `0.0.0.0` | Interface de rede |
| `NAF_PORT` | `5000` | Porta HTTP |
| `NAF_DEBUG` | `0` | Ativa debug somente quando igual a `1` |
| `NAF_COOKIE_SECURE` | `0` | Exige HTTPS no cookie quando igual a `1` |
| `NAF_DEMO_ADMIN_PASSWORD` | `admin123` | Senha local criada pelo seed |
| `NAF_DEMO_ATENDENTE_PASSWORD` | `atendente123` | Senha local criada pelo seed |

## Orange Pi / Raspberry Pi

O frontend não depende de Google Fonts, CDN ou internet. Depois de iniciar o
servidor, o terminal pode abrir o Chromium em modo kiosk:

```bash
chromium --kiosk --noerrdialogs --disable-infobars http://localhost:5000
```

O executável pode se chamar `chromium-browser`, conforme a distribuição Linux.
Para implantação permanente, configure um serviço `systemd` com usuário sem
privilégios e um servidor WSGI em vez do servidor de desenvolvimento do Flask.

## Preview na Vercel

A V2 pode ser publicada como **preview temporário** para validar páginas, login,
fila e um fluxo curto do chat:

```bash
npx vercel link
npx vercel
```

O `pyproject.toml` aponta explicitamente para `run:app`, evitando que a Vercel
publique por engano a V1 preservada em `app.py`. Os arquivos de frontend ficam
em `public/static/`, compatíveis com o CDN da plataforma.

O SQLite não possui armazenamento persistente nas Vercel Functions. Por isso,
os ambientes `preview` e `development` usam um banco efêmero em `/tmp` com as
contas de demonstração. Para permitir conscientemente a mesma demonstração no
primeiro deploy criado pela interface web, configure
`NAF_ALLOW_EPHEMERAL_VERCEL=1`. Os dados podem desaparecer ou divergir entre
instâncias a qualquer momento. Esse modo serve para demonstração curta, não para
validar persistência, concorrência ou disponibilidade do chat.

Deploy de `production` é bloqueado enquanto o SQLite não for substituído por um
banco externo compartilhado, exceto quando essa variável de demonstração estiver
explicitamente habilitada.

## Segurança aplicada

- senha armazenada somente como hash do Werkzeug;
- autenticação por sessão com cookie `HttpOnly` e `SameSite=Lax`;
- proteção CSRF em operações de escrita;
- autorização server-side para atendente e administrador;
- código de chat armazenado somente como hash e autorização pública vinculada à
  sessão;
- identidade do autor definida no servidor, sem confiar no tipo enviado pelo
  navegador;
- mensagens limitadas a texto de até 1.000 caracteres e renderizadas no frontend
  com `textContent`;
- validação das transições de estado no servidor;
- restrições de integridade e unicidade também no SQLite;
- páginas amigáveis para erros 400, 403, 404 e 500;
- debug desativado por padrão.

Em produção, ainda é necessário usar HTTPS, `NAF_COOKIE_SECURE=1`, uma chave de
sessão secreta, servidor WSGI, política de backup externo e limitação de
tentativas no login e na validação do código do chat.

## V1 preservada

A V1 está preservada no commit `5e52830` da branch `main` e a reconstrução foi
feita em paralelo. Os arquivos antigos não foram removidos.

- aplicação V1: `app.py`, `templates/` e `static/`;
- banco V1: `naf_terminal.db`;
- backup validado antes da reconstrução:
  `backups/naf_terminal.backup-pre-v2-20260817.db`;
- aplicação V2: `run.py` e pacote `terminal_naf/`;
- banco V2: `instance/terminal_naf_v2.db`.

Para executar a V1 preservada, use `python app.py`; ela continua na porta 5001.

## Pendências não críticas

- troca de senha pela própria interface;
- exportação de relatórios em CSV/PDF;
- edição de serviços já cadastrados, além de ativação/desativação;
- conteúdo completo ou arquivos para os materiais educativos;
- migrações versionadas para evoluções futuras do schema;
- deploy WSGI/systemd pronto para produção;
- assistente virtual, propositalmente fora do escopo desta entrega.
