"""Camada de controle do PC REAL (mouse/teclado) via pyautogui.

Segurança:
- Começa DESLIGADO. Só executa ações com `ligado = True` (botão grande no HUD).
- pyautogui.FAILSAFE: jogar o mouse num canto da tela aborta e desliga o controle.
- Parada de emergência: Ctrl+Alt+Q ou Esc 3 vezes seguidas (atalho global via pynput, se instalado)
  e também pelo botão PARAR do HUD / Esc×3 na interface.
- Toda ação vai para o log (aparece no painel do HUD).
Coordenadas: as ações usam (u, v) normalizados 0..1 da tela 3D, convertidos para pixels do monitor real.
"""
import sys, time, threading, types, webbrowser
from collections import deque
from datetime import datetime

if sys.platform.startswith("linux"):           # pyautogui importa o mouseinfo, que exige tkinter no Linux
    sys.modules.setdefault("mouseinfo", types.ModuleType("mouseinfo"))
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
except Exception as e:   # sem display
    pyautogui = None
    _ERRO_PYAUTOGUI = str(e)

TECLAS_OK = set(getattr(pyautogui, "KEYBOARD_KEYS", []) if pyautogui else [])


class Controle:
    def __init__(self, geo_fn):
        self.ligado = False
        self.geo_fn = geo_fn                 # devolve {left, top, width, height} do monitor capturado
        self.log = deque(maxlen=200)
        self.lock = threading.Lock()
        self._esc = deque(maxlen=3)
        self.registrar("sistema", "Controle do PC DESLIGADO (padrão). Parada: Ctrl+Alt+Q ou Esc×3.")
        self._atalho_global()

    # ---------- log ----------
    def registrar(self, tipo, texto, ok=True):
        self.log.append({"hora": datetime.now().strftime("%H:%M:%S"), "tipo": tipo, "texto": texto, "ok": ok})

    # ---------- liga / desliga / emergência ----------
    def definir(self, ligado: bool, motivo="HUD"):
        self.ligado = bool(ligado) and pyautogui is not None
        self.registrar("sistema", f"Controle {'LIGADO' if self.ligado else 'DESLIGADO'} ({motivo})", True)
        return self.ligado

    def emergencia(self, motivo="parada de emergência"):
        self.ligado = False
        self.registrar("PARADA", f"PARADA DE EMERGÊNCIA: {motivo}", False)

    def _atalho_global(self):
        try:
            from pynput import keyboard
        except Exception:
            self.registrar("sistema", "pynput ausente: atalho global desativado (use o botão PARAR ou o mouse no canto).", False)
            return

        def esc():
            agora = time.time(); self._esc.append(agora)
            if len(self._esc) == 3 and agora - self._esc[0] < 1.5:
                self.emergencia("Esc×3")

        def on_press(k):
            if k == keyboard.Key.esc:
                esc()
        try:
            hk = keyboard.GlobalHotKeys({"<ctrl>+<alt>+q": lambda: self.emergencia("Ctrl+Alt+Q")})
            hk.daemon = True; hk.start()
            ls = keyboard.Listener(on_press=on_press); ls.daemon = True; ls.start()
            self.registrar("sistema", "Atalhos de emergência ativos: Ctrl+Alt+Q / Esc×3.")
        except Exception as e:
            self.registrar("sistema", f"Atalho global indisponível: {e}", False)

    # ---------- coordenadas ----------
    def uv_para_px(self, u, v):
        g = self.geo_fn()
        u, v = min(max(float(u), 0.0), 1.0), min(max(float(v), 0.0), 1.0)
        x = g["left"] + round(u * (g["width"] - 1)); y = g["top"] + round(v * (g["height"] - 1))
        # não deixa a própria ação acionar o failsafe (cantos), só o usuário
        x = min(max(x, g["left"] + 2), g["left"] + g["width"] - 3); y = min(max(y, g["top"] + 2), g["top"] + g["height"] - 3)
        return x, y

    def cursor_uv(self):
        if pyautogui is None:
            return None
        try:
            g = self.geo_fn(); x, y = pyautogui.position()
            return [(x - g["left"]) / max(1, g["width"] - 1), (y - g["top"]) / max(1, g["height"] - 1)]
        except Exception:
            return None

    # ---------- execução ----------
    def executar(self, acao: dict) -> dict:
        tipo = acao.get("tipo")
        desc = self.descrever(acao)
        if not self.ligado:
            self.registrar("bloqueado", f"{desc} (controle DESLIGADO)", False)
            return {"ok": False, "erro": "Controle do PC está DESLIGADO. Ligue no botão do HUD."}
        try:
            with self.lock:
                if tipo == "mover":
                    pyautogui.moveTo(*self.uv_para_px(acao["u"], acao["v"]), duration=0.15)
                elif tipo in ("clicar", "duplo", "direito"):
                    x, y = self.uv_para_px(acao["u"], acao["v"])
                    pyautogui.moveTo(x, y, duration=0.12)
                    if tipo == "duplo": pyautogui.doubleClick(x, y)
                    elif tipo == "direito": pyautogui.rightClick(x, y)
                    else: pyautogui.click(x, y)
                elif tipo == "digitar":
                    self._digitar(acao["texto"])
                elif tipo == "teclas":
                    teclas = [t.lower() for t in acao["teclas"]]
                    ruins = [t for t in teclas if TECLAS_OK and t not in TECLAS_OK]
                    if ruins: raise ValueError(f"tecla desconhecida: {ruins}")
                    pyautogui.hotkey(*teclas)
                elif tipo == "rolar":
                    pyautogui.scroll(int(acao.get("qtd", -5)) * 100)
                elif tipo == "abrir":
                    webbrowser.open(acao.get("url") or "https://www.google.com")
                else:
                    raise ValueError(f"ação desconhecida: {tipo}")
            self.registrar("ação", desc, True)
            return {"ok": True}
        except pyautogui.FailSafeException:
            self.emergencia("mouse no canto da tela (failsafe)")
            return {"ok": False, "erro": "Failsafe: mouse no canto. Controle desligado."}
        except Exception as e:
            self.registrar("erro", f"{desc}: {e}", False)
            return {"ok": False, "erro": str(e)}

    def _digitar(self, texto):
        if texto.isascii():
            pyautogui.write(texto, interval=0.02)
            return
        try:   # acentos (pt-BR): cola pela área de transferência
            import pyperclip
            pyperclip.copy(texto); pyautogui.hotkey("command" if sys.platform == "darwin" else "ctrl", "v")
        except Exception:
            pyautogui.write(texto.encode("ascii", "ignore").decode(), interval=0.02)

    @staticmethod
    def descrever(a):
        t = a.get("tipo")
        if t in ("mover", "clicar", "duplo", "direito"):
            nomes = {"mover": "mover mouse", "clicar": "clique", "duplo": "clique duplo", "direito": "clique direito"}
            return f"{nomes[t]} em ({float(a['u']):.2f}, {float(a['v']):.2f})"
        if t == "digitar": return f"digitar “{a.get('texto', '')[:40]}”"
        if t == "teclas": return "atalho " + "+".join(a.get("teclas", []))
        if t == "rolar": return f"rolar {a.get('qtd')}"
        if t == "abrir": return f"abrir {a.get('url') or 'navegador'}"
        return str(a)
