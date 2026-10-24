"""Loop do agente: PLANEJAR -> CHAMAR FERRAMENTA -> OBSERVAR -> ... até responder ou atingir o limite.

    agente = Agente()                 # escolhe o LLM pelas variáveis de ambiente
    r = agente.executar("ache padarias sem site em Boa Vista e crie um site pra primeira")
    r["resposta"], r["passos"]

Observação visual: se uma ferramenta devolve {"imagem_b64": ...} (ex.: captura de tela) e o
provedor tem visão, a imagem é anexada na próxima mensagem para o modelo "ver" a tela.
"""
import json
from .llm import escolher_provedor
from .registro import registro

SISTEMA = """Você é o JARVIS, agente do Bruno, controlado pelo avatar Ryker. Fale português do Brasil.
Trabalhe em ciclos: pense no próximo passo, chame UMA ou mais ferramentas, observe o resultado e continue.
Para mexer no computador: primeiro `tela_capturar` para ver a tela, depois aja com coordenadas normalizadas (u,v de 0 a 1).
Ações de risco só funcionam com o controle LIGADO pelo usuário; se recusar, explique e peça para ligar.
Nunca invente resultados: use as ferramentas. Ao terminar, responda com um resumo curto do que fez e onde ficaram os arquivos."""


class Agente:
    def __init__(self, provedor=None, max_passos=12, reg=registro):
        from . import ferramentas  # noqa: F401  (registra todas as ferramentas)
        self.llm = provedor or escolher_provedor()
        self.reg = reg
        self.max_passos = max_passos
        self.historico = [{"papel": "sistema", "texto": SISTEMA}]

    def executar(self, pedido: str) -> dict:
        self.historico.append({"papel": "usuario", "texto": pedido})
        self.reg.evento("pedido", f"[{self.llm.nome}] {pedido}")
        passos = []
        for _ in range(self.max_passos):
            if self.reg.perm.parado.is_set():
                return {"resposta": "Parado pelo usuário.", "passos": passos, "provedor": self.llm.nome}
            self.reg.estado.update(trabalhando=True, ferramenta="pensando")
            try:
                r = self.llm.pensar(self.historico, self.reg.descricoes())
            except Exception as e:
                self.reg.evento("erro", f"LLM {self.llm.nome}: {e}", False)
                self.reg.estado.update(trabalhando=False, ferramenta=None)
                return {"resposta": f"Erro no provedor {self.llm.nome}: {e}", "passos": passos, "provedor": self.llm.nome}
            self.historico.append({"papel": "assistente", "texto": r["texto"], "chamadas": r["chamadas"]})
            if not r["chamadas"]:
                self.reg.estado.update(trabalhando=False, ferramenta=None)
                return {"resposta": r["texto"], "passos": passos, "provedor": self.llm.nome}
            imagem = None
            for c in r["chamadas"]:
                res = self.reg.chamar(c["nome"], c["args"])
                if res.get("imagem_b64"): imagem = res.pop("imagem_b64")
                passos.append({"ferramenta": c["nome"], "args": c["args"], "resultado": res})
                self.historico.append({"papel": "ferramenta", "id": c["id"], "texto": json.dumps(res, ensure_ascii=False)[:6000]})
            if imagem and getattr(self.llm, "visao", False):
                self.historico.append({"papel": "usuario", "texto": "Captura de tela atual (observação):", "imagem_b64": imagem})
        self.reg.estado.update(trabalhando=False, ferramenta=None)
        return {"resposta": "Limite de passos atingido.", "passos": passos, "provedor": self.llm.nome}
