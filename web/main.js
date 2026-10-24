// Lógica da interface: chat, fala (TTS real ou simulada) e HUD.
import { criarCena } from './scene.js';

const cena = criarCena(document.getElementById('cena'));
const $ = id => document.getElementById(id);
const chat = $('chat'), onda = $('onda');
for (let i = 0; i < 28; i++) onda.appendChild(document.createElement('i'));

setInterval(() => { $('relogio').textContent = new Date().toLocaleTimeString('pt-BR'); }, 500);

function addMsg(quem, texto) {
  const d = document.createElement('div'); d.className = 'msg' + (quem === 'eu' ? ' eu' : '');
  d.innerHTML = `<em>${quem === 'eu' ? 'BRUNO' : 'JARVIS'}</em>`; d.append(texto);
  chat.appendChild(d); chat.scrollTop = chat.scrollHeight;
  cena.estado.ultimas.push([quem, texto]);
}

// Nível de "volume" da fala: simulado por sílabas, para animar boca e ondas
let alvo = 0;
setInterval(() => { alvo = cena.estado.falando ? .3 + Math.random() * .7 : 0; }, 90);
(function anima() {
  cena.estado.nivel += (alvo - cena.estado.nivel) * .35;
  onda.querySelectorAll('i').forEach((b, i) => {
    const h = cena.estado.falando ? 6 + cena.estado.nivel * 40 * Math.abs(Math.sin(i * .7 + performance.now() / 120)) : 4 + Math.sin(i + performance.now() / 400) * 2;
    b.style.height = h + 'px';
  });
  requestAnimationFrame(anima);
})();

function setFalando(v) {
  cena.estado.falando = v;
  document.body.classList.toggle('falando', v);
  $('estado').textContent = v ? 'FALANDO' : 'EM ESPERA';
}

export function falar(texto) {
  $('legenda').textContent = texto;
  setFalando(true);
  const fim = () => setFalando(false);
  if ($('tts').checked && 'speechSynthesis' in window && speechSynthesis.getVoices) {
    const u = new SpeechSynthesisUtterance(texto); u.lang = 'pt-BR'; u.rate = 1.02; u.pitch = .9;
    const v = speechSynthesis.getVoices().find(v => v.lang.startsWith('pt'));
    if (v) u.voice = v;
    u.onend = fim; u.onerror = () => setTimeout(fim, texto.length * 60);
    speechSynthesis.cancel(); speechSynthesis.speak(u);
    setTimeout(() => { if (!speechSynthesis.speaking) setTimeout(fim, texto.length * 60); }, 800); // fallback
  } else setTimeout(fim, 600 + texto.length * 60); // modo simulado
}

$('form').addEventListener('submit', async ev => {
  ev.preventDefault();
  const texto = $('entrada').value.trim(); if (!texto) return;
  $('entrada').value = ''; addMsg('eu', texto);
  try {
    if ($('motor').checked) {   // agente com ferramentas (pesquisa, comércios, sites, Blender, Godot...)
      const r = await fetch('/api/motor', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto }) });
      const j = await r.json(); const extra = j.passos.map(p => `${p.ok ? '✔' : '✖'} ${p.ferramenta} ${Object.values(p.resumo).join(' ')}`).join('\n');
      addMsg('jarvis', j.resposta + (extra ? '\n' + extra : '')); falar(j.resposta); return;
    }
    const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto }) });
    const { resposta, acoes } = await r.json(); addMsg('jarvis', resposta); falar(resposta);
    if (acoes && acoes.length && controleLigado) for (const a of acoes) { if (!(await executar(a))) break; }
  } catch { addMsg('jarvis', 'Falha de conexão com o núcleo Python.'); }
});

addMsg('jarvis', 'Sistemas online. Olá, Bruno.');
const NOMES = { live5d: 'LIVE · câmera 5D no tripé', medio: 'Medium shot', close: 'Close-up na tela', ombro: 'Por cima do ombro', tela: 'Tela de frente', live: 'Frente (mesa)', orbita: '360° órbita', quarto: 'Quarto', rosto: 'Close no rosto' };
document.querySelectorAll('.vistas button').forEach(b => b.onclick = () => {
  document.querySelectorAll('.vistas button').forEach(x => x.classList.toggle('on', x === b));
  cena.vista(b.dataset.v); $('vistaNome').textContent = NOMES[b.dataset.v];
});

// ---------- controle do PC (DESLIGADO por padrão) ----------
let controleLigado = false;
function mostrarControle(v) {
  controleLigado = v; cena.estado.controle = v;
  const b = $('togControle'); b.classList.toggle('on', v); b.classList.toggle('off', !v);
  $('togTxt').textContent = v ? 'CONTROLE DO PC: LIGADO' : 'CONTROLE DO PC: DESLIGADO';
  document.body.classList.toggle('controlando', v);
}
const post = (url, corpo) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo || {}) }).then(r => r.json());
$('togControle').onclick = async () => {
  const quer = !controleLigado;
  if (quer && !confirm('Ligar o controle? O Ryker vai mover o mouse e clicar/digitar no seu PC de verdade.\nPara parar: botão PARAR, Esc 3x, Ctrl+Alt+Q ou mouse num canto da tela.')) return;
  mostrarControle((await post('/api/controle', { ligado: quer })).ligado);
};
async function parar() { cena.fimAcao(); mostrarControle((await post('/api/parar')).ligado); atualizarLog(); }
$('parar').onclick = parar;
let escs = [];
addEventListener('keydown', ev => {
  if (ev.key === 'Escape') { const t = performance.now(); escs = escs.filter(x => t - x < 1500).concat(t); if (escs.length >= 3) { escs = []; parar(); } }
  if (ev.ctrlKey && ev.altKey && ev.key.toLowerCase() === 'q') parar();
});
// executa UMA ação: anima mão + cursor 3D até o alvo e então manda pro PC real
async function executar(a) {
  if (!controleLigado) { addMsg('jarvis', 'Controle do PC desligado: ligue no botão grande pra eu clicar no seu PC.'); return false; }
  await cena.animarAcao(a);
  let r; try { r = await post('/api/acao', a); } catch { r = { ok: false, erro: 'sem conexão' }; }
  cena.fimAcao(); atualizarLog();
  if (!r.ok) { addMsg('jarvis', 'Ação recusada: ' + r.erro); if (/DESLIGADO|Failsafe|emerg/i.test(r.erro || '')) mostrarControle(false); }
  return r.ok;
}
cena.aoClicarTela(a => executar(a));
async function atualizarLog() {
  try {
    const { ligado, log } = await (await fetch('/api/log')).json();
    if (ligado !== controleLigado) mostrarControle(ligado);
    $('log').innerHTML = log.slice(-14).reverse().map(l => `<div class="${l.ok ? '' : 'erro'}"><b>${l.hora}</b> ${l.tipo}: ${String(l.texto).replace(/</g, '&lt;')}</div>`).join('') || '<div>(nenhuma ação ainda)</div>';
  } catch { }
}
setInterval(atualizarLog, 1500); atualizarLog();
// estado do motor: Ryker "trabalhando" + badge no HUD e na tela 3D
setInterval(async () => {
  try {
    const e = await (await fetch('/api/motor/estado')).json();
    cena.estado.trabalhando = e.trabalhando ? e.ferramenta : null;
    const b = $('trabalho'); b.style.display = e.trabalhando ? 'block' : 'none'; b.textContent = '⚙ RYKER TRABALHANDO: ' + (e.ferramenta || '');
  } catch { }
}, 700);

window.jarvis = { executar, mostrarControle, falar, cena, enviar: t => { $('entrada').value = t; $('form').requestSubmit(); } };
