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

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  if (body.dataset.area === 'public' && body.dataset.home !== 'true') {
    let timeout;
    const restartTimeout = () => {
      window.clearTimeout(timeout);
      timeout = window.setTimeout(() => { window.location.href = '/'; }, 60_000);
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
})();
