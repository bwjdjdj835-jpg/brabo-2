"""Registro de ferramentas com schema tipado (JSON Schema gerado das anotações) e permissões.

Cada ferramenta declara um nível de risco:
  - "leitura": seguro (busca, leitura de página, listar)       -> executa direto
  - "arquivo": cria arquivos dentro de saidas/                  -> executa direto
  - "risco":   mexe no computador (mouse/teclado) ou roda programas -> exige controle LIGADO
               e, se confirmar=True, confirmação explícita do usuário.
"""
import inspect, json, time, threading, typing
from collections import deque
from dataclasses import dataclass, field

_TIPOS = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}


@dataclass
class Ferramenta:
    nome: str
    func: typing.Callable
    descricao: str
    risco: str = "leitura"
    confirmar: bool = False
    schema: dict = field(default_factory=dict)


class Permissoes:
    """Estado de segurança compartilhado (reaproveita o app.controle da v4 quando existe)."""
    def __init__(self):
        self.ligado = False                     # controle do PC DESLIGADO por padrão
        self.parado = threading.Event()         # PARAR / emergência
        self.confirmador = None                 # função(nome, args) -> bool ; None = negar o que exige confirmação
        self.controle = None                    # app.controle.Controle (opcional)

    @property
    def controle_ligado(self):
        return self.controle.ligado if self.controle is not None else self.ligado

    def parar(self, motivo="PARAR"):
        self.parado.set(); self.ligado = False
        if self.controle is not None: self.controle.emergencia(motivo)


class Registro:
    def __init__(self):
        self.ferramentas: dict[str, Ferramenta] = {}
        self.perm = Permissoes()
        self.log = deque(maxlen=300)          # atividade mostrada na interface 3D
        self.estado = {"trabalhando": False, "ferramenta": None, "desde": None}
        self.ouvintes = []

    def evento(self, tipo, texto, ok=True):
        e = {"hora": time.strftime("%H:%M:%S"), "tipo": tipo, "texto": str(texto)[:300], "ok": ok}
        self.log.append(e)
        if self.perm.controle is not None:      # aparece no painel LOG DE AÇÕES da v4
            self.perm.controle.registrar(tipo, e["texto"], ok)
        for f in self.ouvintes: f(e)

    def adicionar(self, func, risco="leitura", confirmar=False, nome=None):
        sig = inspect.signature(func); hints = typing.get_type_hints(func)
        props, req = {}, []
        for p in sig.parameters.values():
            t = hints.get(p.name, str); orig = typing.get_origin(t) or t
            props[p.name] = {"type": _TIPOS.get(orig, "string")}
            if p.default is inspect._empty: req.append(p.name)
            else: props[p.name]["default"] = p.default
        doc = inspect.getdoc(func) or ""
        f = Ferramenta(nome or func.__name__, func, doc.split("\n")[0], risco, confirmar,
                       {"type": "object", "properties": props, "required": req})
        self.ferramentas[f.nome] = f
        return func

    def descricoes(self):
        """Lista no formato 'tools' (OpenAI/Anthropic) – também usada no prompt do protocolo JSON."""
        return [{"name": f.nome, "description": f"{f.descricao} [risco: {f.risco}]", "parameters": f.schema}
                for f in self.ferramentas.values()]

    def chamar(self, nome, args=None):
        args = args or {}
        f = self.ferramentas.get(nome)
        if not f: return {"ok": False, "erro": f"ferramenta desconhecida: {nome}"}
        if self.perm.parado.is_set(): return {"ok": False, "erro": "PARADO pelo usuário (PARAR). Reinicie para continuar."}
        if f.risco == "risco":
            if not self.perm.controle_ligado:
                self.evento("recusado", f"{nome}: controle do PC DESLIGADO", False)
                return {"ok": False, "erro": "Controle do PC DESLIGADO. Ligue no botão do HUD para ações de risco."}
            if f.confirmar and not (self.perm.confirmador and self.perm.confirmador(nome, args)):
                self.evento("recusado", f"{nome}: sem confirmação do usuário", False)
                return {"ok": False, "erro": "Ação exige confirmação do usuário e não foi confirmada."}
        faltando = [r for r in f.schema["required"] if r not in args]
        if faltando: return {"ok": False, "erro": f"argumentos faltando: {faltando}"}
        extras = [k for k in args if k not in f.schema["properties"]]
        if extras: return {"ok": False, "erro": f"argumentos desconhecidos: {extras}; aceitos: {list(f.schema['properties'])}"}
        args = {k: v for k, v in args.items() if k in f.schema["properties"]}
        self.estado.update(trabalhando=True, ferramenta=nome, desde=time.time())
        self.evento("ferramenta", f"{nome}({json.dumps(args, ensure_ascii=False)[:160]})")
        try:
            r = f.func(**args)
            r = r if isinstance(r, dict) else {"ok": True, "resultado": r}
            r.setdefault("ok", True)
            self.evento("resultado", f"{nome}: " + ("ok" if r["ok"] else r.get("erro", "")), r["ok"])
            return r
        except Exception as e:
            self.evento("erro", f"{nome}: {e}", False)
            return {"ok": False, "erro": f"{type(e).__name__}: {e}"}
        finally:
            self.estado.update(trabalhando=False, ferramenta=None)


registro = Registro()


def ferramenta(risco="leitura", confirmar=False, nome=None):
    def deco(func): return registro.adicionar(func, risco, confirmar, nome)
    return deco
