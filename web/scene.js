// Jarvis v4 — Ryker no Quarto do Braga. A tela do ThinkPad 3D espelha a tela REAL do PC (WebSocket /ws/tela)
// e cliques/ações nela são executados no PC real (quando o controle está LIGADO).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const B = (x, y, z) => new THREE.Vector3(x, z, -y);   // coordenadas Blender (Z pra cima) -> three.js

export function criarCena(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x05080f);
  const pm = new THREE.PMREMGenerator(renderer); scene.environment = pm.fromScene(new RoomEnvironment(), .04).texture;   // reflexos PBR do notebook

  const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, .01, 50);
  const controls = new OrbitControls(camera, canvas); controls.enableDamping = true;
  controls.minDistance = .25; controls.maxDistance = 3.2; controls.autoRotateSpeed = 1.6;

  // Luzes: plafon quente, brilho azul da tela, luar pela janela, ambiente
  scene.add(new THREE.HemisphereLight(0xa8bfff, 0x2a2420, 1.1));
  const teto = new THREE.PointLight(0xffe2c0, 5, 9, 1.2); teto.position.copy(B(0, 0, 2.4)); teto.castShadow = true;
  teto.shadow.mapSize.set(1024, 1024); teto.shadow.bias = -.004; teto.shadow.normalBias = .03; scene.add(teto);
  const telaLuz = new THREE.PointLight(0x7fb8ff, 1.2, 1.6, 1.5); telaLuz.position.copy(B(-1, 1.0, 1.0)); scene.add(telaLuz);
  const preench = new THREE.DirectionalLight(0xfff0e6, .9); preench.position.copy(B(.5, -1.2, 2)); preench.target.position.copy(B(-1, .5, 1.1));
  scene.add(preench, preench.target);
  const lua = new THREE.PointLight(0x6080ff, 1.5, 3); lua.position.copy(B(.85, 1.2, 1.5)); scene.add(lua);

  const tela = criarTelaNotebook(renderer);
  const estado = { nivel: 0, falando: false, gesto: 0, modo: 'live5d', ultimas: [], cursor: null, acao: null, hover: null, controle: false };
  const R = { ossos: {}, rest: {}, morph: [] };
  let pronto = false, cam5Pos = new THREE.Vector3(-0.02, 1.62, 0.2), telaObj = null, telaC = new THREE.Vector3(), telaN = new THREE.Vector3(0, 0, 1), telaUp = new THREE.Vector3(0, 1, 0), webcamPos = B(-.76, 1.22, 1.12), cabecaPos = B(-1, .5, 1.3);

  const grad = new THREE.DataTexture(new Uint8Array([90, 90, 90, 255, 175, 175, 175, 255, 255, 255, 255, 255]), 3, 1);
  grad.minFilter = grad.magFilter = THREE.NearestFilter; grad.needsUpdate = true;
  const contorno = new THREE.MeshBasicMaterial({ color: 0x120808, side: THREE.BackSide });
  contorno.onBeforeCompile = s => { s.vertexShader = s.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n transformed += normalize(normal) * 0.0022;'); };

  new GLTFLoader().load('assets/jarvis_v5.glb', gltf => {
    const raiz = gltf.scene; const extras = [];
    raiz.traverse(o => {
      if (o.isBone) { R.ossos[o.name] = o; R.rest[o.name] = o.quaternion.clone(); }
      if (!o.isMesh) return;
      o.castShadow = true; o.receiveShadow = true;
      const m = o.material;
      if (m && m.name && m.name.startsWith('Ryker_')) {   // visual anime: toon + contorno
        const t = new THREE.MeshToonMaterial({ color: m.color, map: m.map, gradientMap: grad, name: m.name });
        if (m.emissive && m.emissive.getHex()) { t.emissive = m.emissive; t.emissiveIntensity = 1; }
        o.material = t; o.receiveShadow = false;
        if (!/Olhos|Boca|Nariz|Brilho|Emblema/.test(o.name + m.name)) extras.push(o);
      }
      if (o.morphTargetDictionary) R.morph.push(o);
      if (m && m.name === 'TelaAoVivo') { tela.textura.flipY = false; o.material = new THREE.MeshBasicMaterial({ map: tela.textura, toneMapped: false }); o.castShadow = false; o.receiveShadow = false; telaObj = o; }
      else if (m && m.name && m.name.startsWith('TP_') && m.isMeshStandardMaterial) m.envMapIntensity = .7;
      if (m && /Vidro|LuzTeto|LedBranco/.test(m.name)) o.castShadow = false;
    });
    for (const o of extras) {   // contorno "inverted hull" (funciona também na malha com ossos)
      let c;
      if (o.isSkinnedMesh) { c = new THREE.SkinnedMesh(o.geometry, contorno); c.bind(o.skeleton, o.bindMatrix); }
      else c = new THREE.Mesh(o.geometry, contorno);
      c.position.copy(o.position); c.quaternion.copy(o.quaternion); c.scale.copy(o.scale);
      if (o.morphTargetInfluences) { c.morphTargetInfluences = o.morphTargetInfluences; c.morphTargetDictionary = o.morphTargetDictionary; }
      c.castShadow = false; o.parent.add(c);
    }
    scene.add(raiz); raiz.updateMatrixWorld(true);
    const w = raiz.getObjectByName('WebcamOlho'); if (w) w.getWorldPosition(webcamPos);
    if (R.ossos.Head) { R.ossos.Head.getWorldPosition(cabecaPos); cabecaPos.y += .1; }
    gltf.scene.updateMatrixWorld(true); const o5 = gltf.scene.getObjectByName('Cam5DOlho'); console.log('cam5', !!o5); if (o5) o5.getWorldPosition(cam5Pos);
    if (telaObj) {
      scene.updateMatrixWorld(true);
      const g = telaObj.geometry, P = g.attributes.position, T = g.attributes.uv, c = {};
      for (let i = 0; i < T.count; i++) c[Math.round(T.getX(i)) + '' + Math.round(T.getY(i))] = new THREE.Vector3().fromBufferAttribute(P, i).applyMatrix4(telaObj.matrixWorld);
      const dx = c['10'].clone().sub(c['00']), dyBaixo = c['01'].clone().sub(c['00']);   // v cresce pra baixo
      telaC.copy(c['00']).addScaledVector(dx, .5).addScaledVector(dyBaixo, .5);
      telaUp.copy(dyBaixo).negate().normalize(); telaN.crossVectors(dx, telaUp).normalize();
      if (telaN.dot(cabecaPos.clone().sub(telaC)) < 0) telaN.negate();
      console.log('Tela', telaC.toArray().map(v => v.toFixed(3)), 'normal', telaN.toArray().map(v => v.toFixed(2)));
    }
    pronto = true; vista(estado.modo); console.log('Cena v5 carregada', Object.keys(R.ossos).length, 'ossos');
  }, undefined, e => console.error('Falha ao carregar GLB', e));

  const ombro = (d, up, dir, fov) => () => {
    const lado = new THREE.Vector3().crossVectors(telaUp, telaN).normalize();
    return { pos: telaC.clone().addScaledVector(telaN, d).addScaledVector(telaUp, up).addScaledVector(lado, dir), alvo: telaC.clone().addScaledVector(telaUp, -.015), fov, auto: false };
  };
  const VISTAS = {
    live5d: () => ({ pos: cam5Pos.clone(), alvo: telaC.clone().add(new THREE.Vector3(.0, .07, .3)), fov: 41, auto: false }),     // Live: câmera 5D no tripé
    medio:  () => ({ pos: cabecaPos.clone().add(new THREE.Vector3(.36, .1, .95)), alvo: telaC.clone().add(new THREE.Vector3(0, -.06, .25)), fov: 42, auto: false }), // Medium shot por trás
    close:  () => ({ pos: telaC.clone().addScaledVector(telaN, .62).addScaledVector(telaUp, .04).add(new THREE.Vector3(0, .16, 0)), alvo: telaC.clone().addScaledVector(telaUp, -.07), fov: 40, auto: false }), // tela + mãos
    ombro: ombro(1.0, .16, -.26, 26),     // por trás/por cima do ombro: tela grande e legível
    tela:  ombro(.62, .02, 0, 30),     // de frente pra tela (melhor para clicar)
    live:   () => ({ pos: webcamPos.clone(), alvo: cabecaPos.clone().add(new THREE.Vector3(.05, -.36, 0)), fov: 62, auto: false }),
    orbita: () => ({ pos: cabecaPos.clone().add(new THREE.Vector3(.9, .1, -.9)), alvo: cabecaPos.clone().add(new THREE.Vector3(0, -.3, 0)), fov: 55, auto: true }),
    quarto: () => ({ pos: B(-1.25, -1.35, 1.8), alvo: B(-.3, .6, .8), fov: 70, auto: false }),
    rosto:  () => ({ pos: cabecaPos.clone().add(new THREE.Vector3(.16, -.03, -.45)), alvo: cabecaPos.clone().add(new THREE.Vector3(0, -.04, 0)), fov: 35, auto: false }),
  };
  function vista(nome) {
    if (typeof nome === 'number') nome = Object.keys(VISTAS)[nome];
    estado.modo = nome; const v = VISTAS[nome]();
    camera.position.copy(v.pos); controls.target.copy(v.alvo); camera.fov = v.fov; camera.updateProjectionMatrix();
    controls.autoRotate = v.auto; controls.update();
  }
  vista('live5d');

  addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });

  const E = new THREE.Euler(), Q = new THREE.Quaternion();
  function gira(nome, x = 0, y = 0, z = 0) {
    const o = R.ossos[nome]; if (!o) return;
    o.quaternion.copy(R.rest[nome]).multiply(Q.setFromEuler(E.set(x, y, z)));
  }
  // dedos com ossos separados (Finger0..3): leve defasagem entre eles = movimento natural
  function dedos(L, v, y = 0) { for (let f = 0; f < 4; f++) gira(`Finger${f}_${L}`, v * (1 + (f - 1.5) * .12), y); }
  function morph(nome, v) { for (const m of R.morph) { const i = m.morphTargetDictionary[nome]; if (i !== undefined) m.morphTargetInfluences[i] = v; } }

  let piscarAte = 0, proxPiscar = 2;
  function animar(t, dt) {
    const n = estado.nivel, f = estado.falando;
    estado.gesto += ((f ? 1 : 0) - estado.gesto) * Math.min(1, dt * 3); const g = estado.gesto;
    // respiração
    const resp = Math.sin(t * 1.7);
    gira('Spine', resp * .012); gira('Chest', resp * .018 - g * .05, Math.sin(t * .9) * g * .06);
    // cabeça: olha a tela digitando; falando, olha pra webcam e acena
    gira('Neck', .05 * (1 - g) + Math.sin(t * .6) * .02, -g * .1);
    gira('Head', (1 - g) * .12 + g * (Math.sin(t * 4.2) * .05 + n * .06) - .04, -g * .32 + Math.sin(t * .45) * .06 + g * Math.sin(t * 1.3) * .08, g * Math.sin(t * 1.1) * .05);
    // digitando (dedos e mãos), que para quando ele gesticula
    for (const [L, ph] of [['L', 0], ['R', 1.7]]) {
      const tp = Math.max(0, Math.sin(t * (estado.trabalhando ? 24 : 13) + ph)) * Math.max(0, Math.sin(t * 2.1 + ph * 2));
      const k = L === 'R' ? 1 - g : 1 - g * .5;
      dedos(L, tp * .35 * k);
      gira('Hand_' + L, -tp * .08 * k);
    }
    // ação no PC: a mão direita vai pro touchpad/TrackPoint e o dedo "clica" em sincronia com o cursor 3D
    const A = estado.acao;
    if (A) {
      const p = Math.min(1, (performance.now() - A.t0) / A.dur), e = p < .5 ? 2 * p * p : 1 - (-2 * p + 2) ** 2 / 2;
      if (A.de && A.para) estado.cursor = [A.de[0] + (A.para[0] - A.de[0]) * e, A.de[1] + (A.para[1] - A.de[1]) * e];
      const ux = (estado.cursor ? estado.cursor[0] : .5) - .5, vy = (estado.cursor ? estado.cursor[1] : .5) - .5;
      gira('UpperArm_R', 0, 0, 0); gira('UpperArm_L', 0, 0, 0); gira('ForeArm_L', 0); gira('ForeArm_R', -.05, ux * .25, 0); gira('Hand_R', -.05 + vy * .12, ux * .35);
      dedos('R', A.tipo === 'digitar' ? Math.max(0, Math.sin(t * 22)) * .4 : (p > .85 ? .45 : .1));
      dedos('L', A.tipo === 'digitar' ? Math.max(0, Math.sin(t * 22 + 1.5)) * .4 : 0);
      gira('Head', .16, -ux * .15, 0);
      if (p >= 1 && !A.feito) { A.feito = true; A.resolve(); }
      return;
    }
    // gestos ao falar: mão direita sobe e gesticula, esquerda acompanha de leve
    const gs = Math.sin(t * 2.4), gs2 = Math.sin(t * 1.3 + 1);
    gira('UpperArm_R', g * (.12 + gs2 * .06), 0, -g * (.25 + gs * .06));
    gira('ForeArm_R', g * (.42 + gs * .15), g * .35);
    gira('Hand_R', g * gs * .3, g * .6);
    gira('UpperArm_L', g * .15 * Math.max(0, gs2), 0, 0); gira('ForeArm_L', g * .25 * Math.max(0, gs2));
    // piscar
    if (t > proxPiscar) { piscarAte = t + .13; proxPiscar = t + 2 + Math.random() * 3.5; }
    morph('Piscar', t < piscarAte ? 1 : 0);
    morph('Fala', Math.min(1, n * 1.2));
  }

  const relogio = new THREE.Clock();
  (function loop() {
    requestAnimationFrame(loop);
    const dt = relogio.getDelta(), t = relogio.elapsedTime;
    if (pronto) animar(t, dt);
    tela.desenhar(t, estado);
    controls.update(); renderer.render(scene, camera);
  })();
  // ---------- espelho da tela real ----------
  function conectarTela() {
    const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/tela');
    ws.binaryType = 'blob';
    ws.onmessage = async ev => {
      if (typeof ev.data === 'string') {
        const m = JSON.parse(ev.data); if (m.erro) tela.erro = m.erro;
        if (m.cursor && !estado.acao) estado.cursor = m.cursor; if (m.tela) tela.geo = m.tela; estado.controle = !!m.controle;
        return;
      }
      try { tela.frame(await createImageBitmap(ev.data)); } catch (e) { }
    };
    ws.onclose = () => { tela.erro = 'Reconectando à captura...'; setTimeout(conectarTela, 1500); };
  }
  conectarTela();

  // ---------- clique/hover direto na tela 3D ----------
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function uvDoPonteiro(ev) {
    if (!telaObj) return null;
    const r = canvas.getBoundingClientRect(); ndc.set((ev.clientX - r.left) / r.width * 2 - 1, -(ev.clientY - r.top) / r.height * 2 + 1);
    ray.setFromCamera(ndc, camera); const h = ray.intersectObject(telaObj)[0];
    return h && h.uv ? [h.uv.x, h.uv.y] : null;
  }
  let down = null; const ouvintes = [];
  canvas.addEventListener('pointerdown', ev => { down = [ev.clientX, ev.clientY, ev.button]; });
  canvas.addEventListener('pointermove', ev => { estado.hover = uvDoPonteiro(ev); canvas.style.cursor = estado.hover ? 'crosshair' : ''; });
  canvas.addEventListener('pointerup', ev => {
    if (!down || Math.hypot(ev.clientX - down[0], ev.clientY - down[1]) > 6) return;
    const uv = uvDoPonteiro(ev); if (uv) ouvintes.forEach(f => f({ tipo: down[2] === 2 ? 'direito' : 'clicar', u: uv[0], v: uv[1] }));
  });
  canvas.addEventListener('dblclick', ev => { const uv = uvDoPonteiro(ev); if (uv) ouvintes.forEach(f => f({ tipo: 'duplo', u: uv[0], v: uv[1] })); });
  canvas.addEventListener('contextmenu', ev => { if (uvDoPonteiro(ev)) ev.preventDefault(); });

  // anima o Ryker + cursor 3D até o alvo; resolve quando a mão "clica"
  function animarAcao(a) {
    return new Promise(resolve => {
      const para = a.u !== undefined ? [a.u, a.v] : null;
      const dur = a.tipo === 'digitar' ? Math.min(4000, 500 + (a.texto || '').length * 45) : para ? 700 : 450;
      estado.acao = { tipo: a.tipo, t0: performance.now(), dur, de: estado.cursor || [.5, .5], para, resolve };
    }).then(() => { if (a.u !== undefined) tela.clique(a.u, a.v); });
  }
  function fimAcao() { estado.acao = null; }
  // posição na janela do navegador de um ponto (u,v) da tela 3D (usado nos testes)
  function pontoNaJanela(u, v) {
    // interpola pelos cantos de UV da malha da Tela (independe do eixo local exportado)
    const g = telaObj.geometry, P = g.attributes.position, T = g.attributes.uv, c = {};
    for (let i = 0; i < T.count; i++) c[Math.round(T.getX(i)) + '' + Math.round(T.getY(i))] = new THREE.Vector3().fromBufferAttribute(P, i);
    const p = c['00'].clone().addScaledVector(c['10'].clone().sub(c['00']), u).addScaledVector(c['01'].clone().sub(c['00']), v);
    telaObj.localToWorld(p); p.project(camera);
    return [(p.x + 1) / 2 * innerWidth, (1 - p.y) / 2 * innerHeight];
  }
  return { estado, vista, renderer, camera, R, animarAcao, fimAcao, aoClicarTela: f => ouvintes.push(f), pontoNaJanela };
}

function criarTelaNotebook(renderer) {
  const W = 1920, H = 1080;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const c = cv.getContext('2d'); const textura = new THREE.CanvasTexture(cv);
  textura.colorSpace = THREE.SRGBColorSpace; textura.anisotropy = renderer.capabilities.getMaxAnisotropy();
  textura.minFilter = THREE.LinearMipmapLinearFilter; textura.generateMipmaps = true;
  let quadro = null, cliques = [], ultimo = -1;
  const api = {
    textura, erro: null, geo: null,
    frame(bmp) { if (quadro && quadro.close) quadro.close(); quadro = bmp; api.erro = null; },
    clique(u, v) { cliques.push({ u, v, t: performance.now() }); },
    desenhar(t, e) {
      const q = Math.floor(t * 30); if (q === ultimo) return; ultimo = q;
      if (quadro) c.drawImage(quadro, 0, 0, W, H);
      else {
        c.fillStyle = '#0a1f5c'; c.fillRect(0, 0, W, H); c.fillStyle = '#fff'; c.font = 'bold 54px sans-serif'; c.textAlign = 'center';
        c.fillText('Aguardando a tela do seu PC...', W / 2, H / 2); c.font = '32px sans-serif'; c.fillText(api.erro || 'captura via mss (app/captura.py)', W / 2, H / 2 + 60); c.textAlign = 'left';
      }
      // hover do usuário: anel bem visível onde o clique vai cair
      if (e.hover) { const [x, y] = [e.hover[0] * W, e.hover[1] * H];
        c.lineWidth = 6; c.strokeStyle = e.controle ? '#33ff77' : '#ffcc00'; c.beginPath(); c.arc(x, y, 34, 0, 7); c.stroke();
        c.beginPath(); c.moveTo(x - 50, y); c.lineTo(x - 20, y); c.moveTo(x + 20, y); c.lineTo(x + 50, y); c.moveTo(x, y - 50); c.lineTo(x, y - 20); c.moveTo(x, y + 20); c.lineTo(x, y + 50); c.stroke(); }
      // ondas de clique
      const agora = performance.now(); cliques = cliques.filter(k => agora - k.t < 700);
      for (const k of cliques) { const p = (agora - k.t) / 700; c.strokeStyle = `rgba(255,40,40,${1 - p})`; c.lineWidth = 10; c.beginPath(); c.arc(k.u * W, k.v * H, 20 + p * 70, 0, 7); c.stroke(); }
      // cursor 3D grande (posição real do mouse ou animação do Ryker)
      if (e.cursor) {
        const [x, y] = [e.cursor[0] * W, e.cursor[1] * H], s = 2.2;
        c.save(); c.translate(x, y); c.scale(s, s); c.beginPath();
        c.moveTo(0, 0); c.lineTo(0, 22); c.lineTo(5.5, 17); c.lineTo(9.5, 26); c.lineTo(13, 24.5); c.lineTo(9, 16); c.lineTo(16, 16); c.closePath();
        c.fillStyle = '#fff'; c.fill(); c.lineWidth = 1.6; c.strokeStyle = '#000'; c.stroke(); c.restore();
        if (e.acao) { c.fillStyle = 'rgba(255,40,40,.9)'; c.font = 'bold 30px sans-serif'; c.fillText('RYKER', x + 40, y + 70); }
      }
      if (e.trabalhando) { c.fillStyle = 'rgba(255,176,0,.92)'; c.fillRect(40, H - 110, 900, 70); c.fillStyle = '#000'; c.font = 'bold 40px sans-serif'; c.fillText('⚙ Jarvis: ' + e.trabalhando, 60, H - 60); }
      // faixa de estado do controle, bem visível
      c.fillStyle = e.controle ? 'rgba(0,160,70,.85)' : 'rgba(170,0,0,.85)'; c.fillRect(W - 560, 40, 456, 52);
      c.fillStyle = '#fff'; c.font = 'bold 30px sans-serif'; c.fillText(e.controle ? '● JARVIS CONTROLANDO O PC' : '■ CONTROLE DESLIGADO', W - 542, 77);
      textura.needsUpdate = true;
    },
  };
  return api;
}
