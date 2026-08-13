// Relógio no topo
function atualizarRelogio() {
  const el = document.getElementById('relogio');
  if (!el) return;
  const agora = new Date();
  el.textContent = agora.toLocaleDateString('pt-BR') + '  ' + agora.toLocaleTimeString('pt-BR');
}
setInterval(atualizarRelogio, 1000);
atualizarRelogio();

// Modo kiosk: depois de um tempo sem interação, volta para a tela inicial.
// Evita que o terminal fique "preso" na tela de outra pessoa.
const TEMPO_INATIVIDADE_MS = 60 * 1000; // 60s — ajuste conforme o uso real
let timerInatividade;

function reiniciarTimerInatividade() {
  clearTimeout(timerInatividade);
  if (window.location.pathname === '/') return;
  timerInatividade = setTimeout(() => {
    window.location.href = '/';
  }, TEMPO_INATIVIDADE_MS);
}

['click', 'touchstart', 'keydown'].forEach(evt =>
  document.addEventListener(evt, reiniciarTimerInatividade)
);
reiniciarTimerInatividade();
