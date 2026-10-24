"""Testes do motor:  python -m unittest discover -s motor/testes -t .   (na pasta jarvis/)"""
import json, os, sys, tempfile, types, unittest
from unittest import mock
sys.modules.setdefault("mouseinfo", types.ModuleType("mouseinfo"))
os.environ["JARVIS_SAIDAS"] = tempfile.mkdtemp(prefix="jarvis_teste_")
for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OLLAMA_MODEL", "JARVIS_LLM", "GOOGLE_MAPS_API_KEY", "SERPAPI_KEY"): os.environ.pop(k, None)

from motor import Agente, registro
from motor.llm import ProvedorRegras, escolher_provedor, ProvedorOpenAI
from motor.ferramentas import comercios, sites, anime2d, godot


class FakeControle:
    def __init__(self): self.ligado = False; self.feitas = []
    def registrar(self, *a): pass
    def emergencia(self, m=""): self.ligado = False
    def executar(self, a):
        if not self.ligado: return {"ok": False, "erro": "DESLIGADO"}
        self.feitas.append(a); return {"ok": True}
    def cursor_uv(self): return [.5, .5]


class TestRegistro(unittest.TestCase):
    def setUp(self):
        self.c = FakeControle(); registro.perm.controle = self.c; registro.perm.parado.clear(); registro.perm.confirmador = None

    def test_schema_tipado(self):
        d = {f["name"]: f for f in registro.descricoes()}
        for nome in ("pesquisar_web", "ler_pagina", "buscar_comercios_sem_site", "gerar_site", "blender_cena_anime",
                     "anime2d_sprites", "criar_jogo_godot", "computador_clicar", "tela_capturar", "computador_alvo"):
            self.assertIn(nome, d)
        p = d["computador_clicar"]["parameters"]
        self.assertEqual(p["properties"]["u"]["type"], "number"); self.assertEqual(p["required"], ["u", "v"])
        self.assertEqual(d["criar_jogo_godot"]["parameters"]["properties"]["exportar"]["type"], "boolean")

    def test_risco_recusado_com_controle_desligado(self):
        r = registro.chamar("computador_clicar", {"u": .5, "v": .5})
        self.assertFalse(r["ok"]); self.assertIn("DESLIGADO", r["erro"]); self.assertEqual(self.c.feitas, [])

    def test_risco_permitido_com_controle_ligado(self):
        self.c.ligado = True
        self.assertTrue(registro.chamar("computador_clicar", {"u": .2, "v": .3})["ok"])
        self.assertEqual(self.c.feitas[-1], {"tipo": "clicar", "u": .2, "v": .3})

    def test_confirmacao_obrigatoria(self):
        self.c.ligado = True
        self.assertFalse(registro.chamar("blender_executar_script", {"codigo": "print(1)"})["ok"])

    def test_parar_bloqueia_tudo(self):
        registro.perm.parar("teste")
        self.assertFalse(registro.chamar("pesquisar_web", {"consulta": "x"})["ok"])
        registro.perm.parado.clear()

    def test_argumento_faltando(self):
        self.assertIn("faltando", registro.chamar("gerar_site", {})["erro"])


class TestAgente(unittest.TestCase):
    def setUp(self): registro.perm.controle = FakeControle(); registro.perm.parado.clear()

    def test_sem_chave_usa_regras(self):
        self.assertIsInstance(escolher_provedor(), ProvedorRegras)
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "x"}): self.assertIsInstance(escolher_provedor(), ProvedorOpenAI)

    def test_regras_viram_ferramenta_de_pc(self):
        r = Agente(ProvedorRegras()).executar("clica no meio da tela")
        self.assertEqual(r["passos"][0]["ferramenta"], "computador_acao")
        self.assertFalse(r["passos"][0]["resultado"]["ok"])      # controle desligado -> recusado

    def test_regras_roteiam_ferramentas(self):
        p = ProvedorRegras(); nomes = [f["name"] for f in registro.descricoes()]
        for txt, esperado in (("cria um jogo 3d no godot", "criar_jogo_godot"), ("faz um anime 2d", "anime2d_sprites"),
                              ("comércios sem site de padarias em Boa Vista", "buscar_comercios_sem_site"), ("pesquisa padarias boa vista", "pesquisar_web")):
            r = p.pensar([{"papel": "usuario", "texto": txt}], registro.descricoes())
            self.assertEqual(r["chamadas"][0]["nome"], esperado, txt)

    def test_loop_com_llm_falso(self):
        class LLMFalso:
            nome = "falso"; visao = False; n = 0
            def pensar(self, msgs, tools):
                self.n += 1
                if self.n == 1: return {"texto": "", "chamadas": [{"id": "1", "nome": "anime2d_sprites", "args": {"quadros": 3, "tamanho": 64}}]}
                assert msgs[-1]["papel"] == "ferramenta"; return {"texto": "pronto", "chamadas": []}
        r = Agente(LLMFalso()).executar("faça um anime 2d")
        self.assertEqual(r["resposta"], "pronto"); self.assertTrue(r["passos"][0]["resultado"]["ok"])

    def test_openai_formato_tools(self):
        resp = {"choices": [{"message": {"content": None, "tool_calls": [{"id": "a", "function": {"name": "pesquisar_web", "arguments": "{\"consulta\": \"padaria\"}"}}]}}]}
        with mock.patch("motor.llm.http_json", return_value=resp) as h:
            r = ProvedorOpenAI(chave="k").pensar([{"papel": "usuario", "texto": "oi"}], registro.descricoes())
        self.assertEqual(r["chamadas"][0]["args"], {"consulta": "padaria"}); self.assertIn("tools", h.call_args[0][1])


class TestFerramentas(unittest.TestCase):
    def test_comercios_osm_mock(self):
        falso = {"elements": [{"type": "node", "id": 1, "lat": 2.8, "lon": -60.7, "tags": {"name": "Padaria A", "phone": "+55 95 9999-0000"}},
                              {"type": "node", "id": 2, "lat": 2.8, "lon": -60.7, "tags": {"name": "Padaria B", "website": "https://b.com"}},
                              {"type": "way", "id": 3, "center": {"lat": 2.8, "lon": -60.7}, "tags": {"shop": "bakery"}}]}
        with mock.patch.object(comercios, "_overpass", return_value=falso):
            r = comercios.buscar_comercios_sem_site("Boa Vista", "padarias")
        self.assertEqual((r["total"], r["sem_site"]), (2, 1)); self.assertTrue(os.path.exists(r["csv"]))
        self.assertIn("Padaria A", open(r["csv"], encoding="utf-8-sig").read())

    def test_site(self):
        r = sites.gerar_site("Padaria Teste", "padaria", "Boa Vista", "Rua 1", "(95) 99999-0000", lat=2.8, lon=-60.7)
        h = open(r["index"], encoding="utf-8").read()
        for x in ("Padaria Teste", "wa.me/5595999990000", "application/ld+json", "openstreetmap.org/export/embed", 'name="viewport"'): self.assertIn(x, h)
        self.assertTrue(os.path.exists(os.path.join(r["pasta"], "app.js")))

    def test_anime2d(self):
        r = anime2d.anime2d_sprites("t", 4, 64)
        from PIL import Image
        self.assertEqual(Image.open(r["spritesheet"]).size, (256, 64)); self.assertTrue(os.path.exists(r["gif"]))
        self.assertTrue(open(anime2d.anime2d_svg("ryker")["svg"]).read().startswith("<svg"))

    def test_godot_scaffold(self):
        with mock.patch.object(godot, "achar_godot", return_value=None):
            r = godot.criar_jogo_godot("Teste")
        self.assertIn("player.gd", r["arquivos"]); self.assertIn('run/main_scene="res://main.tscn"', open(os.path.join(r["pasta"], "project.godot")).read())


if __name__ == "__main__":
    unittest.main()
