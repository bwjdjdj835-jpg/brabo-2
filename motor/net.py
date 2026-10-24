"""HTTP mínimo (só stdlib) com User-Agent, timeout e JSON."""
import json, urllib.request, urllib.parse

UA = "JarvisMotor/1.0 (+https://github.com/; contato: jarvis-local)"

def http(url, dados=None, cab=None, timeout=60, metodo=None):
    cab = {"User-Agent": UA, **(cab or {})}
    corpo = None
    if isinstance(dados, (dict, list)):
        corpo = json.dumps(dados).encode(); cab.setdefault("Content-Type", "application/json")
    elif isinstance(dados, str):
        corpo = dados.encode(); cab.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=corpo, headers=cab, method=metodo)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")

def http_json(url, dados=None, cab=None, timeout=60):
    return json.loads(http(url, dados, cab, timeout))

def q(s): return urllib.parse.quote_plus(s)
