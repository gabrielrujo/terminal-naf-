(() => {
  const clock = document.querySelector('[data-clock]');
  const updateClock = () => {
    if (!clock) return;
    const now = new Date();
    clock.textContent = new Intl.DateTimeFormat('pt-BR', {
      weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
    }).format(now);
  };
  updateClock();
  window.setInterval(updateClock, 30_000);

  const body = document.body;
  const menuToggle = document.querySelector('[data-menu-toggle]');
  menuToggle?.addEventListener('click', () => body.classList.toggle('menu-open'));

  window.addEventListener('pageshow', (event) => {
    if (event.persisted && document.querySelector('[data-chat]')) window.location.reload();
  });

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  if (body.dataset.area === 'public' && body.dataset.home !== 'true') {
    let timeout;
    const restartTimeout = () => {
      window.clearTimeout(timeout);
      timeout = window.setTimeout(() => {
        const chat = document.querySelector('[data-chat]');
        const chatStillActive = chat && !['CONCLUIDO', 'CANCELADO'].includes(chat.dataset.chatStatus);
        if (chatStillActive) restartTimeout();
        else window.location.href = '/';
      }, 60_000);
    };
    ['pointerdown', 'keydown', 'touchstart'].forEach((eventName) => {
      document.addEventListener(eventName, restartTimeout, { passive: true });
    });
    restartTimeout();
  }

  const protocolCard = document.querySelector('[data-protocol-card]');
  if (protocolCard) {
    const labels = {
      AGUARDANDO: 'Aguardando atendimento',
      EM_ATENDIMENTO: 'Em atendimento',
      CONCLUIDO: 'Atendimento concluído',
      CANCELADO: 'Atendimento cancelado'
    };
    const guidance = {
      AGUARDANDO: 'Aguarde o chamado da equipe do NAF.',
      EM_ATENDIMENTO: 'Seu atendimento está em andamento.',
      CONCLUIDO: 'Seu atendimento foi finalizado. Você já pode avaliar.',
      CANCELADO: 'Esta senha foi cancelada. Procure a equipe se precisar de ajuda.'
    };
    const pollStatus = async () => {
      try {
        const response = await fetch(protocolCard.dataset.statusUrl, { cache: 'no-store' });
        if (!response.ok) return;
        const data = await response.json();
        const statusPanel = protocolCard.querySelector('.status-panel');
        protocolCard.dataset.status = data.status;
        statusPanel.className = `status-panel status-${data.status.toLowerCase()}`;
        protocolCard.querySelector('[data-status-label]').textContent = labels[data.status];
        protocolCard.querySelector('[data-status-guidance]').textContent = guidance[data.status];
        document.querySelector('[data-evaluation-link]')?.classList.toggle('hidden', !data.pode_avaliar);
        document.querySelector('[data-evaluated-note]')?.classList.toggle('hidden', !data.avaliado);
        if (['CONCLUIDO', 'CANCELADO'].includes(data.status)) window.clearInterval(pollTimer);
      } catch (_error) {
        // A consulta seguinte tenta novamente; o terminal continua utilizável offline.
      }
    };
    const pollTimer = window.setInterval(pollStatus, 4_000);
  }

  const formatMessageTime = (value) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat('pt-BR', {
      hour: '2-digit', minute: '2-digit'
    }).format(date);
  };

  document.querySelectorAll('[data-chat]').forEach((chat) => {
    const ownSide = chat.dataset.chatSide;
    const timeline = chat.querySelector('[data-chat-messages]');
    const empty = chat.querySelector('[data-chat-empty]');
    const form = chat.querySelector('[data-chat-form]');
    const input = chat.querySelector('[data-chat-input]');
    const send = chat.querySelector('[data-chat-send]');
    const stateLabel = chat.querySelector('[data-chat-state]');
    const feedback = chat.querySelector('[data-chat-feedback]');
    let lastId = 0;
    let polling = false;
    let timer = null;

    const setFeedback = (message = '') => {
      feedback.textContent = message;
    };

    const setState = (status, open) => {
      chat.dataset.chatStatus = status;
      chat.classList.toggle('is-open', open);
      chat.classList.toggle('is-closed', ['CONCLUIDO', 'CANCELADO'].includes(status));
      input.disabled = !open;
      send.disabled = !open;
      if (open) stateLabel.textContent = 'Conversa aberta';
      else if (status === 'AGUARDANDO') stateLabel.textContent = 'Aguardando o início do atendimento';
      else stateLabel.textContent = 'Conversa encerrada · disponível para consulta';
      if (['CONCLUIDO', 'CANCELADO'].includes(status) && timer) {
        window.clearInterval(timer);
        timer = null;
      }
    };

    const renderMessage = (message) => {
      if (timeline.querySelector(`[data-message-id="${message.id}"]`)) return;
      empty?.remove();
      const own = message.autor_tipo === ownSide;
      const article = document.createElement('article');
      article.className = `chat-message ${own ? 'own' : 'other'}`;
      article.dataset.messageId = message.id;
      if (message.lido_em && own) article.classList.add('is-read');

      const header = document.createElement('header');
      const author = document.createElement('strong');
      const time = document.createElement('time');
      author.textContent = own ? 'Você' : message.autor_nome;
      time.textContent = formatMessageTime(message.criado_em);
      time.dateTime = message.criado_em;
      header.append(author, time);

      const content = document.createElement('p');
      content.textContent = message.conteudo;
      article.append(header, content);

      if (own) {
        const footer = document.createElement('footer');
        const receipt = document.createElement('span');
        receipt.dataset.chatReceipt = '';
        footer.append(receipt);
        article.append(footer);
      }
      timeline.append(article);
      lastId = Math.max(lastId, Number(message.id));
      timeline.scrollTop = timeline.scrollHeight;
    };

    const markAsRead = (readUntil) => {
      chat.querySelectorAll('.chat-message.own[data-message-id]').forEach((message) => {
        if (Number(message.dataset.messageId) <= Number(readUntil)) {
          message.classList.add('is-read');
        }
      });
    };

    const parseResponse = async (response) => {
      const contentType = response.headers.get('content-type') || '';
      return contentType.includes('application/json') ? response.json() : {};
    };

    const poll = async () => {
      if (polling) return;
      polling = true;
      try {
        const separator = chat.dataset.chatGetUrl.includes('?') ? '&' : '?';
        const response = await fetch(
          `${chat.dataset.chatGetUrl}${separator}depois_de=${lastId}`,
          { cache: 'no-store', headers: { Accept: 'application/json' } }
        );
        const data = await parseResponse(response);
        if (!response.ok) {
          setFeedback(data.erro || 'Não foi possível atualizar a conversa.');
          if (response.status === 403 && timer) window.clearInterval(timer);
          return;
        }
        setFeedback('');
        data.mensagens.forEach(renderMessage);
        markAsRead(data.lido_ate);
        setState(data.status, data.aberto);
      } catch (_error) {
        setFeedback('Reconectando...');
      } finally {
        polling = false;
      }
    };

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!input.value.trim() || input.disabled) return;
      send.disabled = true;
      setFeedback('Enviando...');
      try {
        const response = await fetch(chat.dataset.chatPostUrl, {
          method: 'POST',
          body: new FormData(form),
          headers: { Accept: 'application/json' }
        });
        const data = await parseResponse(response);
        if (!response.ok) {
          setFeedback(data.erro || 'Não foi possível enviar a mensagem.');
          if (response.status === 409) await poll();
          return;
        }
        renderMessage(data.mensagem);
        form.reset();
        setFeedback('');
        input.focus();
      } catch (_error) {
        setFeedback('Sem conexão. Tente enviar novamente.');
      } finally {
        send.disabled = input.disabled;
      }
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });

    setState(chat.dataset.chatStatus, chat.dataset.chatStatus === 'EM_ATENDIMENTO');
    timer = window.setInterval(poll, 2_500);
    poll();
  });
})();
