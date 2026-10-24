"""Provedores de LLM plugáveis (só stdlib/urllib). Todos expõem:

    pensar(mensagens, ferramentas) -> {"texto": str, "chamadas": [{"id", "nome", "args"}]}

Mensagens no formato interno:
    {"papel": "sistema"|"usuario"|"assistente"|"ferramenta", "texto": str,
     "imagem_b64": str|None, "chamadas": [...], "id": str (resposta de ferramenta)}

Variáveis de ambiente (escolha automática nesta ordem):
    JARVIS_LLM            = openai | anthropic | ollama | regras   (força um provedor)
    OPENAI_API_KEY        (+ OPENAI_BASE_URL p/ qualquer API compatível: Groq, OpenRouter, xAI, DeepSeek, LM Studio...)
    OPENAI_MODEL          padrão gpt-4o-mini
    ANTHROPIC_API_KEY     ANTHROPIC_MODEL padrão claude-3-5-sonnet-latest
    OLLAMA_HOST           padrão http://localhost:11434 ; OLLAMA_MODEL padrão llama3.1 (visão: llava / qwen2.5vl)
Sem nenhuma chave -> ProvedorRegras (o parser pt-BR do app/brain.py).
"""
import json, os, uuid
from .net import http_json


class Provedor:
    nome = "base"; visao = False
    def pensar(self, mensagens, ferramentas): raise NotImplementedError


class ProvedorOpenAI(Provedor):
    """Qualquer API compatível com /v1/chat/completions + tools (OpenAI, Groq, OpenRouter, xAI, Ollama /v1...)."""
    nome = "openai"; visao = True
    def __init__(self, chave=None, base=None, modelo=None):
        self.chave = chave or os.environ.get("OPENAI_API_KEY", "")
        self.base = (base or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.modelo = modelo or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def _msgs(self, mensagens):
        out = []
        for m in mensagens:
            p = m["papel"]
            if p == "ferramenta":
                out.append({"role": "tool", "tool_call_id": m["id"], "content": m["texto"]}); continue
            role = {"sistema": "system", "usuario": "user", "assistente": "assistant"}[p]
            content = m.get("texto") or ""
            if m.get("imagem_b64"):
                content = [{"type": "text", "text": content},
                           {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + m["imagem_b64"]}}]
            d = {"role": role, "content": content}
            if m.get("chamadas"):
                d["tool_calls"] = [{"id": c["id"], "type": "function",
                                    "function": {"name": c["nome"], "arguments": json.dumps(c["args"], ensure_ascii=False)}}
                                   for c in m["chamadas"]]
            out.append(d)
        return out

    def pensar(self, mensagens, ferramentas):
        corpo = {"model": self.modelo, "messages": self._msgs(mensagens), "temperature": .3}
        if ferramentas:
            corpo["tools"] = [{"type": "function", "function": f} for f in ferramentas]
        cab = {"Authorization": f"Bearer {self.chave}"} if self.chave else {}
        r = http_json(self.base + "/chat/completions", corpo, cab, timeout=180)
        msg = r["choices"][0]["message"]
        chamadas = [{"id": c["id"], "nome": c["function"]["name"],
                     "args": json.loads(c["function"].get("arguments") or "{}")} for c in (msg.get("tool_calls") or [])]
        return {"texto": msg.get("content") or "", "chamadas": chamadas}


class ProvedorOllama(ProvedorOpenAI):
    """Ollama local usando a API compatível com OpenAI (http://localhost:11434/v1). Sem chave."""
    nome = "ollama"
    def __init__(self):
        super().__init__(chave="ollama", base=os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/") + "/v1",
                         modelo=os.environ.get("OLLAMA_MODEL", "llama3.1"))


class ProvedorAnthropic(Provedor):
    nome = "anthropic"; visao = True
    def __init__(self):
        self.chave = os.environ.get("ANTHROPIC_API_KEY", "")
        self.modelo = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    def pensar(self, mensagens, ferramentas):
        sistema = "\n".join(m["texto"] for m in mensagens if m["papel"] == "sistema")
        msgs = []
        for m in mensagens:
            if m["papel"] == "sistema": continue
            if m["papel"] == "ferramenta":
                bloco = {"type": "tool_result", "tool_use_id": m["id"], "content": m["texto"]}
                msgs.append({"role": "user", "content": [bloco]}); continue
            blocos = []
            if m.get("texto"): blocos.append({"type": "text", "text": m["texto"]})
            if m.get("imagem_b64"):
                blocos.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": m["imagem_b64"]}})
            for c in m.get("chamadas") or []:
                blocos.append({"type": "tool_use", "id": c["id"], "name": c["nome"], "input": c["args"]})
            msgs.append({"role": "user" if m["papel"] == "usuario" else "assistant", "content": blocos or [{"type": "text", "text": "."}]})
        corpo = {"model": self.modelo, "max_tokens": 2048, "system": sistema, "messages": msgs,
                 "tools": [{"name": f["name"], "description": f["description"], "input_schema": f["parameters"]} for f in ferramentas]}
        r = http_json("https://api.anthropic.com/v1/messages", corpo,
                      {"x-api-key": self.chave, "anthropic-version": "2023-06-01"}, timeout=180)
        texto = "".join(b.get("text", "") for b in r["content"] if b["type"] == "text")
        chamadas = [{"id": b["id"], "nome": b["name"], "args": b["input"]} for b in r["content"] if b["type"] == "tool_use"]
        return {"texto": texto, "chamadas": chamadas}


class ProvedorRegras(Provedor):
    """Fallback sem chave: usa CerebroRegras.interpretar() do app/brain.py e traduz em chamadas de ferramentas."""
    nome = "regras"
    def __init__(self):
        try:
            from app.brain import cerebro
        except ImportError:
            cerebro = None
        self.cerebro = cerebro

    def pensar(self, mensagens, ferramentas):
        if mensagens and mensagens[-1]["papel"] == "ferramenta":
            return {"texto": "Feito.", "chamadas": []}       # uma rodada só: executa e encerra
        texto = next((m["texto"] for m in reversed(mensagens) if m["papel"] == "usuario"), "")
        t = texto.lower()
        nomes = {f["name"] for f in ferramentas}
        import re
        def ch(_ferr, **a): return {"id": uuid.uuid4().hex[:8], "nome": _ferr, "args": a}
        m = re.search(r"(?:com[eé]rcios?|lojas?|neg[oó]cios?)\s+sem\s+site.*?(?:de|tipo)?\s*([\wçãéêíóõú ]+?)\s+em\s+([\wçãéêíóõú ]+)$", t)
        if m and "buscar_comercios_sem_site" in nomes:
            return {"texto": "Procurando comércios sem site.", "chamadas": [ch("buscar_comercios_sem_site", cidade=m.group(2).strip().title(), categoria=m.group(1).strip())]}
        m = re.match(r"(?:pesquisa|pesquise|busca|busque|procura|procure|google)\s+(.+)", t)
        if m and "pesquisar_web" in nomes:
            return {"texto": "Pesquisando.", "chamadas": [ch("pesquisar_web", consulta=m.group(1))]}
        if re.search(r"\b(projeto|jogo)\b.*\bgodot\b|\bjogo 3d\b", t) and "criar_jogo_godot" in nomes:
            return {"texto": "Criando o projeto Godot.", "chamadas": [ch("criar_jogo_godot", nome="JogoJarvis")]}
        if re.search(r"anime 3d|cena 3d|render", t) and "blender_cena_anime" in nomes:
            return {"texto": "Abrindo o Blender em segundo plano.", "chamadas": [ch("blender_cena_anime", titulo=texto[:40])]}
        if re.search(r"anime 2d|sprite|anima[cç][aã]o 2d", t) and "anime2d_sprites" in nomes:
            return {"texto": "Desenhando os quadros 2D.", "chamadas": [ch("anime2d_sprites", nome="anime2d")]}
        if self.cerebro is None:
            return {"texto": "Sem LLM configurado.", "chamadas": []}
        resp, acoes = self.cerebro.interpretar(texto)
        return {"texto": resp, "chamadas": [ch("computador_acao", acao=a) for a in acoes]}


def escolher_provedor(nome=None) -> Provedor:
    nome = (nome or os.environ.get("JARVIS_LLM", "")).lower()
    if nome == "openai" or (not nome and os.environ.get("OPENAI_API_KEY")): return ProvedorOpenAI()
    if nome == "anthropic" or (not nome and os.environ.get("ANTHROPIC_API_KEY")): return ProvedorAnthropic()
    if nome == "ollama" or (not nome and os.environ.get("OLLAMA_MODEL")): return ProvedorOllama()
    return ProvedorRegras()
