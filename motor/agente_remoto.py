"""Agente remoto: rode isto num computador na NUVEM (VM com área de trabalho) ou em outro PC.

    pip install websockets mss Pillow pyautogui pyperclip
    JARVIS_REMOTO_TOKEN=um-segredo-longo python -m motor.agente_remoto --porta 8765 [--permitir]

No Jarvis:  computador_alvo(destino="ws://IP_DA_VM:8765", token="um-segredo-longo")

Segurança:
  * token obrigatório (comparação em tempo constante); sem token o servidor não inicia;
  * o controle começa DESLIGADO e NÃO pode ser ligado pela rede, a menos que --permitir seja passado (use só em VM descartável);
  * failsafe do pyautogui ativo (mouse no canto = para tudo);
  * prefira expor só via túnel SSH/VPN (ssh -L 8765:localhost:8765 vm) em vez de abrir a porta.
"""
import argparse, asyncio, base64, hmac, io, json, os, sys


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--permitir", action="store_true")
    a = ap.parse_args()
    token = os.environ.get("JARVIS_REMOTO_TOKEN", "")
    if len(token) < 12: sys.exit("Defina JARVIS_REMOTO_TOKEN (>= 12 caracteres).")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.captura import CapturaTela
    from app.controle import Controle
    import websockets
    from PIL import Image
    cap = CapturaTela(fps=4); cap.iniciar(); ctl = Controle(lambda: cap.geo); ctl.definir(a.permitir)

    async def atender(ws):
        autenticado = False
        async for bruto in ws:
            try:
                m = json.loads(bruto); cmd = m.get("cmd")
                if cmd == "ola":
                    autenticado = hmac.compare_digest(str(m.get("token", "")), token)
                    r = {"ok": autenticado, "erro": None if autenticado else "token inválido", "controle": ctl.ligado}
                elif not autenticado:
                    r = {"ok": False, "erro": "não autenticado"}
                elif cmd == "captura":
                    for _ in range(50):
                        if cap.jpeg: break
                        await asyncio.sleep(.1)
                    im = Image.open(io.BytesIO(cap.jpeg)); im.thumbnail((int(m.get("largura", 1280)),) * 2)
                    b = io.BytesIO(); im.convert("RGB").save(b, "JPEG", quality=70)
                    r = {"ok": True, "geo": cap.geo, "cursor": ctl.cursor_uv(), "jpeg_b64": base64.b64encode(b.getvalue()).decode()}
                elif cmd == "acao":
                    r = ctl.executar(m["acao"])
                elif cmd == "controle":
                    if m.get("ligado") and not a.permitir:   # sem --permitir, ninguém liga o controle pela rede
                        r = {"ok": False, "ligado": ctl.ligado, "erro": "agente iniciado sem --permitir: ligar remotamente é proibido"}
                    else:
                        r = {"ok": True, "ligado": ctl.definir(bool(m.get("ligado")))}
                elif cmd == "parar":
                    ctl.emergencia("parar remoto"); r = {"ok": True, "ligado": False}
                else:
                    r = {"ok": False, "erro": f"comando desconhecido {cmd}"}
            except Exception as e:
                r = {"ok": False, "erro": str(e)}
            await ws.send(json.dumps(r))
            if not autenticado: await ws.close(); return

    async def rodar():
        async with websockets.serve(atender, a.host, a.porta, max_size=2**25):
            print(f"agente_remoto ouvindo em ws://{a.host}:{a.porta} (controle {'LIGADO' if ctl.ligado else 'DESLIGADO'})")
            await asyncio.Future()
    asyncio.run(rodar())


if __name__ == "__main__":
    main()
