// Notebook realista estilo ThinkPad preto; a tela recebe o espelho ao vivo do PC.
// Leve para o vídeo Intel: a tela só é reenviada à placa quando chega um quadro novo (~9 por segundo, em 960x600),
// e o cursor/cliques ficam numa camada transparente pequena, redesenhada só quando mudam.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
export function criarNotebook(canvas, aoClicar) {
  const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true }); r.toneMapping = THREE.ACESFilmicToneMapping; r.setPixelRatio(1);
  const cena = new THREE.Scene();
  cena.environment = new THREE.PMREMGenerator(r).fromScene(new RoomEnvironment(), .04).texture;
  const cam = new THREE.PerspectiveCamera(38, 1, .01, 50); cam.position.set(0, .22, .5);
  const ctl = new OrbitControls(cam, canvas); ctl.target.set(0, .08, -.03); ctl.enableDamping = true; ctl.minDistance = .3; ctl.maxDistance = 1.6;
  cena.add(new THREE.HemisphereLight(0x8fbfff, 0x101020, .6)); const sol = new THREE.DirectionalLight(0xffffff, 1.4); sol.position.set(.5, 1, .6); cena.add(sol);
  const mat = new THREE.MeshStandardMaterial({ color: 0x0b0b0d, roughness: .6, metalness: .1, envMapIntensity: .25 });
  const W = .34, D = .235;
  const base = new THREE.Mesh(new THREE.BoxGeometry(W, .018, D), mat); base.position.y = .009; cena.add(base);
  // teclado: teclas em InstancedMesh + rótulos
  const linhas = ['ESC F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 DEL', '` 1 2 3 4 5 6 7 8 9 0 - = ⌫', 'TAB Q W E R T Y U I O P [ ] \\', 'CAPS A S D F G H J K L Ç ~ ENTER', 'SHIFT Z X C V B N M , . ; SHIFT', 'FN CTRL WIN ALT ESPAÇO ALT PRT CTRL'];
  const largura = { '⌫': 1.8, TAB: 1.4, CAPS: 1.7, ENTER: 2.1, SHIFT: 2.2, 'ESPAÇO': 5.6, '\\': 1.3 };
  const u = .0182, teclas = [];
  linhas.forEach((l, li) => { const ks = l.split(' '); const tot = ks.reduce((a, k) => a + (largura[k] || 1), 0); let x = -tot * u / 2;
    ks.forEach(k => { const w = (largura[k] || 1) * u; teclas.push({ k, x: x + w / 2, z: -.085 + li * u * (li ? 1 : .8), w: w - .002, h: li ? u - .002 : u * .7 }); x += w; }); });
  const lbl = document.createElement('canvas'); lbl.width = 2048; lbl.height = 1024; const c = lbl.getContext('2d');
  c.fillStyle = '#1d1d20'; c.fillRect(0, 0, 2048, 1024);
  const kx = x => (x / W + .5) * 2048, kz = z => (z / D + .5) * 1024;
  c.textAlign = 'center'; c.textBaseline = 'middle';
  teclas.forEach(t => { const px = kx(t.x), pz = kz(t.z), pw = t.w / W * 2048, ph = t.h / D * 1024;
    c.fillStyle = '#0c0c0e'; c.fillRect(px - pw / 2, pz - ph / 2, pw, ph); c.fillStyle = '#e8e8e8'; c.font = `bold ${t.k.length > 2 ? 15 : 22}px sans-serif`; c.fillText(t.k, px, pz); });
  c.fillStyle = '#d00'; c.beginPath(); c.arc(kx(0.0005), kz(-.085 + 3.5 * u), 9, 0, 7); c.fill();
  c.fillStyle = '#0c0c0e'; c.fillRect(kx(-.05), kz(.06), .1 / W * 2048, .055 / D * 1024); // touchpad
  c.fillStyle = '#2a2a2e'; [-1, 0, 1].forEach(i => c.fillRect(kx(-.03 + i * .02 + .02) - 38, kz(.052) - 10, 76, 20));
  c.fillStyle = '#c0c0c0'; c.font = 'italic bold 28px sans-serif'; c.fillText('ThinkPad', kx(.13), kz(.1));
  const tampo = new THREE.Mesh(new THREE.PlaneGeometry(W - .004, D - .004), new THREE.MeshStandardMaterial({ map: new THREE.CanvasTexture(lbl), color: 0x8a8a8a, roughness: .7, envMapIntensity: .2 }));
  tampo.rotation.x = -Math.PI / 2; tampo.position.y = .0185; cena.add(tampo);
  const trackpoint = new THREE.Mesh(new THREE.CylinderGeometry(.0028, .0028, .006, 16), new THREE.MeshStandardMaterial({ color: 0xcc0000, roughness: .9 }));
  trackpoint.position.set(.0005, .021, -.085 + 3.5 * u); cena.add(trackpoint);
  // tampa + tela
  const tampa = new THREE.Group(); tampa.position.set(0, .018, -D / 2 + .004); tampa.rotation.x = -.22; cena.add(tampa);
  const H = .225; const casca = new THREE.Mesh(new THREE.BoxGeometry(W, H, .008), mat); casca.position.set(0, H / 2, -.004); tampa.add(casca);
  // tela: um canvas de 960x600 que só é redesenhado (e reenviado à placa) quando chega um quadro novo do PC.
  // (Mandar o ImageBitmap direto para a textura deixava a tela preta no vídeo Intel.)
  const telaCv = document.createElement('canvas'); telaCv.width = 960; telaCv.height = 600; desenharAguardo(telaCv);
  const telaCtx = telaCv.getContext('2d');
  const texTela = new THREE.CanvasTexture(telaCv); texTela.colorSpace = THREE.SRGBColorSpace;
  texTela.minFilter = THREE.LinearFilter; texTela.generateMipmaps = false;
  const geoTela = new THREE.PlaneGeometry(W - .022, H - .03);
  const tela = new THREE.Mesh(geoTela, new THREE.MeshBasicMaterial({ map: texTela, toneMapped: false }));
  tela.position.set(0, H / 2 + .004, .0002); tampa.add(tela);
  // camada das marcas: cursor e ondas de clique, transparente, logo à frente da tela
  const mc = document.createElement('canvas'); mc.width = 640; mc.height = 400; const m2 = mc.getContext('2d');
  const texMarcas = new THREE.CanvasTexture(mc); texMarcas.colorSpace = THREE.SRGBColorSpace; texMarcas.minFilter = THREE.LinearFilter; texMarcas.generateMipmaps = false;
  const marcas = new THREE.Mesh(geoTela, new THREE.MeshBasicMaterial({ map: texMarcas, transparent: true, depthWrite: false, toneMapped: false }));
  marcas.position.set(0, H / 2 + .004, .0006); tampa.add(marcas);
  const cam2 = new THREE.Mesh(new THREE.CircleGeometry(.0018, 16), new THREE.MeshBasicMaterial({ color: 0x222233 })); cam2.position.set(0, H - .006, .0003); tampa.add(cam2);
  const anel = new THREE.Group(); [[.26,.006,1],[.3,.002,.5],[.34,.0015,.3]].forEach(([r,e,o]) => anel.add(new THREE.Mesh(new THREE.TorusGeometry(r,e,8,128), new THREE.MeshBasicMaterial({ color: 0x1e90ff, transparent: true, opacity: o, blending: THREE.AdditiveBlending }))));
  const brilho = new THREE.Mesh(new THREE.CircleGeometry(.26, 64), new THREE.MeshBasicMaterial({ color: 0x0b3a8a, transparent: true, opacity: .35 })); brilho.rotation.x = -Math.PI / 2; brilho.position.y = -.061;
  const logo = document.createElement('canvas'); logo.width = 256; logo.height = 48; const lc = logo.getContext('2d'); lc.fillStyle = '#9a9aa0'; lc.font = '30px sans-serif'; lc.textAlign = 'center'; lc.fillText('Lenovo', 128, 34);
  const lg = new THREE.Mesh(new THREE.PlaneGeometry(.045, .0085), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(logo), transparent: true })); lg.position.set(0, .008, .0003); tampa.add(lg);
  const corpo = new THREE.Group(); cena.children.slice().forEach(o => { if (!o.isLight) corpo.add(o); }); cena.add(corpo); corpo.rotation.y = -.35;
  anel.rotation.x = -Math.PI / 2; anel.position.y = -.06; cena.add(anel, brilho);
  // clique na tela 3D -> (u,v)
  const ray = new THREE.Raycaster(), m = new THREE.Vector2(); let down = null;
  const uv = ev => { const b = canvas.getBoundingClientRect(); m.set((ev.clientX - b.left) / b.width * 2 - 1, -(ev.clientY - b.top) / b.height * 2 + 1); ray.setFromCamera(m, cam); const h = ray.intersectObject(tela)[0]; return h ? [h.uv.x, 1 - h.uv.y] : null; };
  canvas.addEventListener('pointerdown', e => down = [e.clientX, e.clientY, e.button]);
  canvas.addEventListener('pointerup', e => { if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 4) { const p = uv(e); if (p) aoClicar({ tipo: down[2] === 2 ? 'direito' : 'clicar', u: p[0], v: p[1] }); } down = null; });
  canvas.addEventListener('dblclick', e => { const p = uv(e); if (p) aoClicar({ tipo: 'duplo', u: p[0], v: p[1] }); });
  canvas.addEventListener('contextmenu', e => e.preventDefault());

  let cursor = null, cliques = [], marcaAntes = '';
  function desenharMarcas() {
    const agora = performance.now(); cliques = cliques.filter(k => agora - k.t < 700);
    const marca = (cursor ? cursor.map(v => v.toFixed(3)).join() : '') + '|' + cliques.length;
    if (marca === marcaAntes && !cliques.length) return;
    marcaAntes = marca; m2.clearRect(0, 0, 640, 400);
    for (const k of cliques) { const p = (agora - k.t) / 700; m2.strokeStyle = `rgba(255,50,50,${1 - p})`; m2.lineWidth = 4; m2.beginPath(); m2.arc(k.u * 640, k.v * 400, 8 + p * 30, 0, 7); m2.stroke(); }
    if (cursor) { m2.strokeStyle = '#f33'; m2.lineWidth = 3; m2.beginPath(); m2.arc(cursor[0] * 640, cursor[1] * 400, 7, 0, 7); m2.stroke(); }
    texMarcas.needsUpdate = true;
  }
  return {
    frame(bmp) {   // um quadro novo da tela do PC (já reduzido para 960x600 ao abrir o JPEG)
      telaCtx.drawImage(bmp, 0, 0, 960, 600); bmp.close();
      texTela.needsUpdate = true;
    },
    cursor(c) { cursor = c; },
    clique(u, v) { cliques.push({ u, v, t: performance.now() }); },
    quadro() { const w = canvas.clientWidth, h = canvas.clientHeight; if (!w) return;
      if (canvas.width !== w || canvas.height !== h) { r.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
      desenharMarcas();
      const t = performance.now() / 1000; corpo.position.y = Math.sin(t * 1.3) * .006; anel.rotation.z = t * .2; ctl.update(); r.render(cena, cam); },
    foto() { r.render(cena, cam); return canvas.toDataURL('image/jpeg', .8); },
  };
}

function desenharAguardo(cv) {
  const tc = cv.getContext('2d'), g = tc.createLinearGradient(0, 0, 960, 600);
  g.addColorStop(0, '#0a2a5a'); g.addColorStop(1, '#020814'); tc.fillStyle = g; tc.fillRect(0, 0, 960, 600);
  tc.fillStyle = '#5cc8ff'; tc.font = 'bold 40px sans-serif'; tc.textAlign = 'center'; tc.fillText('J.A.R.V.I.S.', 480, 270);
  tc.font = '20px sans-serif'; tc.fillStyle = '#9cf'; tc.fillText('Aguardando a tela do notebook...', 480, 308);
}
