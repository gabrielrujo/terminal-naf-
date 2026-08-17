# Terminal NAF

Aplicação web para triagem e acompanhamento de atendimentos do Núcleo de Apoio
Contábil e Fiscal (NAF). O projeto foi desenhado como um protótipo para rodar em
um Orange Pi 5 com uma tela touch em modo kiosk, mas também pode ser executado em
qualquer computador com Python.

## Estado atual

O fluxo principal está funcional de ponta a ponta:

```text
Cidadão escolhe um serviço
        ↓
Senha criada como "aguardando"
        ↓
Atendente inicia o atendimento
        ↓
Status muda para "em_atendimento"
        ↓
Atendente responsável ou coordenação conclui
        ↓
Status muda para "concluido" e a avaliação é liberada
```

A emissão de uma senha não é contabilizada como atendimento concluído. Os
indicadores separam senhas emitidas, pessoas aguardando, atendimentos em curso e
atendimentos concluídos.

### Perfis

- **Cidadão:** consulta os serviços e materiais, escolhe um serviço e recebe um
  protocolo no formato `NAF-AAAAMMDD-0000`.
- **Atendente:** acessa a fila, inicia uma senha e conclui os próprios
  atendimentos.
- **Coordenador:** possui as funções do atendente e também acessa os indicadores,
  conclui qualquer atendimento e gerencia usuários.

### Funcionalidades implementadas

- primeiro acesso com criação obrigatória de uma conta de coordenação;
- autenticação por sessão e senhas armazenadas com hash do Werkzeug;
- cadastro de atendentes e coordenadores, com ativação e desativação de contas;
- fila ordenada, priorizando atendimentos já iniciados;
- registro do responsável e dos horários de criação, início e conclusão;
- avaliação única de 1 a 5, aceita apenas após a conclusão;
- dashboard com totais, conclusão por serviço, taxa de resolução e nota média;
- endpoint JSON protegido em `GET /api/stats`;
- retorno automático à página inicial após 60 segundos sem interação nas telas
  públicas;
- criação automática do banco e migração básica do esquema da primeira versão;
- testes automatizados para o ciclo do atendimento e a proteção do dashboard.

## Tecnologias e organização

- **Backend:** Python, Flask e Werkzeug.
- **Persistência:** SQLite no arquivo local `naf_terminal.db`.
- **Frontend:** templates Jinja, HTML, CSS e JavaScript sem etapa de build.
- **Testes:** `unittest` e cliente de testes do Flask.

O arquivo `app.py` concentra a configuração, o acesso ao banco, a autenticação e
as rotas. Os dados de serviços e materiais ainda são listas fixas nesse arquivo.
As páginas ficam em `templates/`; o estilo e o comportamento do kiosk ficam em
`static/`.

O banco possui três tabelas:

- `usuarios`: credenciais, perfil e situação da conta;
- `atendimentos`: protocolo, serviço, estado, responsável e horários;
- `avaliacoes`: nota vinculada ao protocolo, limitada a um registro por
  protocolo.

## Requisitos

- Python 3;
- `pip`;
- navegador moderno; Chromium é indicado para o modo kiosk.

## Instalação e execução local

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export NAF_SECRET_KEY="defina-uma-chave-longa-e-aleatoria"
python app.py
```

A aplicação ficará disponível em `http://localhost:5001` e aceitará conexões da
rede local porque o servidor escuta em `0.0.0.0`.

`NAF_SECRET_KEY` protege a sessão da equipe. Se a variável não for definida, o
sistema usa uma chave conhecida de desenvolvimento; isso é aceitável somente
para testes locais.

O arquivo `naf_terminal.db` é criado automaticamente na raiz do projeto e está
ignorado pelo Git. Para reiniciar totalmente os dados durante o desenvolvimento,
pare a aplicação e remova esse arquivo sabendo que usuários, atendimentos e
avaliações serão perdidos.

### Primeiro acesso

1. Abra `http://localhost:5001/login` ou clique em **Acesso da equipe**.
2. Como ainda não existem usuários, o sistema abrirá a configuração inicial.
3. Cadastre a primeira conta; ela terá o perfil de coordenador.
4. Use **Usuários** para cadastrar os atendentes.

Não existe usuário ou senha padrão.

## Como validar o fluxo

O ideal é usar duas janelas ou dispositivos: uma janela anônima representa o
terminal do cidadão e outra representa a equipe.

1. Entre como coordenador ou atendente na janela da equipe.
2. Na janela do cidadão, escolha **Iniciar atendimento**, selecione o serviço e
   anote o protocolo.
3. Na área da equipe, abra **Fila** e clique em **Iniciar**.
4. Conclua o atendimento com a mesma conta que o iniciou ou com uma conta de
   coordenação.
5. Registre uma nota na tela de avaliação.
6. Como coordenador, confira os resultados no dashboard.

## Testes

Com o ambiente virtual ativo, execute:

```bash
python -m unittest discover -s tests -v
```

Os testes usam um banco SQLite temporário e não alteram o banco local da
aplicação.

## Rotas principais

| Método | Rota | Acesso | Finalidade |
| --- | --- | --- | --- |
| `GET` | `/` | Público | Página inicial |
| `GET/POST` | `/atendimento` | Público | Seleção do serviço e emissão da senha |
| `GET` | `/confirmacao/<protocolo>` | Público | Confirmação da senha |
| `GET` | `/informacoes` | Público | Lista dos serviços |
| `GET` | `/materiais` | Público | Lista dos materiais educativos |
| `GET/POST` | `/avaliacao/<protocolo>` | Público após conclusão | Registro da avaliação |
| `GET/POST` | `/configuracao-inicial` | Público enquanto não há usuários | Criação do primeiro coordenador |
| `GET/POST` | `/login` | Público | Login da equipe |
| `POST` | `/logout` | Equipe | Encerramento da sessão |
| `GET` | `/fila` | Equipe | Fila de senhas ativas |
| `POST` | `/atendimentos/<id>/iniciar` | Equipe | Início do atendimento |
| `POST` | `/atendimentos/<id>/concluir` | Responsável ou coordenação | Conclusão do atendimento |
| `GET` | `/dashboard` | Coordenação | Indicadores consolidados |
| `GET/POST` | `/usuarios` | Coordenação | Consulta e cadastro de usuários |
| `POST` | `/usuarios/<id>/alternar` | Coordenação | Ativação ou desativação de usuário |
| `GET` | `/api/stats` | Coordenação | Quantidade de concluídos por serviço em JSON |

## Estrutura do projeto

```text
terminal-naf/
├── app.py
├── requirements.txt
├── README.md
├── static/
│   ├── script.js
│   └── style.css
├── templates/
│   ├── atendimento.html
│   ├── avaliacao.html
│   ├── base.html
│   ├── configuracao_inicial.html
│   ├── confirmacao.html
│   ├── dashboard.html
│   ├── fila.html
│   ├── index.html
│   ├── informacoes.html
│   ├── login.html
│   ├── materiais.html
│   └── usuarios.html
└── tests/
    └── test_fluxo.py
```

## Uso no Orange Pi

Depois de iniciar a aplicação, abra o Chromium em tela cheia. O nome do
executável pode ser `chromium` ou `chromium-browser`, conforme a distribuição:

```bash
chromium --kiosk --noerrdialogs --disable-infobars http://localhost:5001
```

As fontes visuais são carregadas do Google Fonts pelo CSS. Em uma instalação sem
internet estável, elas devem ser baixadas para `static/fonts/` e referenciadas
localmente.

## Limitações antes de produção

O projeto está adequado para demonstração e validação do fluxo, mas ainda não
está pronto para exposição direta na internet:

- `python app.py` inicia o servidor de desenvolvimento do Flask com o modo debug
  habilitado; uma implantação real precisa de servidor WSGI e debug desativado;
- os formulários não possuem proteção CSRF e o login não tem limitação de
  tentativas;
- a chave de sessão padrão deve ser substituída por `NAF_SECRET_KEY`;
- a conclusão redireciona o navegador usado pela equipe para a avaliação; em uma
  operação com telas separadas, ainda falta sincronizar ou abrir a avaliação no
  terminal do cidadão;
- o dashboard consolida todo o histórico, sem filtro por período ou unidade;
- os materiais educativos exibem somente títulos, sem arquivo, link ou conteúdo;
- não há rotina automatizada de backup, recuperação ou exportação do SQLite;
- os testes atuais cobrem o caminho principal, mas não toda a autenticação, as
  permissões, as migrações e os cenários de concorrência.

## Próximos passos sugeridos

1. Separar a experiência do terminal público da estação da equipe e sincronizar
   a liberação da avaliação.
2. Preparar a execução de produção, com configuração externa, WSGI, CSRF,
   cookies seguros e limitação de tentativas de login.
3. Adicionar filtros por data e exportação de relatórios no dashboard.
4. Transformar serviços e materiais em conteúdo administrável.
5. Ampliar os testes de autenticação, autorização, migração e concorrência.
6. Adicionar uma triagem assistida para quem não sabe qual serviço escolher,
   sempre pedindo confirmação e encaminhando casos incertos para **Outros**.
