"""Backend FastAPI: interface 3D, chat, espelho da tela real (WebSocket) e controle do PC."""
import asyncio, json
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .brain import responder, info_sistema, cerebro
from .captura import CapturaTela
from .controle import Controle

WEB = Path(__file__).resolve().parent.parent / "web"
app = FastAPI(title="Jarvis")
captura = CapturaTela()
controle = Controle(lambda: captura.geo)

# ---- motor (agente com ferramentas) usa o MESMO controle/segurança da interface ----
from motor import registro as motor_registro
motor_registro.perm.controle = controle
_agente = None
def agente():
    global _agente
    if _agente is None:
        from motor import Agente
        _agente = Agente()
    return _agente


@app.on_event("startup")
def _iniciar():
    captura.iniciar()


class Mensagem(BaseModel):
    texto: str
    alvos: dict | None = None     # elementos clicáveis conhecidos {nome: [u, v]} (opcional)


@app.post("/api/chat")
def chat(m: Mensagem):
    g = captura.geo
    resposta, acoes = cerebro.interpretar(m.texto, m.alvos, (g["width"], g["height"]))
    if acoes and not controle.ligado:
        resposta += " (O controle do PC está DESLIGADO: ligue no botão grande para eu executar.)"
    return {"resposta": resposta, "acoes": acoes}


@app.get("/api/status")
def status():
    return {**info_sistema(), "tela": captura.geo, "captura_erro": captura.erro, "controle": controle.ligado}


class Acao(BaseModel):
    tipo: str
    u: float | None = None
    v: float | None = None
    texto: str | None = None
    teclas: list[str] | None = None
    qtd: int | None = None
    url: str | None = None


@app.post("/api/acao")
def acao(a: Acao):
    return controle.executar(a.model_dump(exclude_none=True))


class Liga(BaseModel):
    ligado: bool


@app.post("/api/controle")
def definir_controle(l: Liga):
    if l.ligado: motor_registro.perm.parado.clear()
    return {"ligado": controle.definir(l.ligado)}


@app.post("/api/parar")
def parar():
    controle.emergencia("botão PARAR / Esc×3 na interface")
    motor_registro.perm.parado.set()
    return {"ligado": False}


class Pedido(BaseModel):
    texto: str


@app.post("/api/motor")
def motor_pedido(p: Pedido):
    """Pedido em linguagem natural para o agente (loop planejar -> ferramenta -> observar)."""
    motor_registro.perm.parado.clear()
    r = agente().executar(p.texto)
    return {"resposta": r["resposta"], "provedor": r["provedor"],
            "passos": [{"ferramenta": x["ferramenta"], "ok": x["resultado"].get("ok"), "resumo": {k: v for k, v in x["resultado"].items() if k in ("csv", "index", "png", "pasta", "erro", "total", "sem_site", "url")}} for x in r["passos"]]}


@app.get("/api/motor/estado")
def motor_estado():
    import motor.ferramentas  # noqa: registra as ferramentas
    return {**motor_registro.estado, "ferramentas": [f["name"] for f in motor_registro.descricoes()]}


@app.get("/api/log")
def log():
    return {"ligado": controle.ligado, "log": list(controle.log)[-60:]}


@app.websocket("/ws/tela")
async def ws_tela(ws: WebSocket):
    """Envia quadros JPEG (binário) + estado em JSON (texto) da tela real."""
    await ws.accept()
    ultimo = -1
    try:
        while True:
            if captura.quadro != ultimo and captura.jpeg:
                ultimo = captura.quadro
                await ws.send_text(json.dumps({"cursor": controle.cursor_uv(), "tela": captura.geo, "controle": controle.ligado}))
                await ws.send_bytes(captura.jpeg)
            elif captura.erro and ultimo < 0:
                await ws.send_text(json.dumps({"erro": captura.erro, "controle": controle.ligado})); await asyncio.sleep(1)
            await asyncio.sleep(0.03)
    except (WebSocketDisconnect, RuntimeError):
        pass


# ---------------- v6: status do sistema (psutil) e modo "Direto no PC" ----------------
_rede = {"t": 0.0, "b": 0}
@app.get("/api/sistema")
def sistema():
    import time, platform
    try:
        import psutil
    except ImportError:
        return {"erro": "instale psutil"}
    io = psutil.net_io_counters(); agora = time.time(); b = io.bytes_sent + io.bytes_recv
    mbps = ((b - _rede["b"]) * 8 / 1e6 / (agora - _rede["t"])) if _rede["t"] else 0.0
    _rede.update(t=agora, b=b)
    gpu = None
    try:
        import GPUtil; g = GPUtil.getGPUs(); gpu = round(g[0].load * 100) if g else None
    except Exception:
        pass
    bat = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    return {"cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent, "gpu": gpu, "rede_mbps": round(mbps, 2),
            "bateria": round(bat.percent) if bat else None, "na_tomada": bat.power_plugged if bat else None,
            "uptime_s": int(agora - psutil.boot_time()), "os": f"{platform.system()} {platform.release()}", "maquina": platform.node()}


@app.post("/api/acao_direta")
def acao_direta(a: Acao):
    """Modo 'Direto no PC': minimiza a janela do Jarvis, executa a ação na tela real e restaura a janela.
    Respeita o mesmo controle (DESLIGADO por padrão) e o PARAR."""
    import time
    if not controle.ligado:
        return {"ok": False, "erro": "Controle DESLIGADO"}
    janela = None
    try:
        import pygetwindow as gw  # Windows/macOS
        ws = [w for w in gw.getAllWindows() if "J.A.R.V.I.S" in (w.title or "")]
        if ws:
            janela = ws[0]; janela.minimize(); time.sleep(0.4)
    except Exception:
        pass
    r = controle.executar(a.model_dump(exclude_none=True))
    if janela:
        try:
            time.sleep(0.6); janela.restore(); janela.activate()
        except Exception:
            pass
    r["minimizou"] = bool(janela)
    return r


app.mount("/v6", StaticFiles(directory=WEB.parent / "web_v6", html=True), name="web_v6")
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
