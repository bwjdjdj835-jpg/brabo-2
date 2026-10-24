"""Cérebro do Jarvis: interpreta comandos em português e gera respostas.
Troque/estenda `responder` para ligar a um LLM no futuro."""
import datetime as dt
import platform
import random

SAUDACOES = ("oi", "olá", "ola", "e aí", "bom dia", "boa tarde", "boa noite")


def info_sistema() -> dict:
    return {
        "so": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "maquina": platform.machine(),
        "cpu": "Intel Core i5 13ª geração (simulado)",
    }


def responder(texto: str) -> str:
    t = texto.lower().strip()
    agora = dt.datetime.now()
    if not t:
        return "Estou ouvindo, senhor."
    if any(t.startswith(s) for s in SAUDACOES):
        return random.choice([
            "Olá, Bruno. Todos os sistemas operacionais. Como posso ajudar?",
            "Bem-vindo de volta, Bruno. Pronto para trabalhar.",
        ])
    if "hora" in t:
        return f"Agora são {agora:%H:%M}."
    if "data" in t or "dia" in t:
        return f"Hoje é {agora:%d/%m/%Y}."
    if "sistema" in t or "status" in t:
        s = info_sistema()
        return f"Sistema {s['so']}, Python {s['python']}, processador {s['cpu']}. Tudo estável."
    if "quem é você" in t or "quem e voce" in t or "seu nome" in t:
        return "Eu sou o Jarvis, seu assistente pessoal. Fui criado em Python pelo Bruno."
    if "piada" in t:
        return "Por que o Python não briga? Porque ele sempre respeita a indentação."
    if "obrigado" in t or "valeu" in t:
        return "Sempre às ordens, senhor."
    return f"Entendido: “{texto.strip()}”. Ainda estou aprendendo esse comando, mas já anotei."


# ---------------------------------------------------------------------------
# Comandos de controle do PC (pt-BR). Estrutura plugável: troque `CerebroRegras`
# por uma classe com o mesmo método `interpretar(texto) -> (resposta, acoes)`
# que chame um modelo de IA (LLM) e devolva as mesmas ações.
# Ações: {"tipo": "mover|clicar|duplo|direito", "u":0..1, "v":0..1}, {"tipo":"digitar","texto":...},
#        {"tipo":"teclas","teclas":["ctrl","c"]}, {"tipo":"rolar","qtd":-5}, {"tipo":"abrir","url":...}
import re

LUGARES = {
    "centro": (.5, .5), "meio": (.5, .5), "canto superior esquerdo": (.03, .03), "canto superior direito": (.97, .03),
    "barra de tarefas": (.5, .985), "menu iniciar": (.02, .985), "iniciar": (.02, .985), "relógio": (.95, .985),
    "topo": (.5, .05), "baixo": (.5, .93), "esquerda": (.15, .5), "direita": (.85, .5),
}
TECLAS_NOMES = {"enter": "enter", "esc": "esc", "tab": "tab", "espaço": "space", "espaco": "space", "apagar": "backspace",
                "backspace": "backspace", "delete": "delete", "control": "ctrl", "ctrl": "ctrl", "alt": "alt", "shift": "shift",
                "windows": "win", "win": "win", "cima": "up", "baixo": "down", "esquerda": "left", "direita": "right"}


def _coords(s, alvos=None):
    s = s.strip().lower()
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%?\s*[,x ]\s*(\d+(?:[.,]\d+)?)\s*(%?)", s)
    if m:
        a, b = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
        if "%" in s: return a / 100, b / 100
        if a <= 1 and b <= 1: return a, b
        return ("px", a, b)
    for nome, uv in (alvos or {}).items():          # elementos conhecidos (ex.: botões da tela)
        if nome.lower() in s: return uv
    for nome, uv in LUGARES.items():
        if nome in s: return uv
    return None


class CerebroRegras:
    VERBOS = r"(clica|clique|clicar|duplo|dá|da um|digita|digite|escreve|escreva|aperta|aperte|pressiona|abre|abra|abrir|rola|role|move|mova|leva)"

    def interpretar(self, texto: str, alvos: dict | None = None, tela=(1920, 1080)):
        """Aceita vários comandos encadeados: "clica no meio da tela e digita olá"."""
        partes = [p for p in re.split(r"\s+(?:e|depois|e depois|aí)\s+(?=" + self.VERBOS + r"\b)", texto.strip(), flags=re.I) if p and not re.fullmatch(self.VERBOS, p, re.I)]
        if len(partes) <= 1:
            return self._um(texto, alvos, tela)
        respostas, acoes = [], []
        for p in partes:
            r, a = self._um(p, alvos, tela); respostas.append(r); acoes += a
        return " ".join(respostas), acoes

    def _um(self, texto: str, alvos: dict | None = None, tela=(1920, 1080)):
        t = texto.lower().strip()
        def uv(c):
            if c and c[0] == "px": return c[1] / max(1, tela[0] - 1), c[2] / max(1, tela[1] - 1)
            return c
        if re.search(r"\babr(e|a|ir)\b.*\b(navegador|chrome|edge|firefox|google)\b", t):
            return "Abrindo o navegador.", [{"tipo": "abrir", "url": "https://www.google.com"}]
        m = re.search(r"\babr(?:e|a|ir)\s+(?:o\s+site\s+)?((?:https?://)?[\w-]+\.[\w./-]+)", t)
        if m:
            url = m.group(1) if m.group(1).startswith("http") else "https://" + m.group(1)
            return f"Abrindo {url}.", [{"tipo": "abrir", "url": url}]
        m = re.match(r"^(?:clica|clique|clicar)\s+(duas vezes|duplo|com o direito|direito)?\s*(?:em|no|na|sobre)?\s*(.+)$", t)
        if m:
            c = uv(_coords(m.group(2), alvos))
            if not c: return f"Não achei “{m.group(2)}” na tela. Diga a posição, tipo “clica em 50% 30%” ou “clica em 800 400”.", []
            tipo = "duplo" if m.group(1) in ("duas vezes", "duplo") else "direito" if m.group(1) else "clicar"
            return f"Clicando em {m.group(2)}.", [{"tipo": tipo, "u": c[0], "v": c[1]}]
        m = re.match(r"^(?:move|mova|mover|leva|leve)\s+(?:o\s+)?(?:mouse|cursor)\s+(?:para|pra|até|ate|no|na|em)\s+(.+)$", t)
        if m:
            c = uv(_coords(m.group(1), alvos))
            if c: return "Movendo o mouse.", [{"tipo": "mover", "u": c[0], "v": c[1]}]
        m = re.match(r"^(?:digita|digite|digitar|escreve|escreva)\s+(.+)$", texto.strip(), re.I)
        if m:
            return "Digitando.", [{"tipo": "digitar", "texto": m.group(1).strip().strip('"“”')}]
        m = re.match(r"^(?:aperta|aperte|pressiona|pressione|tecla)\s+(.+)$", t)
        if m:
            teclas = [TECLAS_NOMES.get(k.strip(), k.strip()) for k in re.split(r"\s*\+\s*|\s+e\s+|\s+", m.group(1)) if k.strip()]
            return f"Apertando {'+'.join(teclas)}.", [{"tipo": "teclas", "teclas": teclas}]
        if re.search(r"\brola(r)?\b|\brole\b", t):
            return "Rolando a página.", [{"tipo": "rolar", "qtd": 5 if "cima" in t else -5}]
        return responder(texto), []


cerebro = CerebroRegras()
