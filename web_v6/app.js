// Jarvis v6 — esfera Nexus + tela grande + notebook realista. Sem avatar.
import { criarEsfera } from './esfera.js';
import { criarNotebook } from './notebook.js';
const $ = id => document.getElementById(id);
const estado = { nivel: 0, falando: false, modo: 'notebook', agir: 'notebook', controle: false, cursor: null, ultima: 0 };
const post = (url, c) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(c || {}) }).then(r => r.json());

// ---- tela usada pelo notebook 3D: espelho ao vivo ou "desktop na nuvem" ----
const telaCv = document.createElement('canvas'); telaCv.width = 1280; telaCv.height = 800; const tc = telaCv.getContext('2d');
const img = $('espelho');
function desenharTela() {
  if (img.naturalWidth && performance.now() - estado.ultima < 5000) tc.drawImage(img, 0, 0, 1280, 800);
  else {
    const g = tc.createLinearGradient(0, 0, 1280, 800); g.addColorStop(0, '#0a2a5a'); g.addColorStop(1, '#020814'); tc.fillStyle = g; tc.fillRect(0, 0, 1280, 800);
    tc.fillStyle = '#5cc8ff'; tc.font = 'bold 54px sans-serif'; tc.textAlign = 'center'; tc.fillText('JARVIS CLOUD', 640, 360);
    tc.font = '26px sans-serif'; tc.fillStyle = '#9cf'; tc.fillText('Aguardando espelho do notebook real...', 640, 410);
    tc.fillStyle = '#06203fcc'; tc.fillRect(0, 760, 1280, 40); tc.fillStyle = '#cfe8ff'; tc.font = '18px sans-serif'; tc.fillText(new Date().toLocaleTimeString(), 1200, 786);
  }
  if (estado.cursor) { tc.strokeStyle = '#f33'; tc.lineWidth = 4; tc.beginPath(); tc.arc(estado.cursor[0] * 1280, estado.cursor[1] * 800, 12, 0, 7); tc.stroke(); }
}

// ---- espelho ao vivo via WebSocket ----
function conectar() {
  const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/tela'); ws.binaryType = 'blob';
  ws.onmessage = ev => {
    if (typeof ev.data === 'string') { const m = JSON.parse(ev.data); if (m.cursor) estado.cursor = m.cursor; if ('controle' in m && m.controle !== estado.controle) mostrarControle(m.controle);
      if (m.erro) $('semTela').textContent = 'Captura indisponível: ' + m.erro; return; }
    const url = URL.createObjectURL(ev.data), velho = img.src; img.onload = () => velho && URL.revokeObjectURL(velho); img.src = url;
    estado.ultima = performance.now(); $('semTela').style.display = 'none';
  };
  ws.onclose = () => setTimeout(conectar, 1500);
}
conectar();
function clicarImg(ev, tipo) { const b = img.getBoundingClientRect(); acaoClique({ tipo, u: (ev.clientX - b.left) / b.width, v: (ev.clientY - b.top) / b.height }); }
img.addEventListener('click', e => clicarImg(e, 'clicar')); img.addEventListener('dblclick', e => clicarImg(e, 'duplo'));
img.addEventListener('contextmenu', e => { e.preventDefault(); clicarImg(e, 'direito'); });
const rotaAcao = () => estado.agir === 'direto' ? '/api/acao_direta' : '/api/acao';
async function acaoClique(a) {
  if (!estado.controle) { addMsg('j', 'Controle desligado: ligue no botão verde pra eu clicar no seu notebook.'); return; }
  pensar(`Executando ${a.tipo} em (${a.u.toFixed(2)}, ${a.v.toFixed(2)})` + (estado.agir === 'direto' ? ' — direto no PC' : ''), 60);
  let r; try { r = await post(rotaAcao(), a); } catch { r = { ok: false, erro: 'sem conexão' }; }
  pensar(r.ok ? 'Ação concluída' : 'Ação recusada: ' + r.erro, 100); atualizarLog();
  if (!r.ok && /DESLIGADO|Failsafe|emerg/i.test(r.erro || '')) mostrarControle(false);
}

// ---- 3D ----
const esfera = criarEsfera($('esfera3d'), estado), mini = criarEsfera($('mini'), estado);
const note = criarNotebook($('notebook3d'), telaCv, acaoClique);
function laco(ms) { const t = ms / 1000;
  if (!estado.falando) estado.nivel *= .9; else estado.nivel = Math.max(estado.nivel * .85, estado.alvo || 0);
  if (estado.modo === 'esfera') esfera.quadro(t); mini.quadro(t);
  if (estado.modo === 'notebook') { desenharTela(); note.quadro(); }
  ondas(t); requestAnimationFrame(laco); }
requestAnimationFrame(laco);

// ---- ondas de voz ----
const oc = $('ondas'), ox = oc.getContext('2d');
function ondas(t) { const w = oc.width = oc.clientWidth || 110, h = oc.height = oc.clientHeight || 44; ox.clearRect(0, 0, w, h);
  for (let k = 0; k < 3; k++) { ox.strokeStyle = ['#1e90ff', '#5cc8ff', '#7fffd4'][k]; ox.globalAlpha = .8 - k * .2; ox.beginPath();
    for (let x = 0; x < w; x += 2) { const a = (2 + estado.nivel * h * .4) * Math.exp(-(((x - w / 2) / (w / 3)) ** 2)); ox.lineTo(x, h / 2 + Math.sin(x * .12 + t * (4 + k) + k) * a); } ox.stroke(); } ox.globalAlpha = 1; }

// ---- modos visuais ----
document.querySelectorAll('.modos button').forEach(b => b.onclick = () => modo(b.dataset.modo));
function modo(m) { estado.modo = m; document.querySelectorAll('.modos button').forEach(b => b.classList.toggle('ativo', b.dataset.modo === m));
  $('esfera3d').style.display = m === 'esfera' ? 'block' : 'none'; $('vistaTela').classList.toggle('on', m === 'tela'); $('notebook3d').classList.toggle('on', m === 'notebook'); }
modo('notebook');
// ---- modo de AÇÃO: tela grande / notebook 3D / direto no PC ----
function agir(m) { estado.agir = m; document.querySelectorAll('.acaoModo button').forEach(x => x.classList.toggle('on', x.dataset.agir === m)); if (m !== 'direto') modo(m); }
document.querySelectorAll('.acaoModo button').forEach(b => b.onclick = () => { agir(b.dataset.agir);
  addMsg('j', estado.agir === 'direto' ? 'Modo Direto no PC: eu minimizo a interface, clico na tela real e volto.' : 'Agindo pelo modo ' + b.textContent.trim() + '.'); });
document.querySelectorAll('.qa').forEach(b => b.onclick = () => window.jarvis.enviar(b.dataset.q));

// ---- status real do sistema (psutil) ----
const barra = (id, v, txt) => { $('b' + id).style.width = (v ?? 0) + '%'; $('v' + id).textContent = txt; };
async function sistema() { try { const s = await (await fetch('/api/sistema')).json(); if (s.erro) return;
  barra('Cpu', s.cpu, s.cpu + '%'); barra('Ram', s.ram, s.ram + '%'); barra('Gpu', s.gpu, s.gpu == null ? 'n/d' : s.gpu + '%'); barra('Net', Math.min(100, s.rede_mbps * 2), s.rede_mbps + ' Mbps');
  $('iDev').textContent = s.maquina; $('iOs').textContent = s.os; const u = s.uptime_s; $('iUp').textContent = `${Math.floor(u / 86400)}d ${Math.floor(u % 86400 / 3600)}h ${Math.floor(u % 3600 / 60)}m`;
  $('iBat').textContent = s.bateria == null ? 'n/d' : s.bateria + '%'; $('anel').style.strokeDashoffset = 100.5 * (1 - (s.bateria ?? 0) / 100); } catch {} }
setInterval(sistema, 2000); sistema();
setInterval(() => $('relogio').textContent = new Date().toLocaleTimeString(), 1000);

// ---- fala: esfera/ondas reagem (por palavra no TTS + envelope simulado) ----
function falar(texto) {
  estado.falando = true; let fimT; const fim = () => { estado.falando = false; estado.alvo = 0; clearInterval(sim); clearTimeout(fimT); };
  const sim = setInterval(() => estado.alvo = .35 + Math.random() * .65, 90);
  if ($('tts').checked && 'speechSynthesis' in window) {
    const u = new SpeechSynthesisUtterance(texto); u.lang = 'pt-BR'; const v = speechSynthesis.getVoices().find(v => v.lang.startsWith('pt')); if (v) u.voice = v;
    u.onboundary = () => estado.nivel = 1; u.onend = fim; u.onerror = fim; speechSynthesis.cancel(); speechSynthesis.speak(u);
    fimT = setTimeout(fim, 1500 + texto.length * 80);
  } else fimT = setTimeout(fim, 600 + texto.length * 60);
}
window.jarvis = { falar, modo, agir, enviar: t => { $('entrada').value = t; $('form').requestSubmit(); }, estado };

// ---- chat / thinking ----
function addMsg(q, t) { const d = document.createElement('div'); d.className = q; d.textContent = (q === 'u' ? 'Você: ' : 'Jarvis: ') + t; $('chat').appendChild(d); $('chat').scrollTop = 1e9; }
function pensar(t, p) { $('pensa').textContent = t; $('barra').style.width = p + '%'; }
$('form').addEventListener('submit', async ev => { ev.preventDefault();
  const texto = $('entrada').value.trim(); if (!texto) return; $('entrada').value = ''; addMsg('u', texto);
  pensar('Thinking: analisando pedido...', 25); const tm = setTimeout(() => pensar('Thinking: planejando...', 60), 700);
  try {
    if ($('motor').checked) { const j = await post('/api/motor', { texto }); clearTimeout(tm);
      const extra = (j.passos || []).map(p => `${p.ok ? '✔' : '✖'} ${p.ferramenta}`).join(' '); addMsg('j', j.resposta + (extra ? '\n' + extra : '')); pensar('Concluído', 100); falar(j.resposta); return; }
    const { resposta, acoes } = await post('/api/chat', { texto }); clearTimeout(tm); addMsg('j', resposta); pensar('Concluído', 100); falar(resposta);
    if (acoes && estado.controle) for (const a of acoes) { const r = await post(rotaAcao(), a); atualizarLog(); if (!r.ok) break; }
  } catch { clearTimeout(tm); pensar('Erro de conexão', 0); addMsg('j', 'Falha de conexão com o núcleo Python.'); }
});
$('mic').onclick = () => { const SR = window.SpeechRecognition || window.webkitSpeechRecognition; if (!SR) return addMsg('j', 'Seu navegador não suporta reconhecimento de voz (use Chrome/Edge).');
  const r = new SR(); r.lang = 'pt-BR'; $('mic').classList.add('on'); pensar('Listening...', 10);
  r.onresult = e => window.jarvis.enviar(e.results[0][0].transcript); r.onend = () => $('mic').classList.remove('on'); r.start(); };

// ---- controle do PC (DESLIGADO por padrão) + PARAR ----
function mostrarControle(v) { estado.controle = v; const b = $('togControle'); b.classList.toggle('on', v); b.classList.toggle('off', !v);
  $('togTxt').textContent = v ? 'CONTROLE: LIGADO' : 'CONTROLE: DESLIGADO'; $('segTxt').textContent = v ? 'Controle LIGADO · PARAR disponível' : 'Controle desligado · seguro'; }
$('togControle').onclick = async () => { const quer = !estado.controle;
  if (quer && !confirm('Ligar o controle? O Jarvis vai clicar/digitar no seu PC de verdade.\nPara parar: PARAR, Esc 3x, Ctrl+Alt+Q ou mouse num canto.')) return;
  mostrarControle((await post('/api/controle', { ligado: quer })).ligado); };
async function parar() { try { speechSynthesis.cancel(); } catch {} estado.falando = false; pensar('PARADO pelo usuário', 0); mostrarControle((await post('/api/parar')).ligado); atualizarLog(); }
$('parar').onclick = parar;
let escs = []; addEventListener('keydown', ev => {
  if (ev.key === 'Escape') { const t = performance.now(); escs = escs.filter(x => t - x < 1500).concat(t); if (escs.length >= 3) { escs = []; parar(); } }
  if (ev.ctrlKey && ev.altKey && ev.key.toLowerCase() === 'q') parar(); });
async function atualizarLog() { try { const { ligado, log } = await (await fetch('/api/log')).json(); if (ligado !== estado.controle) mostrarControle(ligado);
  $('log').innerHTML = log.slice(-20).reverse().map(l => `<div class="${l.ok ? '' : 'erro'}">${l.hora} ${l.tipo}: ${String(l.texto).replace(/</g, '&lt;')}</div>`).join('') || '(nenhuma ação)'; } catch {} }
setInterval(atualizarLog, 3000); atualizarLog();
addMsg('j', 'Sistemas online. Olá, Bruno. Como posso ajudar?');
