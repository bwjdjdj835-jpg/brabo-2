import os, re, unicodedata
SAIDAS = os.environ.get("JARVIS_SAIDAS", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saidas"))

def pasta(*p):
    d = os.path.join(SAIDAS, *p); os.makedirs(d, exist_ok=True); return d

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "item"
