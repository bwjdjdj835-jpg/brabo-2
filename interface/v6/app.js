// Jarvis 2 (visual v6): esfera Nexus + tela grande + notebook realista, ligado ao Braga (app.py) pela ponte do
// pywebview (pywebview.api). O cérebro, a voz, o microfone e o controle do PC são os do Braga:
// - a tela grande e o notebook 3D mostram a tela do PC ao vivo (mini notebook do Braga);
// - clicar nelas clica no PC de verdade, só com o CONTROLE ligado; PARAR, Esc×3 e Ctrl+Alt+Q param tudo.
import { criarEsfera } from './esfera.js';
import { criarNotebook } from './notebook.js';
const $ = id => document.getElementById(id);
const api = () => window.pywebview && window.pywebview.api;
const estado = { nivel: 0, alvo: 0, falando: false, modo: 'notebook', agir: 'notebook', controle: false, cursor: null, fps: 0 };

// ---- tela do PC ao vivo: só o visual que está na frente recebe os quadros (esfera = captura parada) ----
const img = $('espelho');
let nbInfo = null, navInfo = null, miniTela = false, numeroQuadro = '', buscando = false, quadrosEspelho = 0;
async function buscarQuadro() {
  if (buscando || document.hidden || estado.modo === 'esfera' || !api() || !api().notebook_info) return;
  buscando = true;
  try {
    if (!nbInfo) nbInfo = await api().notebook_info();
    const info = miniTela ? (navInfo || (navInfo = await api().navegador_info())) : nbInfo;
    const r = await fetch(`${info.quadro}?n=${numeroQuadro}&t=${Date.now()}`, { cache: 'no-store' });
    if (r.ok) {
      numeroQuadro = r.headers.get('X-Quadro') || '';
      if (r.status === 200) {
        const blob = await r.blob(); quadrosEspelho++;
        if (estado.modo === 'notebook') note.frame(await createImageBitmap(blob, { resizeWidth: 960, resizeHeight: 600, resizeQuality: 'medium' }));
        else { const url = URL.createObjectURL(blob), velho = img.src; img.onload = () => velho.startsWith('blob:') && URL.revokeObjectURL(velho); img.src = url; }
        $('semTela').style.display = 'none';
      }
    } else $('semTela').textContent = 'Captura da tela indisponível agora';
  } catch (_) {}
  buscando = false;
}
function clicarImg(ev, tipo) { const b = img.getBoundingClientRect(); acaoClique({ tipo, u: (ev.clientX - b.left) / b.width, v: (ev.clientY - b.top) / b.height }); }
img.addEventListener('click', e => clicarImg(e, 'clicar')); img.addEventListener('dblclick', e => clicarImg(e, 'duplo'));
img.addEventListener('contextmenu', e => { e.preventDefault(); clicarImg(e, 'direito'); });
async function acaoClique(a) {
  if (!estado.controle) { addMsg('j', 'Controle desligado: ligue no botão verde pra eu clicar no seu notebook.'); return; }
  pensar(`Executando ${a.tipo} em (${a.u.toFixed(2)}, ${a.v.toFixed(2)})`, 60);
  note.clique(a.u, a.v);
  let r;
  try {
    if (miniTela) {   // navegador do Braga: clique dentro dele, não no PC
      const L = (navInfo && navInfo.largura) || 1280, A = (navInfo && navInfo.altura) || 800;
      for (let i = a.tipo === 'duplo' ? 2 : 1; i > 0; i--) await api().navegador_acao('clicar', a.u * L, a.v * A);
      r = {};
    } else r = await api().notebook_acao(a.tipo, a.u, a.v, null);   // o clique atravessa a janela e cai no programa de trás
  } catch { r = { erro: 'sem conexão' }; }
  pensar(r && r.erro ? 'Ação recusada: ' + r.erro : 'Ação concluída', 100);
  if (r && r.erro && /fail|canto|safe/i.test(r.erro)) mostrarControle(false);   // freio do canto: tudo desligado
}

// ---- 3D (até 30 quadros por segundo; a bolinha do topo, 15) ----
const esfera = criarEsfera($('esfera3d'), estado), mini = criarEsfera($('mini'), estado);
const note = criarNotebook($('notebook3d'), acaoClique);
let ultimo = 0, ultimoMini = 0, contagem = 0, inicioJanela = performance.now();
function laco(ms) {
  requestAnimationFrame(laco);
  if (document.hidden || ms - ultimo < 28) return;
  ultimo = ms; const t = ms / 1000;
  if (!estado.falando) estado.nivel *= .9; else estado.nivel = Math.max(estado.nivel * .85, estado.alvo || 0);
  if (estado.modo === 'esfera') esfera.quadro(t);
  if (ms - ultimoMini > 66) { ultimoMini = ms; mini.quadro(t); }
  if (estado.modo === 'notebook') note.quadro();
  ondas(t);
  contagem++; if (ms - inicioJanela > 2000) { estado.fps = Math.round(contagem * 1000 / (ms - inicioJanela)); contagem = 0; inicioJanela = ms; }
}
requestAnimationFrame(laco);

// ---- ondas de voz ----
const oc = $('ondas'), ox = oc.getContext('2d');
function ondas(t) { const w = oc.width = oc.clientWidth || 110, h = oc.height = oc.clientHeight || 44; ox.clearRect(0, 0, w, h);
  for (let k = 0; k < 3; k++) { ox.strokeStyle = ['#1e90ff', '#5cc8ff', '#7fffd4'][k]; ox.globalAlpha = .8 - k * .2; ox.beginPath();
    for (let x = 0; x < w; x += 2) { const a = (2 + estado.nivel * h * .4) * Math.exp(-(((x - w / 2) / (w / 3)) ** 2)); ox.lineTo(x, h / 2 + Math.sin(x * .12 + t * (4 + k) + k) * a); } ox.stroke(); } ox.globalAlpha = 1; }

// ---- modos visuais ----
document.querySelectorAll('.modos button').forEach(b => b.onclick = () => modo(b.dataset.modo));
function modo(m) { estado.modo = m; numeroQuadro = ''; document.querySelectorAll('.modos button').forEach(b => b.classList.toggle('ativo', b.dataset.modo === m));
  $('esfera3d').style.display = m === 'esfera' ? 'block' : 'none'; $('vistaTela').classList.toggle('on', m === 'tela'); $('notebook3d').classList.toggle('on', m === 'notebook'); }
modo('notebook');
// ---- modo de AÇÃO: tela grande / notebook 3D / direto no PC ----
function agir(m) { estado.agir = m; document.querySelectorAll('.acaoModo button').forEach(x => x.classList.toggle('on', x.dataset.agir === m)); if (m !== 'direto') modo(m); }
document.querySelectorAll('.acaoModo button').forEach(b => b.onclick = () => { agir(b.dataset.agir);
  addMsg('j', estado.agir === 'direto' ? 'Modo Direto no PC: o clique atravessa a minha janela e cai no programa que está atrás dela.' : 'Agindo pelo modo ' + b.textContent.trim() + '.'); });
document.querySelectorAll('.qa').forEach(b => b.onclick = () => enviar(b.dataset.q));

// ---- status real do sistema (o mesmo do Braga) ----
const barra = (id, v, txt) => { $('b' + id).style.width = (v ?? 0) + '%'; $('v' + id).textContent = txt; };
async function sistema() {
  if (document.hidden || !api() || !api().status) return;
  try { const s = await api().status(), d = s.detalhes || {};
    barra('Cpu', s.cpu, s.cpu + '%'); barra('Ram', s.ram, s.ram + '%'); barra('Gpu', s.gpu, s.gpu == null ? 'n/d' : s.gpu + '%');
    barra('Net', Math.min(100, (s.rede_mbps || 0) * 2), (s.rede_mbps ?? 0) + ' Mbps');
    $('iDev').textContent = s.maquina || '--'; $('iOs').textContent = s.os || '--';
    const u = (d.uptime_h || 0) * 3600; $('iUp').textContent = `${Math.floor(u / 86400)}d ${Math.floor(u % 86400 / 3600)}h ${Math.floor(u % 3600 / 60)}m`;
    $('iBat').textContent = s.bateria == null ? 'n/d' : s.bateria + '%' + (s.carregando ? ' ⚡' : ''); $('anel').style.strokeDashoffset = 100.5 * (1 - (s.bateria ?? 0) / 100);
    $('modelo').textContent = s.claude ? 'Claude · cérebro do Braga' : 'IA de reserva (Claude indisponível)';
  } catch {} }
setInterval(() => $('relogio').textContent = new Date().toLocaleTimeString(), 1000);

// ---- fala: a voz do Braga (edge-tts) tocada aqui; esfera e ondas seguem o volume ----
let ctx = null, analisador = null, dados = null, medindo = false, audioAtual = null;
function audioCtx() {
  if (!ctx) { ctx = new AudioContext(); analisador = ctx.createAnalyser(); analisador.fftSize = 512; dados = new Uint8Array(analisador.fftSize); analisador.connect(ctx.destination); }
  return ctx;
}
async function tocar(b64) {
  let terminou = false;
  const fim = () => { if (terminou) return; terminou = true; estado.falando = false; estado.alvo = 0; medindo = false; audioAtual = null; try { api().fim_fala(); } catch (_) {} };
  if (!$('tts').checked) { estado.falando = true; setTimeout(fim, 1200); return; }   // voz desligada: só a animação
  const audio = audioAtual = new Audio('data:audio/mpeg;base64,' + b64);
  audio.onended = fim; audio.onerror = fim;
  try {
    const c = audioCtx();
    if (c.state !== 'running') await Promise.race([c.resume(), new Promise(r => setTimeout(r, 300))]).catch(() => {});
    if (c.state === 'running') { c.createMediaElementSource(audio).connect(analisador); medindo = true; }
  } catch (_) { medindo = false; }
  estado.falando = true;
  try { await audio.play(); } catch (_) { fim(); }
}
setInterval(() => {
  if (!estado.falando) return;
  if (medindo) { analisador.getByteTimeDomainData(dados); let s = 0; for (const v of dados) s += (v - 128) * (v - 128); estado.alvo = Math.min(1, Math.sqrt(s / dados.length) / 40); }
  else estado.alvo = .35 + Math.random() * .65;
}, 60);
function bip() {
  try { const c = audioCtx(), o = c.createOscillator(), g = c.createGain();
    o.frequency.setValueAtTime(880, c.currentTime); o.frequency.linearRampToValueAtTime(1320, c.currentTime + .12);
    g.gain.setValueAtTime(.15, c.currentTime); g.gain.exponentialRampToValueAtTime(.001, c.currentTime + .18);
    o.connect(g).connect(c.destination); o.start(); o.stop(c.currentTime + .2); } catch (_) {}
}

// ---- funções chamadas pelo Python (jarvis._ui); as que este visual não tem são ignoradas ----
const NOMES = { ouvindo: 'Como posso ajudar?', escutando: 'Listening... pode falar', pensando: 'Thinking: analisando pedido...', falando: 'Respondendo...',
  pausado: 'Microfone pausado', 'sem-microfone': 'Microfone indisponível', offline: 'Offline' };
let trabalhando = false;
const funcoes = {
  estado(s) { if (!trabalhando || s !== 'pensando') pensar(NOMES[s] || s, { pensando: 40, escutando: 10, falando: 90 }[s] || 0); $('mic').classList.toggle('on', s === 'escutando'); },
  voceDisse(t) { addMsg('u', t); },
  ouviu(t) { pensar('Ouvi: ' + t, 15); },
  falaTexto(t) { addMsg('j', t); },
  tocarAudio(b64) { tocar(b64); },
  micEstado(l) { $('micLigado').checked = !!l; },
  bip() { bip(); },
  aviso(t) { addMsg('j', t); },
  nota(t) { addMsg('j', t); },
  comandoProposto(frases, descricao) { addMsg('j', `Comando novo: "${(frases || []).join('" / "')}" — ${descricao || ''}`); },
  atividade(t) { pensar(t, 60); },
  tarefa(titulo, pedido) { trabalhando = !!titulo; if (trabalhando) pensar(`${titulo}${pedido ? ': ' + pedido : ''}`, 30); else { pensar('Concluído', 100); miniTelaFonte(false); } },
  abrirNotebook(f) { miniTelaFonte(f === 'navegador'); modo('notebook'); },
  abrirNavegador() { miniTelaFonte(true); if (estado.modo === 'esfera') modo('tela'); addMsg('j', 'Mini tela do navegador na tela grande/notebook. Ligue o controle para clicar nela.'); },
  fecharNavegador() { miniTelaFonte(false); },
  abrirAba(titulo, url) { $('aba-titulo').textContent = titulo || ''; $('aba-frame').src = url; $('aba').hidden = false; },
  fecharAba() { $('aba').hidden = true; $('aba-frame').src = 'about:blank'; },
  parado(motivo) { pararAudio(); mostrarControle(false); pensar('PARADO: ' + (motivo || 'emergência'), 0); },
};
window.jarvis = new Proxy(funcoes, { get: (alvo, nome) => alvo[nome] || (() => {}) });
function miniTelaFonte(sim) {
  if (sim === miniTela) return;
  miniTela = sim; numeroQuadro = ''; navInfo = null;
  if (sim) { try { api().navegador_acao('estado'); } catch (_) {} }   // liga o navegador do Braga, se estiver desligado
  try { api().contexto_interface(sim ? 'navegador' : 'jarvis', ''); } catch (_) {}
}
$('aba-fechar').onclick = () => funcoes.fecharAba();

// ---- chat / thinking ----
function addMsg(q, t) { const d = document.createElement('div'); d.className = q; d.textContent = (q === 'u' ? 'Você: ' : 'Jarvis: ') + t; $('chat').appendChild(d);
  while ($('chat').children.length > 80) $('chat').firstChild.remove(); $('chat').scrollTop = 1e9; }
function pensar(t, p) { $('pensa').textContent = t; $('barra').style.width = p + '%'; }
function enviar(texto) { try { api().comando_texto(texto); } catch (_) { addMsg('j', 'Falha de conexão com o núcleo do Braga.'); } }
$('form').addEventListener('submit', ev => { ev.preventDefault(); const texto = $('entrada').value.trim(); if (!texto) return; $('entrada').value = ''; enviar(texto); });
$('mic').onclick = () => { try { api().ouvir_agora(); } catch (_) {} };
$('micLigado').onchange = async () => { try { $('micLigado').checked = await api().alternar_microfone(); } catch (_) {} };

// ---- controle do PC (DESLIGADO por padrão) + PARAR ----
function mostrarControle(v) { estado.controle = v; const b = $('togControle'); b.classList.toggle('on', v); b.classList.toggle('off', !v);
  $('togTxt').textContent = v ? 'CONTROLE: LIGADO' : 'CONTROLE: DESLIGADO'; $('segTxt').textContent = v ? 'Controle LIGADO · PARAR disponível' : 'Controle desligado · seguro'; }
$('togControle').onclick = () => { const quer = !estado.controle;
  if (quer && !confirm('Ligar o controle? Clicar na tela grande ou no notebook 3D vai clicar no seu PC de verdade.\nPara parar: PARAR, Esc 3x, Ctrl+Alt+Q ou mouse num canto.')) return;
  mostrarControle(quer); };
function pararAudio() { if (audioAtual) { audioAtual.pause(); audioAtual.onended && audioAtual.onended(); } estado.falando = false; }
async function parar(motivo) { pararAudio(); mostrarControle(false); pensar('PARADO: ' + motivo, 0); try { await api().notebook_acao('parar'); } catch (_) {} }
$('parar').onclick = () => parar('botão PARAR');
let escs = []; addEventListener('keydown', ev => {
  if (ev.key === 'Escape') { const t = performance.now(); escs = escs.filter(x => t - x < 1500).concat(t); if (escs.length >= 3) { escs = []; parar('Esc×3'); } }
  if (ev.ctrlKey && ev.altKey && ev.key.toLowerCase() === 'q') parar('Ctrl+Alt+Q');
  if (ev.key === 'F11') { ev.preventDefault(); try { api().tela_cheia(); } catch (_) {} }
  if (ev.code === 'Space' && document.activeElement !== $('entrada')) { ev.preventDefault(); try { api().ouvir_agora(); } catch (_) {} } });

// ---- log de ações e cursor (registro do mini notebook do Braga) ----
let acoesVistas = '';
async function lerEstado() {
  if (document.hidden || estado.modo === 'esfera' || !api() || !api().notebook_estado) return;
  let s; try { s = await api().notebook_estado(); } catch (_) { return; }
  if (s.cursor && !miniTela) note.cursor(s.cursor);
  const acoes = s.acoes || [], marca = acoes.length ? acoes[0].hora + acoes[0].texto : '';
  if (marca === acoesVistas) return;
  for (const a of acoes) { if (a.hora + a.texto === acoesVistas) break; if (/^(Clique|Senhor: (clicar|duplo|direito))/.test(a.texto) && s.cursor) note.clique(...s.cursor); }
  acoesVistas = marca;
  $('log').innerHTML = '';
  for (const a of acoes.slice(0, 20)) { const d = document.createElement('div'); if (/Parad|freio|Falha|erro/i.test(a.texto)) d.className = 'erro'; d.textContent = `${a.hora} ${a.texto}`; $('log').append(d); }
}

// ---- desempenho no jarvis.log e fotos de conferência (só com %TEMP%\ryker_fotos\PEDIR) ----
function relatarDesempenho() {
  if (document.hidden || !estado.fps) return;
  try { api().desempenho_js(`Jarvis 2: ${estado.fps} quadros/s, visual ${estado.modo}, espelho ${(quadrosEspelho / 60).toFixed(1)} quadros/s`); } catch (_) {}
  quadrosEspelho = 0;
}
async function fotosDeTeste() {
  try { if (!api() || !(await api().fotos_pedidas())) return; } catch (_) { return; }
  const espera = ms => new Promise(r => setTimeout(r, ms));
  for (const m of ['notebook', 'tela', 'esfera']) {
    modo(m); await espera(2500);
    try {
      const cv = m === 'esfera' ? $('esfera3d') : null;
      const foto = m === 'notebook' ? note.foto() : m === 'esfera' ? (esfera.quadro(performance.now() / 1000), cv.toDataURL('image/jpeg', .8)) : null;
      if (foto) await api().foto_js('v6_' + m, foto);
    } catch (_) {}
  }
  modo('notebook');
}

// ---- início ----
addEventListener('error', e => { try { api().erro_js(`Jarvis 2: ${e.message} (linha ${e.lineno})`); } catch (_) {} });
function iniciar() {
  if (iniciar.feito || !api() || !api().pronto) return;
  iniciar.feito = true;
  sistema(); setInterval(sistema, 2000);
  setInterval(buscarQuadro, 90);
  setInterval(lerEstado, 300);
  setInterval(relatarDesempenho, 60000);
  setTimeout(fotosDeTeste, 6000);
  api().pronto();
}
addEventListener('pywebviewready', iniciar);
iniciar();
window.jarvisV6 = { estado, modo, agir, enviar };   // para testes pelo console
