"""Captura a tela REAL do PC (mss + Pillow) numa thread e guarda o último quadro em JPEG.
O servidor envia esses quadros pelo WebSocket /ws/tela para a textura da tela 3D."""
import io, threading, time
import mss
from PIL import Image


class CapturaTela:
    def __init__(self, fps: float = 10, largura_max: int = 1920, qualidade: int = 75, monitor: int = 1):
        self.fps, self.largura_max, self.qualidade, self.monitor = fps, largura_max, qualidade, monitor
        self.jpeg: bytes | None = None
        self.quadro = 0                       # contador de quadros (para saber se há quadro novo)
        self.geo = {"left": 0, "top": 0, "width": 1920, "height": 1080}
        self.erro: str | None = None
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="captura-tela")

    def iniciar(self):
        if not self._thread.is_alive():
            self._thread.start()

    def parar(self):
        self._parar.set()

    def _loop(self):
        try:
            sct = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
        except Exception as e:  # sem display (servidor sem tela)
            self.erro = f"captura indisponível: {e}"
            return
        with sct:
            mon = sct.monitors[self.monitor] if len(sct.monitors) > self.monitor else sct.monitors[0]
            self.geo = dict(left=mon["left"], top=mon["top"], width=mon["width"], height=mon["height"])
            while not self._parar.is_set():
                t0 = time.perf_counter()
                try:
                    shot = sct.grab(mon)
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    if img.width > self.largura_max:
                        img = img.resize((self.largura_max, round(img.height * self.largura_max / img.width)), Image.BILINEAR)
                    buf = io.BytesIO(); img.save(buf, "JPEG", quality=self.qualidade)
                    self.jpeg = buf.getvalue(); self.quadro += 1; self.erro = None
                except Exception as e:
                    self.erro = str(e)
                time.sleep(max(0, 1 / self.fps - (time.perf_counter() - t0)))
