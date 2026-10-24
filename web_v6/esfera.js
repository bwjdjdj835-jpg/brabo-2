// Esfera "Nexus": partículas azuis conectadas que pulsam com a fala
import * as THREE from 'three';
export function criarEsfera(canvas, estado) {
  const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  const cena = new THREE.Scene(), cam = new THREE.PerspectiveCamera(50, 1, .1, 100); cam.position.z = 6;
  const N = 700, base = [], pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) { // distribuição Fibonacci
    const y = 1 - (i / (N - 1)) * 2, rr = Math.sqrt(1 - y * y), th = i * 2.39996;
    base.push(new THREE.Vector3(Math.cos(th) * rr, y, Math.sin(th) * rr).multiplyScalar(2));
  }
  const gp = new THREE.BufferGeometry(); gp.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const pts = new THREE.Points(gp, new THREE.PointsMaterial({ color: 0x5cc8ff, size: .05, transparent: true, blending: THREE.AdditiveBlending }));
  const pares = []; for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) if (base[i].distanceTo(base[j]) < .32) pares.push(i, j);
  const lp = new Float32Array(pares.length * 3), gl = new THREE.BufferGeometry(); gl.setAttribute('position', new THREE.BufferAttribute(lp, 3));
  const linhas = new THREE.LineSegments(gl, new THREE.LineBasicMaterial({ color: 0x1e90ff, transparent: true, opacity: .35, blending: THREE.AdditiveBlending }));
  const nucleo = new THREE.Mesh(new THREE.SphereGeometry(.5, 32, 32), new THREE.MeshBasicMaterial({ color: 0x1e90ff, transparent: true, opacity: .25 }));
  const g = new THREE.Group(); g.add(pts, linhas, nucleo); cena.add(g);
  let n = 0;
  function quadro(t) {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w) return; if (canvas.width !== w || canvas.height !== h) { r.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
    n += (estado.nivel - n) * .25;
    for (let i = 0; i < N; i++) {
      const b = base[i], ruido = Math.sin(t * 3 + i * .7) * .03 + n * .22 * Math.sin(t * 9 + b.y * 5 + i * .13);
      const k = 1 + .02 * Math.sin(t * 1.2) + ruido; pos[i * 3] = b.x * k; pos[i * 3 + 1] = b.y * k; pos[i * 3 + 2] = b.z * k;
    }
    for (let p = 0; p < pares.length; p++) { const i = pares[p]; lp[p * 3] = pos[i * 3]; lp[p * 3 + 1] = pos[i * 3 + 1]; lp[p * 3 + 2] = pos[i * 3 + 2]; }
    gp.attributes.position.needsUpdate = gl.attributes.position.needsUpdate = true;
    g.rotation.y = t * (.15 + n * .6); g.rotation.x = Math.sin(t * .3) * .2;
    nucleo.scale.setScalar(1 + n * 1.2); linhas.material.opacity = .3 + n * .5; pts.material.size = .05 + n * .04;
    r.render(cena, cam);
  }
  return { quadro };
}
