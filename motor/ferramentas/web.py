"""Pesquisa na web (Google via SerpAPI se SERPAPI_KEY existir; senão DuckDuckGo HTML, grátis) e leitura de páginas."""
import html, os, re
from ..net import http, http_json, q
from ..registro import ferramenta


def _ddg(consulta, n):
    pag = http("https://html.duckduckgo.com/html/", "q=" + q(consulta) + "&kl=br-pt", timeout=30)
    out = []
    for m in re.finditer(r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>', pag, re.S):
        url = m.group(1)
        u = re.search(r"uddg=([^&]+)", url)
        if u:
            import urllib.parse; url = urllib.parse.unquote(u.group(1))
        limpa = lambda s: html.unescape(re.sub("<.*?>", "", s)).strip()
        out.append({"titulo": limpa(m.group(2)), "url": url, "trecho": limpa(m.group(3))})
        if len(out) >= n: break
    return out


@ferramenta(risco="leitura")
def pesquisar_web(consulta: str, n: int = 8):
    """Pesquisa na web (Google/SerpAPI ou DuckDuckGo) e devolve título, URL e trecho."""
    chave = os.environ.get("SERPAPI_KEY")
    if chave:
        r = http_json(f"https://serpapi.com/search.json?engine=google&hl=pt-br&gl=br&q={q(consulta)}&api_key={chave}")
        res = [{"titulo": x.get("title"), "url": x.get("link"), "trecho": x.get("snippet", "")} for x in r.get("organic_results", [])[:n]]
        return {"ok": True, "fonte": "google/serpapi", "resultados": res}
    return {"ok": True, "fonte": "duckduckgo", "resultados": _ddg(consulta, n)}


@ferramenta(risco="leitura")
def ler_pagina(url: str, max_chars: int = 8000):
    """Baixa uma página e devolve o texto limpo (sem scripts/estilos) e os links."""
    if not re.match(r"https?://", url): return {"ok": False, "erro": "URL precisa começar com http(s)://"}
    pag = http(url, timeout=30)
    titulo = re.search(r"<title[^>]*>(.*?)</title>", pag, re.S | re.I)
    corpo = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", pag)
    texto = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", corpo))).strip()
    links = list(dict.fromkeys(re.findall(r'href="(https?://[^"#]+)"', pag)))[:40]
    return {"ok": True, "titulo": html.unescape(titulo.group(1).strip()) if titulo else "", "texto": texto[:max_chars], "links": links}
