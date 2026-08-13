# Terminal NAF — protótipo v1

Protótipo funcional do terminal de suporte tecnológico do NAF, pensado para
rodar no Orange Pi 5 (Linux) e ser exibido em modo kiosk numa tela touch.

## O que já funciona

- Tela inicial com os 4 módulos do briefing: iniciar atendimento, informações
  e serviços, materiais educativos, painel do coordenador.
- Fluxo de atendimento: usuário escolhe o serviço (MEI, CPF, IRPF, DAS,
  Regularização, Outros) → gera um **protocolo** → grava no banco.
- Tela de avaliação (1 a 5) vinculada ao protocolo.
- Painel do coordenador em `/dashboard`, no formato de "livro-caixa" pedido
  no briefing: total de atendimentos, distribuição por serviço, taxa de
  resolução, satisfação média.
- Endpoint `/api/stats` em JSON, caso vocês queiram consumir os dados em
  outro painel depois.
- Timer de inatividade: se ninguém tocar na tela por 60s, o terminal volta
  sozinho para a tela inicial (essencial em modo kiosk público).

## Stack

- **Backend:** Flask + SQLite (arquivo `naf_terminal.db`, criado automaticamente).
- **Frontend:** HTML + CSS puro, sem framework JS — roda bem em hardware
  modesto e não depende de build step, o que facilita implantar no Orange Pi.
- **Fontes:** carregadas via Google Fonts (Fraunces / IBM Plex). Se o
  terminal for usado sem internet estável, baixe as fontes e sirva localmente
  em `static/fonts/`, trocando o `@import` no `style.css`.

## Como rodar

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Depois, no próprio Orange Pi, abra o navegador em modo kiosk apontando para
o servidor local:

```bash
chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:5000
```

Para rodar o Flask como serviço que sobe sozinho no boot, crie um arquivo
`systemd` (`/etc/systemd/system/naf-terminal.service`) chamando
`python app.py`, e outro habilitando o Chromium em kiosk no autostart do
usuário.

## Estrutura

```
naf_terminal/
├── app.py                 # rotas, banco, geração de protocolo, estatísticas
├── requirements.txt
├── static/
│   ├── style.css           # identidade visual "livro-caixa"
│   └── script.js            # relógio + timer de inatividade
└── templates/
    ├── base.html
    ├── index.html           # tela inicial
    ├── atendimento.html      # seleção de serviço
    ├── confirmacao.html      # "carimbo" com o protocolo
    ├── informacoes.html
    ├── materiais.html
    ├── avaliacao.html
    └── dashboard.html        # painel do coordenador
```

## Roadmap sugerido (v2 / v3), usando a NPU do Orange Pi

- **v2:** trocar a seleção manual de serviço por um campo de texto livre
  ("Não sei qual serviço preciso") + classificador leve (ex.: modelo
  pequeno de NLP rodando local via `rknn-toolkit2`, aproveitando a NPU de
  6 TOPS) que sugere o serviço mais provável.
- **v2:** base de conhecimento (FAQ do próprio NAF) com busca semântica
  local, para responder perguntas simples sem precisar de atendente.
- **v3:** chatbot local completo, rodando modelo pequeno on-device,
  encadeando classificação → base de conhecimento → escalonamento para
  atendimento humano quando necessário.
- Em qualquer uma dessas versões, o banco SQLite atual já registra tudo o
  que é necessário para treinar/ajustar esse classificador depois
  (serviço escolhido, protocolo, avaliação).
