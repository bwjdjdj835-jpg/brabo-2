"""Controle de computador: PC local (mss + pyautogui via app.controle) ou máquina remota/nuvem
(agente_remoto.py rodando numa VM, via WebSocket). Mesma API nos dois casos.

Coordenadas sempre normalizadas: u (0=esquerda..1=direita), v (0=topo..1=base).
"""
import base64, io, json, os, sys
from ..registro import ferramenta, registro

_alvo = {"tipo": "local", "url": None, "token": None}
_local = {}


def _controle_local():
    if registro.perm.controle is not None and registro.perm.controle is not _local.get("c"):
        # dentro do servidor: usa o MESMO Controle (e a captura) da interface 3D
        cap = sys.modules["app.server"].captura if "app.server" in sys.modules else None
        if cap is None and "cap" not in _local:
            from app.captura import CapturaTela
            _local["cap"] = CapturaTela(fps=4); _local["cap"].iniciar()
        return registro.perm.controle, cap or _local["cap"]
    if "c" not in _local:
        from app.captura import CapturaTela
        from app.controle import Controle
        cap = CapturaTela(fps=4); cap.iniciar()
        _local["cap"] = cap; _local["c"] = Controle(lambda: cap.geo)
        registro.perm.controle = _local["c"]
    return _local["c"], _local["cap"]


class ClienteRemoto:
    """Cliente síncrono do agente_remoto.py (protocolo JSON sobre WebSocket)."""
    def __init__(self, url, token):
        from websockets.sync.client import connect
        self.ws = connect(url, open_timeout=15, max_size=2**25)
        self._req({"cmd": "ola", "token": token})

    def _req(self, d):
        self.ws.send(json.dumps(d)); r = json.loads(self.ws.recv(timeout=60))
        if not r.get("ok", True): raise RuntimeError(r.get("erro"))
        return r

    def captura(self, largura=1280): return self._req({"cmd": "captura", "largura": largura})
    def acao(self, a): return self._req({"cmd": "acao", "acao": a})


def _remoto():
    if "r" not in _local or _local.get("r_url") != _alvo["url"]:
        _local["r"] = ClienteRemoto(_alvo["url"], _alvo["token"]); _local["r_url"] = _alvo["url"]
    return _local["r"]


@ferramenta(risco="leitura")
def computador_alvo(destino: str = "local", token: str = ""):
    """Escolhe qual computador o Ryker controla: 'local' ou a URL ws://IP:8765 de um agente_remoto (nuvem)."""
    if destino == "local":
        _alvo.update(tipo="local", url=None)
    else:
        _alvo.update(tipo="remoto", url=destino, token=token or os.environ.get("JARVIS_REMOTO_TOKEN", ""))
        _remoto()
    return {"ok": True, "alvo": _alvo["tipo"], "url": _alvo["url"]}


@ferramenta(risco="leitura")
def tela_capturar(largura: int = 1280):
    """Captura a tela do computador-alvo (para o modelo de visão raciocinar). Devolve JPEG base64 + tamanho."""
    if _alvo["tipo"] == "remoto":
        r = _remoto().captura(largura)
        return {"ok": True, "tela": r["geo"], "imagem_b64": r["jpeg_b64"], "cursor": r.get("cursor")}
    c, cap = _controle_local()
    import time
    for _ in range(50):
        if cap.jpeg: break
        time.sleep(.1)
    if not cap.jpeg: return {"ok": False, "erro": cap.erro or "sem captura"}
    from PIL import Image
    im = Image.open(io.BytesIO(cap.jpeg)); im.thumbnail((largura, largura))
    b = io.BytesIO(); im.convert("RGB").save(b, "JPEG", quality=70)
    return {"ok": True, "tela": cap.geo, "imagem_b64": base64.b64encode(b.getvalue()).decode(), "cursor": c.cursor_uv()}


def _executar(acao: dict):
    if _alvo["tipo"] == "remoto":
        return _remoto().acao(acao)
    c, _ = _controle_local()
    return c.executar(acao)


@ferramenta(risco="risco")
def computador_acao(acao: dict):
    """Executa uma ação: {"tipo": mover|clicar|duplo|direito|digitar|teclas|rolar|abrir, "u","v","texto","teclas","qtd","url"}."""
    return _executar(acao)


@ferramenta(risco="risco")
def computador_clicar(u: float, v: float, tipo: str = "clicar"):
    """Clica na posição normalizada (u,v) da tela. tipo: clicar | duplo | direito | mover."""
    return _executar({"tipo": tipo, "u": u, "v": v})


@ferramenta(risco="risco")
def computador_digitar(texto: str):
    """Digita um texto no campo focado (acentos via área de transferência)."""
    return _executar({"tipo": "digitar", "texto": texto})


@ferramenta(risco="risco")
def computador_teclas(teclas: list):
    """Pressiona um atalho, ex.: ["ctrl","c"], ["alt","tab"], ["enter"]."""
    return _executar({"tipo": "teclas", "teclas": teclas})
