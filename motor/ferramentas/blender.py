"""Ponte com o Blender (headless): roda scripts bpy em segundo plano para criar cenas anime 3D, renderizar PNG e exportar GLB.

Binário: variável BLENDER_BIN, ou `blender` no PATH, ou caminhos comuns (Windows: Program Files\\Blender Foundation).
"""
import glob, json, os, shutil, subprocess, sys, tempfile
from ..registro import ferramenta
from .util import pasta, slug

MODELOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modelos")


def achar_blender():
    cands = [os.environ.get("BLENDER_BIN"), shutil.which("blender")]
    cands += sorted(glob.glob("/tmp/blender-*/blender")) + sorted(glob.glob("/opt/blender*/blender"))
    cands += sorted(glob.glob(r"C:\Program Files\Blender Foundation\Blender*\blender.exe"), reverse=True)
    cands += ["/Applications/Blender.app/Contents/MacOS/Blender"]
    return next((c for c in cands if c and os.path.exists(c)), None)


def rodar_blender(script, args=None, timeout=900):
    b = achar_blender()
    if not b: return {"ok": False, "erro": "Blender não encontrado. Instale o Blender 4.x ou defina BLENDER_BIN."}
    cmd = [b, "-b", "--factory-startup", "-P", script, "--", *(args or [])]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    cauda = (p.stdout + p.stderr)[-2500:]
    return {"ok": p.returncode == 0 and "Traceback" not in cauda, "codigo": p.returncode, "saida": cauda}


@ferramenta(risco="arquivo")
def blender_cena_anime(titulo: str = "cena anime", cor_cabelo: str = "#e01b24", cor_roupa: str = "#1c1c28",
                       amostras: int = 24, largura: int = 1280, altura: int = 720):
    """Cria uma cena anime 3D no Blender (personagem toon com cabelo espetado, contorno Freestyle), renderiza PNG e exporta GLB."""
    d = pasta("blender", slug(titulo))
    cfg = dict(titulo=titulo, cabelo=cor_cabelo, roupa=cor_roupa, amostras=amostras, largura=largura, altura=altura,
               png=os.path.join(d, "render.png"), glb=os.path.join(d, "cena.glb"), blend=os.path.join(d, "cena.blend"))
    arq = os.path.join(d, "config.json")
    with open(arq, "w", encoding="utf-8") as f: json.dump(cfg, f, ensure_ascii=False)
    r = rodar_blender(os.path.join(MODELOS, "blender_anime.py"), [arq])
    r.update({k: cfg[k] for k in ("png", "glb", "blend")}) if r["ok"] else None
    return r


@ferramenta(risco="risco", confirmar=True)
def blender_executar_script(codigo: str, nome: str = "script"):
    """Executa um script Python (bpy) arbitrário no Blender headless. Exige controle LIGADO e confirmação."""
    d = pasta("blender", slug(nome)); arq = os.path.join(d, "script.py")
    with open(arq, "w", encoding="utf-8") as f: f.write(codigo)
    r = rodar_blender(arq); r["pasta"] = d; return r
