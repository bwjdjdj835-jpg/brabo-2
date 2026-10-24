"""J.A.R.V.I.S. - assistente de voz para Windows."""
import os

# Deixa a interface tocar a voz sem precisar de um clique antes
os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--autoplay-policy=no-user-gesture-required")

# Carrega o .NET (usado pela janela do pywebview) antes de qualquer outra thread existir: carregado depois,
# com as threads do Jarvis já rodando, às vezes trava para sempre e a janela não abre.
if __name__ == "__main__":
    try:
        import clr  # noqa: F401
    except Exception:
        pass

import asyncio
import base64
import datetime
import difflib
import json
import logging
import platform
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

import edge_tts
import psutil
import speech_recognition as sr
import webview

import biblioteca
import claude_code
import engenharia
import enviar_email
import memoria
import identidade
import segredos
import servidor
import telegram_bot
from comandos import executar, normalizar, tempo_falado

PASTA = os.path.dirname(os.path.abspath(__file__))
DISCO = os.environ.get("SystemDrive", "C:") + "\\"
VOZ = "pt-BR-AntonioNeural"

# O reconhecimento de voz às vezes escreve "Jarvis" e "Braga" de outros jeitos
VARIACOES = re.compile(r"(jarv\w*|djarv\w*|jerv\w*|javis|jarbas|jar|jorge|jarviz|chaves|charles"
                       r"|braga|bragas|bragga|draga|braca)")
SAIR = re.compile(r"^(pode\s+)?(se\s+)?(fecha\w*|encerr\w*|desativ\w*|sair|descansa\w*|desliga\w*)"
                  r"(\s+(o\s+)?(jarvis|braga))?$")
RECALIBRAR_A_CADA = 180  # segundos

log = logging.getLogger("jarvis")


def _eh_jarvis(palavra):
    """A palavra é o chamado do assistente ("Braga" ou "Jarvis", com os jeitos que o reconhecimento escreve)?"""
    return (bool(VARIACOES.fullmatch(palavra))
            or difflib.SequenceMatcher(None, palavra, "jarvis").ratio() >= 0.7
            or difflib.SequenceMatcher(None, palavra, "braga").ratio() >= 0.8)


# Palavras que podem vir antes do chamado: "ei Jarvis", "ok Jarvis", "bom dia Jarvis"
ANTES_DO_CHAMADO = {"ei", "ey", "hey", "oi", "ola", "ok", "okay", "fala", "e", "ai", "o", "bom", "boa", "dia", "tarde",
                    "noite", "alo", "salve", "opa"}


def separar_chamado(texto):
    """Se a frase chama o Jarvis (no começo ou no fim), devolve o comando sem o chamado. Senão, None.
    "Jarvis" no meio de um pedido ("pesquisa jarvis no youtube") é assunto, não chamado."""
    texto = texto.strip()
    palavras = list(re.finditer(r"\w+", normalizar(texto)))
    for n, palavra in enumerate(palavras[:3]):
        if _eh_jarvis(palavra.group()) and all(p.group() in ANTES_DO_CHAMADO for p in palavras[:n]):
            return texto[palavra.end():].strip(" ,.!?")
    if len(palavras) > 3 and _eh_jarvis(palavras[-1].group()):
        # "baixa os vídeos do Jarvis": aqui "Jarvis" é o assunto, não o chamado
        if palavras[-2].group() in ("de", "do", "da", "dos", "sobre", "tiver", "tenha", "tem", "com", "chamado", "o",
                                    "um", "fazer", "criar", "montar", "programar", "construir"):
            return texto
        return texto[:palavras[-1].start()].strip(" ,.!?")
    return None


class Jarvis:
    def __init__(self):
        self._janela = None
        self._trava = threading.Lock()
        self._falando = threading.Event()
        self._ouvir_agora = threading.Event()
        self._iniciado = False
        self._mic_ligado = True
        self._estado = None
        self._pendente = None      # confirmação por voz: callable -> str, à espera de "sim"/"não"
        self._pendente_tg = None   # confirmação pelo Telegram, separada da voz
        self._bot = None           # bot do Telegram, se ligado
        self._aba_ativa = "jarvis"  # aba na frente da interface ("navegador" = mini tela)
        self._url_mini = ""         # site aberto na mini tela
        self._lembretes = []       # lembretes, timers e avisos do modo foco agendados

    # ---------- chamados pela interface ----------
    def pronto(self):
        if self._iniciado:
            return
        self._iniciado = True
        threading.Thread(target=self._saudar_e_ouvir, daemon=True).start()

    def comando_texto(self, texto):
        threading.Thread(target=self._processar, args=(texto,), daemon=True).start()

    def ouvir_agora(self):
        """Botão de falar: o próximo comando não precisa de "Jarvis"."""
        if self._mic_ligado and not self._falando.is_set():
            self._ouvir_agora.set()
            self._mudar_estado("escutando")

    def fim_fala(self):
        self._falando.clear()

    def alternar_microfone(self):
        self._mic_ligado = not self._mic_ligado
        if self._mic_ligado:
            threading.Thread(target=self._falar, args=("Estou ouvindo, senhor.",),
                             kwargs={"lembrar": False}, daemon=True).start()
        elif not self._falando.is_set():
            self._estado_parado()
        return self._mic_ligado

    # ---------- biblioteca ----------
    def anexar(self):
        """Botão de anexar: abre a janela do Windows para escolher arquivos."""
        tipo = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        escolhidos = self._janela.create_file_dialog(tipo, allow_multiple=True) or []
        for caminho in escolhidos:
            self._guardar(lambda c=caminho: biblioteca.adicionar_arquivo(c), os.path.basename(caminho))
        return len(escolhidos)

    def receber_arquivo(self, nome, conteudo_base64):
        """Arquivo arrastado para a janela ou imagem colada (Ctrl+V)."""
        dados = base64.b64decode(conteudo_base64)
        self._guardar(lambda: biblioteca.adicionar_bytes(nome, dados), nome)

    # ---------- sua linguagem de comandos (meus_comandos.json) ----------
    def comandos_listar(self):
        import comandos_usuario
        return comandos_usuario.listar()

    def _sequencia(self, pedido):
        """Roda, em ordem, as frases de um comando seu, como se o senhor tivesse falado cada uma."""
        import comandos_usuario
        profundidade = pedido.get("_profundidade", 0)
        self._ui("atividade", f"Comando: {pedido.get('nome', '')}")
        falas = []
        for frase in pedido.get("frases", [])[:comandos_usuario.MAX_PASSOS]:
            self._ui("atividade", f"→ {frase}")
            try:
                resposta = executar(frase)
                if isinstance(resposta, dict):
                    if resposta.get("acao") in comandos_usuario.ACOES_PROIBIDAS_NA_SEQUENCIA:
                        log.warning("Sequência pulou %r (não permitido dentro de comandos)", frase)
                        continue
                    if resposta.get("acao") == "sequencia":
                        if profundidade >= 2:  # um comando chamando outro sem fim
                            log.warning("Sequência parou em %r: comandos demais um dentro do outro", frase)
                            continue
                        resposta["_profundidade"] = profundidade + 1
                    resposta = self._acao(resposta)
            except Exception:
                log.exception("Falha no passo %r da sequência", frase)
                resposta = None
            if resposta:
                falas.append(resposta)
            time.sleep(0.3)  # dá tempo de a interface acompanhar (abas, mini tela)
        if not falas:
            return "Feito, senhor."
        texto = " ".join(falas)
        return texto if len(texto) < 400 else f"Pronto, senhor. Fiz os {len(falas)} passos do comando."

    def _criar_comando(self, prompt):
        """O Claude transforma o pedido num comando; o Jarvis lê de volta e só salva se o senhor confirmar."""
        if len(prompt.split()) < 3:
            return ("Diga o comando inteiro, senhor. Por exemplo: cria um comando, quando eu disser modo trabalho, "
                    "abre o gmail na mini tela e liga o modo foco.")

        def trabalho():
            import comandos_usuario
            self._ui("atividade", "Transformando o pedido em comando…")
            comando, motivo = comandos_usuario.criar_do_prompt(prompt)
            with self._trava:
                if not comando:
                    self._falar(f"Não consegui criar esse comando, senhor: {motivo}.")
                else:
                    def salvar():
                        comandos_usuario.salvar(comando)
                        self._ui("comandos", comandos_usuario.listar())
                        return f"Comando salvo, senhor. É só dizer: {comando['frases'][0]}."
                    self._pendente = salvar
                    self._ui("comandoProposto", comando["frases"], comandos_usuario.descrever(comando))
                    frases = " ou ".join(comando["frases"][:2]).replace("{", "").replace("}", "")
                    self._falar(f"Quando o senhor disser {frases}, eu vou: {comandos_usuario.descrever(comando)} "
                                "Salvo o comando?")
                self._estado_parado()

        threading.Thread(target=trabalho, daemon=True).start()
        return "Vou transformar isso num comando, senhor. Um momento."

    def _apagar_comando(self, nome):
        import comandos_usuario
        achados = comandos_usuario.buscar(nome)
        if not achados:
            return "Não achei esse comando, senhor. Diga: quais são meus comandos, para ouvir a lista."
        if len(achados) > 1:
            return "Achei mais de um comando com esse nome, senhor: " + ", ".join(c["frases"][0] for c in achados[:4]) + "."
        comando = achados[0]

        def apagar():
            comandos_usuario.remover(comando)
            self._ui("comandos", comandos_usuario.listar())
            return "Comando apagado, senhor."

        self._pendente = apagar
        return f"Vou apagar o comando {comando['frases'][0]}. Confirma?"

    # ---------- skills: habilidades novas a partir de um link do GitHub (só texto, com o "sim") ----------
    def skills_listar(self):
        import skills
        return [{k: s[k] for k in ("nome", "titulo", "descricao", "origem")} for s in skills.listar()]

    def _skill_instalar(self, link):
        if not link:
            return ("Cole o link do repositório do GitHub, senhor. Por exemplo: instala a skill "
                    "github.com/anthropics/skills/tree/main/skills/pdf")

        def trabalho():
            import skills
            self._ui("tarefa", "Procurando a skill", link)
            try:
                achadas = skills.procurar(link)
            except Exception as erro:
                log.warning("Skill: falha ao ler %s", link, exc_info=True)
                achadas, motivo = [], str(erro)[:150]
            else:
                motivo = "não achei SKILL.md nem README nesse repositório"
            self._ui("tarefa", None, None)
            with self._trava:
                if not achadas:
                    self._falar(f"Não consegui pegar a skill, senhor: {motivo}.")
                    self._estado_parado()
                    return

                def instalar():
                    nomes = [skills.instalar(s) for s in achadas]
                    self._ui("skills", self.skills_listar())
                    return (f"Skill {nomes[0]} instalada, senhor. Quando o pedido combinar com ela, eu uso."
                            if len(nomes) == 1 else f"Instalei {len(nomes)} skills, senhor: {', '.join(nomes[:6])}.")

                self._pendente = instalar
                for s in achadas:
                    self._ui("nota", f"Skill {s['nome']}: {s['descricao'][:200]} ({len(s['arquivos'])} arquivos de texto)")
                if len(achadas) == 1:
                    fala = (f"Achei a skill {achadas[0]['nome']}. {achadas[0]['descricao'][:180]} "
                            "Ela é só texto de instruções; não roda nada do repositório. Instalo? Confirma?")
                else:
                    fala = (f"Achei {len(achadas)} skills nesse repositório: "
                            f"{', '.join(s['nome'] for s in achadas[:6])}. São só textos de instruções. "
                            "Instalo todas? Confirma?")
                self._falar(fala)
                self._estado_parado()

        threading.Thread(target=trabalho, daemon=True).start()
        return "Vou ler o repositório e ver que skill ele tem, senhor."

    def _skill_apagar(self, nome):
        import skills
        achadas = skills.buscar(nome)
        if not achadas:
            return "Não achei essa skill, senhor. Diga: quais são minhas skills."
        skill = achadas[0]

        def apagar():
            skills.remover(skill["nome"])
            self._ui("skills", self.skills_listar())
            return "Skill apagada, senhor."

        self._pendente = apagar
        return f"Vou apagar a skill {skill['nome']}. Confirma?"

    # ---------- mini tela: navegador do Jarvis dentro da interface ----------
    def contexto_interface(self, aba, url=""):
        """A interface avisa qual aba está na frente e o site da mini tela."""
        self._aba_ativa = str(aba or "jarvis")
        if url:
            self._url_mini = str(url)

    # ---------- WhatsApp: um contato por vez, com o "sim" do senhor ----------
    def _whatsapp_conectar(self):
        """Abre o WhatsApp Web na mini tela (e na flutuante) para o senhor ler o QR Code uma vez."""
        def trabalho():
            import whatsapp
            try:
                self._aba_ativa = "navegador"
                self._ui("abrirNavegador")
                estado = whatsapp.situacao()
                self.abrir_pip()
                fala = {"logado": "O WhatsApp está conectado, senhor. Já posso mandar as mensagens quando o senhor pedir.",
                        "qr": "Aparece um QR Code na mini tela. No celular, abra o WhatsApp, toque em Aparelhos "
                              "conectados, depois em Conectar um aparelho, e aponte para a mini tela."}.get(
                    estado, "O WhatsApp Web ainda está carregando na mini tela, senhor. Espere um pouco e pergunte de novo.")
            except Exception as erro:
                log.exception("WhatsApp: falha ao conectar")
                fala = f"Não consegui abrir o WhatsApp Web, senhor. {str(erro)[:120]}"
            with self._trava:
                self._falar(fala)
                self._estado_parado()

        threading.Thread(target=trabalho, daemon=True).start()
        return "Abrindo o WhatsApp Web na mini tela, senhor."

    def _whatsapp_preparar(self, alvo, com_video):
        """Mostra para quem vai e o quê, e só envia depois do "sim". Um contato por pedido."""
        import whatsapp
        pasta, contato = whatsapp.achar_em_todas(alvo)
        if not pasta:
            return "Ainda não tenho contatos, senhor. Faça antes uma prospecção ou a fábrica de sites."
        if not contato:
            return ("Não achei esse contato na última lista, senhor. Diga o nome, o número dele na lista, "
                    "ou: manda pro próximo.")
        if not contato.get("whatsapp"):
            return f"{contato['nome']} não tem celular no Google Maps, senhor. Esse precisa ser por ligação."
        if contato.get("enviado"):
            return f"Já mandei para {contato['nome']} em {contato['enviado']}, senhor. Não vou mandar de novo."
        if whatsapp.enviados_hoje() >= whatsapp.LIMITE_POR_DIA:
            return (f"Já foram {whatsapp.LIMITE_POR_DIA} mensagens hoje, senhor. Paro por aqui para o WhatsApp não "
                    "bloquear o seu número. Amanhã continuo.")
        video = os.path.join(pasta, contato["video"]) if com_video and contato.get("video") else None
        if com_video and not (video and os.path.exists(video)):
            return f"Não achei o vídeo de {contato['nome']} na pasta, senhor. Posso mandar só a mensagem."

        def enviar():
            def trabalho():
                self._ui("tarefa", "WhatsApp", contato["nome"])
                try:
                    whatsapp.enviar(contato, contato["mensagem"], video)
                    whatsapp.marcar_enviado(pasta, contato, video)
                    fala = f"Mensagem enviada para {contato['nome']}, senhor" + (", com o vídeo." if video else ".")
                except Exception as erro:
                    log.exception("WhatsApp: falha ao enviar para %s", contato["nome"])
                    fala = f"Não consegui mandar para {contato['nome']}, senhor: {str(erro)[:150]}"
                self._ui("tarefa", None, None)
                with self._trava:
                    self._falar(fala)
                    self._estado_parado()

            self._aba_ativa = "navegador"
            self._ui("abrirNavegador")
            threading.Thread(target=trabalho, daemon=True).start()
            return "Mandando, senhor. Acompanhe na mini tela."

        self._pendente = enviar
        self._ui("nota", f"✆ {contato['nome']} · {contato['telefone']}\n{contato['mensagem']}"
                         + (f"\n+ vídeo {contato['video']}" if video else ""))
        return (f"Vou mandar para {contato['nome']}, {contato['telefone']}, a mensagem perguntando se quer ver a "
                f"prévia do site{', e o vídeo' if video else ''}. Confirma?")

    # ---------- mini tela flutuante: janelinha sempre por cima, com o navegador do Braga ao vivo ----------
    def abrir_pip(self):
        """Abre (ou traz para a frente) a mini tela flutuante, no canto de baixo à direita."""
        import navegador
        if getattr(self, "_pip", None) is not None:
            try:
                self._pip.restore()
                self._pip.show()
                return "A mini tela flutuante já está aberta, senhor."
            except Exception:
                self._pip = None
        try:
            navegador.preparar()
        except Exception as erro:
            log.warning("Mini tela flutuante: navegador não ligou", exc_info=True)
            return f"Não consegui ligar o navegador, senhor. {str(erro)[:120]}"
        largura, altura = 440, 300
        try:
            tela = webview.screens[0]
            x, y = tela.width - largura - 24, tela.height - altura - 64  # acima da barra de tarefas
        except Exception:
            x, y = None, None
        self._pip = webview.create_window(
            "Braga · mini tela", servidor.iniciar() + "/interface/pip.html", js_api=self,
            width=largura, height=altura, x=x, y=y, min_size=(260, 180), on_top=True, frameless=True,
            easy_drag=False, background_color="#020a12")
        self._pip.events.closed += lambda: setattr(self, "_pip", None)
        return "Abri a mini tela flutuante, senhor. Ela fica por cima das outras janelas; arraste pela barrinha."

    def fechar_pip(self):
        if getattr(self, "_pip", None) is not None:
            janela, self._pip = self._pip, None
            janela.destroy()
        return "Fechei a mini tela flutuante, senhor."

    def mostrar_principal(self):
        """Botão ⤢ da mini tela flutuante: traz a janela principal do Braga para a frente."""
        try:
            self._janela.restore()
            self._janela.show()
        except Exception:
            log.debug("Não consegui trazer a janela principal", exc_info=True)

    def navegador_info(self):
        import navegador
        return {"quadro": f"/navegador/{servidor.TOKEN}/quadro.jpg",
                "largura": navegador.LARGURA, "altura": navegador.ALTURA}

    def navegador_acao(self, tipo, valor=None, extra=None):
        """Cliques, rolagem, teclas e endereço vindos da mini tela. Devolve a url e o título atuais."""
        import navegador
        try:
            if tipo == "abrir":
                navegador.abrir(valor or navegador.INICIO)
            elif tipo == "clicar":
                navegador.clicar(float(valor), float(extra))
            elif tipo == "rolar":
                navegador.rolar_pixels(int(valor))
            elif tipo == "tecla":
                navegador.tecla(str(valor))
            elif tipo == "digitar":
                navegador.digitar(str(valor))
            elif tipo in ("voltar", "avancar", "recarregar"):
                getattr(navegador, tipo)()
            estado = navegador.estado()
            self._url_mini = estado.get("url") or self._url_mini
            return estado
        except Exception as erro:
            log.warning("Mini tela: falha em %s", tipo, exc_info=True)
            return {"erro": str(erro)[:200]}

    # ---------- mini notebook: a tela real do notebook ao vivo, com mouse e teclado de verdade ----------
    def notebook_info(self):
        import notebook
        return {"quadro": f"/tela/{servidor.TOKEN}/quadro.jpg", **notebook.info(), **notebook.sessao.estado()}

    def notebook_estado(self):
        import notebook
        return {**notebook.sessao.estado(), "freio": notebook.controle.freio, "cursor": notebook.cursor()}

    def notebook_acao(self, tipo, x=None, y=None, valor=None):
        """Cliques, rolagem, teclas e os botões pausar/parar/freio vindos do mini notebook."""
        import notebook
        try:
            estado = notebook.executar(tipo, x, y, valor)
        except Exception as erro:  # inclui o freio do canto (pyautogui.FailSafeException)
            log.warning("Mini notebook: falha em %s", tipo, exc_info=True)
            estado = {**notebook.sessao.estado(), "erro": str(erro)[:200]}
        return {**estado, "freio": notebook.controle.freio}

    def abrir_notebook_flutuante(self):
        """Notebook flutuante: a tela real em miniatura, sempre por cima, com pausar/parar e o registro."""
        import notebook
        if getattr(self, "_nb", None) is not None:
            try:
                self._nb.restore()
                self._nb.show()
                return "O notebook flutuante já está aberto, senhor."
            except Exception:
                self._nb = None
        largura, altura = 460, 340
        try:
            tela_principal = webview.screens[0]
            x, y = tela_principal.width - largura - 24, tela_principal.height - altura - 64
        except Exception:
            x, y = None, None
        self._nb = webview.create_window(
            notebook.TITULO_FLUTUANTE, servidor.iniciar() + "/interface/notebook.html", js_api=self,
            width=largura, height=altura, x=x, y=y, min_size=(300, 220), on_top=True, frameless=True,
            easy_drag=False, background_color="#050b16")
        self._nb.events.closed += lambda: setattr(self, "_nb", None)
        return "Abri o notebook flutuante, senhor. Ele fica por cima das outras janelas."

    def fechar_notebook_flutuante(self):
        if getattr(self, "_nb", None) is not None:
            janela, self._nb = self._nb, None
            janela.destroy()
        return "Fechei o notebook flutuante, senhor."

    def _notebook_controle(self, tipo, texto=""):
        """Voz: "pausa o notebook", "continua o notebook", "para o notebook", correções no meio da tarefa."""
        import notebook
        if not notebook.sessao.controlando:
            return "Não estou controlando o notebook agora, senhor."
        notebook.executar(tipo, valor=texto)
        return {"pausar": "Pausei, senhor. Diga continua o notebook quando quiser.", "retomar": "Continuando, senhor.",
                "parar": "Parando, senhor.", "corrigir": "Entendi a correção, senhor."}.get(tipo, "Feito, senhor.")

    def _abrir_mini_tela(self, alvo, buscador="bing"):
        """Abre um site (ou uma busca, no Bing por padrão) no navegador do Jarvis e mostra a mini tela."""
        import navegador

        def abrir():
            self._ui("atividade", "Abrindo na mini tela…")
            try:
                self._url_mini = navegador.abrir(alvo or navegador.INICIO, buscador) or self._url_mini
                self._aba_ativa = "navegador"  # a interface confirma em seguida, mas o próximo comando já vale
                self._ui("abrirNavegador")
            except Exception as erro:
                log.exception("Falha ao abrir a mini tela: %s", alvo)
                motivo = str(erro) if isinstance(erro, navegador.Bloqueado) else "Veja os detalhes no registro."
                with self._trava:
                    self._falar(f"Não consegui abrir a mini tela, senhor. {motivo}")
                    self._estado_parado()

        threading.Thread(target=abrir, daemon=True).start()
        if navegador.ligado():
            return "Abrindo na mini tela, senhor."
        return "Abrindo na mini tela, senhor. Na primeira vez o navegador leva alguns segundos para ligar."

    def _prospeccao(self, busca, quantidade=5):
        """Código B/107108109110 300-300: comércios do Maps -> prévias -> vídeos -> página com as mensagens prontas.
        O envio fica com o usuário, um por um (disparo automático em massa bane o número e é proibido)."""
        if not busca:
            return "Qual ramo e cidade, senhor? Por exemplo: prospecção completa de barbearias em Cacoal."
        if getattr(self, "_prospectando", False):
            return "Ainda estou na prospecção anterior, senhor. Aviso quando terminar."
        self._prospectando = True

        def trabalho():
            import navegador
            import prospeccao
            self._ui("tarefa", "Prospecção completa", busca)
            try:
                navegador.preparar()
                self._aba_ativa = "navegador"
                self._ui("abrirNavegador")  # o senhor acompanha tudo na mini tela
                r = prospeccao.executar(busca, quantidade, lambda t: self._ui("atividade", t))
                atalho = self._entregar_pasta(r["pasta_envio"])
                fala = (f"Pronto, senhor. Encontrei {r['negocios']} comércios, fiz as prévias e gravei {r['videos']} "
                        f"vídeos em MP4. {r['com_whatsapp']} têm celular para WhatsApp. Abri a pasta de envios"
                        f"{f' e criei o atalho {identidade.NOME} Envios na área de trabalho' if atalho else ''}: lá estão os "
                        "vídeos e o arquivo Contatos para enviar, com os números e as mensagens. Envie um por um.")
            except Exception as erro:
                log.exception("Falha na prospecção: %s", busca)
                fala = f"Não consegui terminar a prospecção, senhor. {str(erro)[:150]}"
            finally:
                self._prospectando = False
            self._ui("tarefa", None, None)
            with self._trava:
                self._falar(fala)
                self._estado_parado()

        threading.Thread(target=trabalho, daemon=True).start()
        return (f"Começando a prospecção de {busca}, senhor: até {quantidade} comércios. Vou mostrando na mini tela; "
                "leva alguns minutos.")

    def _entregar_pasta(self, pasta):
        """Fim de prospecção ou fábrica: atalho "Jarvis - Envios" na Área de Trabalho apontando para a pasta (com os
        vídeos MP4 e os contatos) e a pasta aberta na tela. Devolve o atalho, ou None se não deu para criar."""
        import isolamento
        import prospeccao
        self._ui("nota", pasta)
        atalho = None
        if not isolamento.ligado():  # no modo isolado a área de trabalho do PC fica como está
            try:
                atalho = prospeccao.atalho_na_area_de_trabalho(pasta)
                self._ui("nota", atalho)
            except Exception:
                log.warning("Não consegui criar o atalho de envios", exc_info=True)
        _mostrar_arquivo(pasta)
        return atalho

    def _fabrica_sites(self, busca, quantidade=3, preco=None, completo=False, no_notebook=False):
        """Código B/07070707: negócios sem site no Maps -> print -> domínio -> modelo -> site -> zip -> vídeo ->
        mensagem. No fim pergunta se pode publicar no GitHub Pages (público: só com o "sim" do senhor).
        completo (código /700): o preço entra na mensagem e, depois dos sites, vem o login do GitHub na mini tela,
        a publicação (com o "sim") e o WhatsApp pronto (envio um por vez, com o "sim").
        no_notebook (código C/19708090): tudo aparece no notebook 3D (navegador do Braga), confirma na web que não
        tem site, cada comércio ganha um skin novo do ramo e, no fim, o WhatsApp Web pergunta um por um."""
        if not busca:
            return "Qual ramo e cidade, senhor? Por exemplo: fábrica de sites de barbearias em Cacoal."
        if getattr(self, "_fabricando", False):
            return "Ainda estou fazendo os sites anteriores, senhor. Aviso quando terminar."
        self._fabricando = True

        def trabalho():
            import fabrica_sites
            import navegador
            self._ui("tarefa", "Fábrica de sites", busca)
            pasta = r = None
            try:
                navegador.preparar()
                if no_notebook:
                    self.mostrar_principal()
                    self._ui("abrirNotebook", "navegador")  # a tela do notebook 3D mostra o navegador do Braga
                else:
                    self._aba_ativa = "navegador"
                    self._ui("abrirNavegador")
                r = fabrica_sites.executar(busca, quantidade, lambda t: self._ui("atividade", t), preco=preco,
                                           confirmar_web=no_notebook, skins=no_notebook)
                pasta = r["pasta"]
                atalho = self._entregar_pasta(r["pasta_envio"])
                videos = sum(1 for i in r["itens"] if i.get("video"))
                livres = sum(1 for i in r["itens"] if any(d["situacao"] == "livre" for d in i["dominios"]))
                fala = (f"Pronto, senhor. Achei {len(r['itens'])} negócios sem site e fiz um site para cada um, com print, "
                        f"zip e {videos} vídeos em MP4. {livres} têm domínio livre. Abri a pasta de envios"
                        f"{f' e criei o atalho {identidade.NOME} Envios na área de trabalho' if atalho else ''}: lá estão os "
                        "vídeos e o arquivo Contatos para enviar.")
            except Exception as erro:
                log.exception("Falha na fábrica de sites: %s", busca)
                fala = f"Não consegui terminar os sites, senhor. {str(erro)[:150]}"
            finally:
                self._fabricando = False
            self._ui("tarefa", None, None)
            if r and r.get("descartados"):
                fala += f" Deixei de fora {len(r['descartados'])} que já têm site, conferindo na internet."
            with self._trava:
                if pasta and not completo and not no_notebook:
                    fala += " " + self._preparar_publicacao(pasta)
                self._falar(fala)
                self._estado_parado()
            if pasta and completo:
                self._etapa_github(pasta)
            if pasta and no_notebook:
                self._whatsapp_em_sequencia(r["pasta_envio"])

        if completo:
            self._github_oferecido = True  # o /700 pergunta do jeito dele; o vigia não pergunta de novo
        threading.Thread(target=trabalho, daemon=True).start()
        return (f"Começando a fábrica de sites de {busca}, senhor: até {quantidade} negócios sem site. "
                "Vou mostrando na mini tela; leva alguns minutos.")

    def _prospeccao_notebook(self, busca):
        """Código C/19708090: o tipo de comércio + cidade ("pet shop em Cacoal"), tudo no notebook 3D."""
        busca = (busca or "").strip(" .")
        if not busca:
            return "Qual tipo de comércio e cidade, senhor? Por exemplo: C/19708090 pet shop em Cacoal."
        if " em " not in f" {busca.lower()} ":
            busca += " em Cacoal"  # a cidade padrão é Cacoal
        return self._fabrica_sites(busca, 3, no_notebook=True)

    def _whatsapp_em_sequencia(self, pasta_envio):
        """C/19708090, fim: WhatsApp Web no notebook 3D. Se pedir o QR Code, pausa e avisa; quando o senhor
        escanear, continua sozinho. Depois pergunta comércio por comércio: cada mensagem só sai com o "sim"."""
        import whatsapp

        def falar(texto):
            with self._trava:
                self._falar(texto)
                self._estado_parado()

        try:
            self._ui("abrirNotebook", "navegador")
            estado = whatsapp.situacao()
            if estado != "logado":
                self._ui("tarefa", "Esperando o QR Code do WhatsApp", "leia com o celular")
                falar("O WhatsApp pediu o QR Code, senhor. Ele está na tela do mini notebook. No celular: WhatsApp, "
                      "Aparelhos conectados, Conectar um aparelho. Eu espero e continuo sozinho.")
                fim = time.time() + 600
                while estado != "logado" and time.time() < fim:
                    time.sleep(5)
                    estado = whatsapp.situacao(espera=10)
                self._ui("tarefa", None, None)
                if estado != "logado":
                    falar("Não vi o WhatsApp conectar em 10 minutos, senhor. Quando ler o QR Code, diga: manda a "
                          "mensagem pro próximo.")
                    return
                falar("WhatsApp conectado, senhor. Continuando.")
        except Exception as erro:
            log.exception("C/19708090: WhatsApp não abriu")
            falar(f"Não consegui abrir o WhatsApp Web, senhor. {str(erro)[:120]}")
            return
        self._oferecer_proximo(pasta_envio)

    def _oferecer_proximo(self, pasta):
        """Mostra o próximo comércio da lista e pergunta. Com o "sim", envia e já pergunta o seguinte."""
        import whatsapp
        pendentes = [c for c in whatsapp.contatos(pasta) if c.get("whatsapp") and not c.get("enviado")]
        with self._trava:
            if not pendentes:
                self._falar("Pronto, senhor: não sobrou nenhum comércio com celular para mandar nesta lista.")
                self._estado_parado()
                return
            if whatsapp.enviados_hoje() >= whatsapp.LIMITE_POR_DIA:
                self._falar(f"Já foram {whatsapp.LIMITE_POR_DIA} mensagens hoje, senhor. Paro aqui para o WhatsApp não "
                            "bloquear o seu número; amanhã diga: manda a mensagem pro próximo.")
                self._estado_parado()
                return
            contato = pendentes[0]

            def enviar():
                def trabalho():
                    self._ui("tarefa", "WhatsApp", contato["nome"])
                    try:
                        whatsapp.enviar(contato, contato["mensagem"])
                        whatsapp.marcar_enviado(pasta, contato, None)
                        fala = f"Enviada para {contato['nome']}, senhor."
                    except Exception as erro:
                        log.exception("WhatsApp: falha ao enviar para %s", contato["nome"])
                        fala = f"Não consegui mandar para {contato['nome']}, senhor: {str(erro)[:150]}"
                    self._ui("tarefa", None, None)
                    with self._trava:
                        self._falar(fala)
                    self._oferecer_proximo(pasta)  # já pergunta o seguinte
                threading.Thread(target=trabalho, daemon=True).start()
                return "Mandando, senhor. Acompanhe na tela do mini notebook."

            self._pendente = enviar
            self._ui("nota", f"✆ {contato['nome']} · {contato['telefone']}\n{contato['mensagem']}")
            restantes = len(pendentes) - 1
            self._falar(f"Mando para {contato['nome']}, {contato['telefone']}, a mensagem perguntando se quer ver a "
                        f"prévia do site?{f' Depois dele faltam {restantes}.' if restantes else ''} Confirma?")
            self._estado_parado()

    def _venda_700(self, nicho):
        """Código /700: comércios de Cacoal sem site -> site, zip e vídeo de cada um, com o preço de R$ 100 na
        mensagem -> login do GitHub na mini tela -> publicar (com o "sim") -> WhatsApp pronto. As mensagens vão
        uma por vez, quando o senhor pede; quando um cliente responde, o Braga avisa para o senhor assumir."""
        nicho = nicho.strip(" .")
        if not nicho:
            return "Qual ramo, senhor? Por exemplo: barra 700 pet shop."
        busca = nicho if " em " in f" {nicho.lower()} " else f"{nicho} em Cacoal"  # a cidade padrão é Cacoal
        return self._fabrica_sites(busca, 3, preco=100, completo=True)

    def _etapa_github(self, pasta):
        """/700, depois dos sites: entra no GitHub pela mini tela se precisar, pergunta se publica e segue."""
        import subprocess
        import github_pages
        import navegador

        def falar(texto):
            with self._trava:
                self._falar(texto)
                self._estado_parado()

        pronto, motivo = github_pages.situacao()
        if not pronto:
            try:
                processo, codigo = github_pages.login_pelo_navegador()
                navegador.abrir("https://github.com/login/device")
            except Exception as erro:
                log.exception("/700: login do GitHub não começou")
                falar(f"Não consegui começar o login do GitHub, senhor. {motivo} {str(erro)[:100]}")
                return
            self._aba_ativa = "navegador"
            self._ui("abrirNavegador")
            self._ui("nota", f"Código do GitHub: {codigo}  (já está copiado: é só colar com Ctrl+V)")
            falar("Agora o GitHub, senhor. Abri a página de login na mini tela. Entre na sua conta, cole o código, "
                  f"que já copiei, {' '.join(codigo)}, clique em Continue e depois em Authorize. Eu espero.")
            try:
                processo.wait(timeout=900)
            except subprocess.TimeoutExpired:
                processo.kill()
                falar("O GitHub não foi autorizado em 15 minutos, senhor. Quando quiser, diga: publica os sites no "
                      "GitHub.")
                return
            if not github_pages.situacao()[0]:
                falar("O login do GitHub não terminou, senhor. Quando quiser, diga: publica os sites no GitHub.")
                return

        def publicar_e_seguir():
            def trabalho():
                import fabrica_sites
                self._ui("tarefa", "Publicando no GitHub Pages", os.path.basename(pasta))
                try:
                    n, execucao = fabrica_sites.publicar(pasta, lambda t: self._ui("atividade", t))
                    self._entregar_pasta(execucao["pasta_envio"])  # contatos refeitos, agora com o link do site
                    fala = f"Publiquei {n} sites no GitHub Pages, senhor. O GitHub leva uns minutos para deixar no ar."
                except Exception as erro:
                    log.exception("/700: falha ao publicar")
                    execucao, fala = None, f"Não consegui publicar, senhor. {str(erro)[:150]}"
                self._ui("tarefa", None, None)
                falar(fala)
                if execucao:
                    self._etapa_whatsapp(execucao["pasta_envio"])
            threading.Thread(target=trabalho, daemon=True).start()
            return "Publicando, senhor. Depois abro o WhatsApp."

        with self._trava:
            self._pendente = publicar_e_seguir
            self._falar("O GitHub está pronto, senhor. Publico os sites agora? Eles ficam públicos na internet. "
                        "Confirma?")
            self._estado_parado()

    def _etapa_whatsapp(self, pasta_envio):
        """/700, último passo: WhatsApp Web na mini tela e as mensagens prontas. Enviar é um por vez, com o "sim"."""
        import whatsapp
        try:
            com_celular = sum(1 for c in whatsapp.contatos(pasta_envio) if c.get("whatsapp"))
            self._aba_ativa = "navegador"
            self._ui("abrirNavegador")
            estado = whatsapp.situacao()
            self.abrir_pip()
        except Exception as erro:
            log.exception("/700: WhatsApp não abriu")
            estado, com_celular = f"erro: {str(erro)[:100]}", 0
        inicio = {"logado": "O WhatsApp está conectado. ",
                  "qr": "Leia o QR Code da mini tela com o celular: WhatsApp, Aparelhos conectados, Conectar um "
                        "aparelho. "}.get(estado, "O WhatsApp Web ainda está abrindo na mini tela. ")
        with self._trava:
            self._falar(f"{inicio}Tenho {com_celular} cliente{'s' if com_celular != 1 else ''} com celular, senhor, "
                        "com a mensagem e o preço de 100 "
                        "reais prontos. Para mandar, diga: manda a mensagem pro próximo. Eu mostro quem é e envio "
                        "depois do seu sim. Quando algum cliente responder, eu aviso para o senhor assumir a conversa.")
            self._estado_parado()

    def _vigiar_respostas(self, intervalo=45):
        """Com o WhatsApp Web aberto na mini tela, avisa quando um cliente que recebeu a mensagem responde.
        Só lê a lista de conversas: quem responde é o senhor."""
        import whatsapp
        avisados = set()
        while True:
            time.sleep(intervalo)
            if self._falando.is_set():
                continue
            try:
                novos = [c for c in whatsapp.quem_respondeu(whatsapp.nao_lidas())
                         if c.get("whatsapp") not in avisados]
            except Exception:
                log.debug("Vigia de respostas: falhou ao olhar o WhatsApp", exc_info=True)
                continue
            if not novos:
                continue
            avisados.update(c.get("whatsapp") for c in novos)
            nomes = ", ".join(c["nome"] for c in novos[:3])
            self._ui("nota", "✆ Respondeu no WhatsApp: " + nomes)
            with self._trava:
                self._falar(f"Senhor, {nomes} respondeu no WhatsApp. Assuma a conversa na mini tela.")
                self._estado_parado()

    def _vigiar_github(self, intervalo=120):
        """De tempos em tempos confere se o GitHub ficou pronto (o senhor fez o `gh auth login`). Quando fica e há
        sites da fábrica esperando, pergunta uma vez se pode publicar. Publicar só acontece com o "sim"."""
        import fabrica_sites
        import github_pages
        while True:
            time.sleep(intervalo)
            if getattr(self, "_github_oferecido", False) or self._pendente or self._falando.is_set():
                continue
            try:
                pendentes = fabrica_sites.pendentes_de_publicar()
                if not pendentes or not github_pages.situacao()[0]:
                    continue
            except Exception:
                log.debug("Vigia do GitHub: falhou ao conferir", exc_info=True)
                continue
            self._github_oferecido = True  # pergunta uma vez por vez que o Braga abre
            total = sum(n for _, n in pendentes)

            def publicar_todos():
                def trabalho():
                    self._ui("tarefa", "Publicando no GitHub Pages", f"{total} sites")
                    feitos, mais_nova = 0, None
                    for pasta, _ in pendentes:
                        try:
                            n, execucao = fabrica_sites.publicar(pasta, lambda t: self._ui("atividade", t))
                            feitos += n
                            mais_nova = mais_nova or execucao
                        except Exception:
                            log.exception("Falha ao publicar %s", pasta)
                    self._ui("tarefa", None, None)
                    if mais_nova and mais_nova.get("pasta_envio"):
                        self._entregar_pasta(mais_nova["pasta_envio"])  # contatos refeitos, agora com os links
                    with self._trava:
                        self._falar(f"Publiquei {feitos} sites no GitHub Pages, senhor. Os links já estão nos "
                                    "contatos de cada pasta de envios.")
                        self._estado_parado()
                threading.Thread(target=trabalho, daemon=True).start()
                return "Publicando, senhor. Aviso quando terminar."

            with self._trava:
                self._pendente = publicar_todos
                self._falar(f"Senhor, o GitHub ficou pronto, e tenho {total} sites da fábrica esperando para "
                            "publicar. Eles ficam públicos na internet. Publico agora?")
                self._estado_parado()

    def _preparar_publicacao(self, pasta):
        """Publicar deixa os sites públicos na internet: só com confirmação. Sem GitHub pronto, explica o que falta."""
        import github_pages
        pronto, motivo = github_pages.situacao()
        if not pronto:
            return f"Para publicar no GitHub: {motivo}"

        def publicar():
            def trabalho():
                import fabrica_sites
                self._ui("tarefa", "Publicando no GitHub Pages", os.path.basename(pasta))
                try:
                    n, execucao = fabrica_sites.publicar(pasta, lambda t: self._ui("atividade", t))
                    fala = (f"Publiquei {n} sites no GitHub Pages, senhor. Os links já estão nas mensagens; o GitHub "
                            "leva uns minutos para deixar no ar.")
                    self._entregar_pasta(execucao["pasta_envio"])  # contatos refeitos, agora com o link do site
                except Exception as erro:
                    log.exception("Falha ao publicar no GitHub")
                    fala = f"Não consegui publicar, senhor. {str(erro)[:150]}"
                self._ui("tarefa", None, None)
                with self._trava:
                    self._falar(fala)
                    self._estado_parado()
            threading.Thread(target=trabalho, daemon=True).start()
            return "Publicando, senhor. Aviso quando estiver no ar."

        self._pendente = publicar
        return "Quer que eu publique os sites no GitHub Pages? Eles ficam públicos na internet. Confirma?"

    def _modo_navegador(self, tarefa):
        """O Jarvis age sozinho dentro da mini tela (clica, digita, rola), mostrando tudo ao vivo."""
        if claude_code.ocupado():
            return "Ainda estou com outra tarefa, senhor. Aguarde eu terminar."
        if not tarefa.strip():
            return "O que o senhor quer que eu faça na mini tela?"
        import navegador

        def trabalho():
            import agente_tela
            self._ui("tarefa", "Agindo na mini tela", tarefa)
            try:
                navegador.preparar()
                self._ui("abrirNavegador")
                deu_certo, resumo = agente_tela.executar_tarefa(
                    tarefa, lambda fala: self._ui("atividade", fala), alvo=navegador)
            except Exception:
                log.exception("Falha no modo mini tela")
                resumo = "Não consegui agir na mini tela, senhor."
            self._ui("tarefa", None, None)
            with self._trava:
                self._falar(resumo)
                self._estado_parado()

        threading.Thread(target=trabalho, daemon=True).start()
        return "Entendido, senhor. Vou fazer isso na mini tela; o senhor pode acompanhar ao vivo."

    def youtube_painel(self, alvo, quantidade, audio, modo):
        """Painel do YouTube: link de playlist ou vídeo, ou um texto para buscar.
        modo: "baixar", "resumir" (ideias para o Jarvis) ou "relatorio" (PDF no Google Drive)."""
        alvo = (alvo or "").strip()
        if not alvo:
            return
        import youtube

        def rodar():
            with self._trava:
                verbo = {"resumir": "Resumir", "relatorio": "Relatório em PDF"}.get(modo, "Baixar")
                self._ui("voceDisse", f"{verbo} do YouTube: {alvo}")
                self._mudar_estado("pensando")
                try:
                    if modo == "relatorio":
                        fala = self._relatorio_youtube(alvo, quantidade or None)
                    elif modo == "resumir":
                        import autoestudo
                        fala = self._resumir_videos(alvo, min(quantidade or 5, autoestudo.MAX_VIDEOS))
                    elif youtube.eh_link(alvo) and not youtube.eh_playlist(alvo):
                        fala = self._baixar_youtube(alvo, bool(audio))
                    else:
                        padrao = youtube.MAX_PLAYLIST if youtube.eh_playlist(alvo) else youtube.MAX_VIDEOS
                        fala = self._baixar_varios(alvo, quantidade or padrao, bool(audio))
                except Exception:
                    log.exception("Falha no painel do YouTube: %s", alvo)
                    fala = "Não consegui começar esse download, senhor. Veja o registro."
                self._falar(fala)
                self._estado_parado()

        threading.Thread(target=rodar, daemon=True).start()

    def gerar_pdf(self):
        """Botão PDF: escolher até 100 arquivos e juntar tudo em um PDF."""
        self._ui("nota", self._escolher_para_pdf())

    def _escolher_para_pdf(self):
        import conversor_pdf  # só aqui: carregar o PDF no início deixava o Jarvis 2 s mais lento para abrir
        tipo = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        escolhidos = list(self._janela.create_file_dialog(tipo, allow_multiple=True) or [])
        if not escolhidos:
            return "Nenhum arquivo escolhido para o PDF."
        aviso = ""
        if len(escolhidos) > conversor_pdf.LIMITE_ARQUIVOS:
            aviso = f" Peguei só os primeiros {conversor_pdf.LIMITE_ARQUIVOS} de {len(escolhidos)}."
        self._pdf_fundo(escolhidos, "Arquivos")
        return f"Vou juntar {min(len(escolhidos), conversor_pdf.LIMITE_ARQUIVOS)} arquivos em um PDF.{aviso}"

    def _pdf_fundo(self, caminhos, titulo, base=None):
        """Gera o PDF em segundo plano, mostra o caminho no registro e abre a pasta com ele selecionado."""
        def tarefa():
            import conversor_pdf
            self._ui("tarefa", "Gerando PDF", titulo)
            try:
                resultado = conversor_pdf.juntar(
                    caminhos, titulo, base,
                    ao_progresso=lambda n, total, nome: self._ui("atividade", f"{n}/{total} · {nome}"))
            except Exception as erro:
                log.exception("Falha ao gerar o PDF")
                resultado, fala = None, f"Não consegui gerar o PDF, senhor. {erro}"
            self._ui("tarefa", None, None)
            if resultado:
                self._ui("nota", resultado["arquivo"])
                for nome, motivo in resultado["pulados"][:10]:
                    self._ui("nota", f"Fora do PDF: {nome} ({motivo})")
                if len(resultado["pulados"]) > 10:
                    self._ui("nota", f"E mais {len(resultado['pulados']) - 10} fora do PDF (lista completa no sumário).")
                _mostrar_arquivo(resultado["arquivo"])
                fala = (f"Pronto, senhor. Juntei {len(resultado['convertidos'])} arquivos em um PDF de "
                        f"{resultado['paginas']} páginas. Está na pasta pdfs.")
                if resultado["pulados"]:
                    fala += f" {len(resultado['pulados'])} ficaram de fora, o motivo está no registro."
            with self._trava:
                self._falar(fala)
                self._estado_parado()
        threading.Thread(target=tarefa, daemon=True).start()

    def lista_biblioteca(self):
        return biblioteca.listar()[:40]

    def abrir_meus_dados(self):
        _editar(biblioteca.MEUS_DADOS)

    # ---------- modo isolado: o que abriria no PC abre no notebook virtual ----------
    def _abrir_no_virtual(self, endereco):
        """Mostra um site, arquivo ou pasta (file:///) no navegador do Braga, na tela do notebook 3D."""
        def trabalho():
            import navegador
            try:
                navegador.abrir(endereco)
            except Exception:
                log.warning("Notebook virtual: não abri %s", endereco, exc_info=True)
            self._ui("abrirNotebook", "navegador")
        threading.Thread(target=trabalho, daemon=True).start()

    def isolamento_estado(self):
        import isolamento
        return isolamento.ligado()

    def _instalar_programa(self, nome):
        """"instala o VLC": procura no winget, diz qual achou e só instala com o "sim" do senhor."""
        import isolamento
        nome = (nome or "").strip(" .")
        if not nome:
            return "Qual programa, senhor? Por exemplo: instala o VLC."
        if isolamento.ligado():
            return isolamento.bloqueado("instalador de programas", "rodo o")

        def trabalho():
            import programas
            self._ui("tarefa", "Procurando o programa", nome)
            try:
                achados = programas.buscar(nome)
                escolhido = programas.melhor(achados, nome)
            except Exception as erro:
                log.warning("winget: busca de %s falhou", nome, exc_info=True)
                achados, escolhido, motivo = [], None, str(erro)[:120]
            else:
                motivo = "o winget não achou nada com esse nome"
            self._ui("tarefa", None, None)
            with self._trava:
                if not escolhido:
                    self._falar(f"Não achei o programa {nome}, senhor: {motivo}.")
                    self._estado_parado()
                    return

                def instalar():
                    def rodar():
                        self._ui("tarefa", "Instalando pelo winget", f"{escolhido['nome']} {escolhido['versao']}")
                        isolamento.antes_de_abrir_no_pc()  # se o instalador abrir janela, ela fica no mini notebook
                        try:
                            deu_certo, resumo = programas.instalar(escolhido["id"], lambda t: self._ui("atividade", t))
                        except Exception as erro:
                            log.exception("winget: falha ao instalar %s", escolhido["id"])
                            deu_certo, resumo = False, str(erro)[:150]
                        self._ui("tarefa", None, None)
                        with self._trava:
                            self._falar(f"Pronto, senhor: {escolhido['nome']} instalado." if deu_certo
                                        else f"Não consegui instalar {escolhido['nome']}, senhor. {resumo}")
                            self._estado_parado()
                    threading.Thread(target=rodar, daemon=True).start()
                    return f"Instalando {escolhido['nome']}, senhor. Acompanhe no mini notebook."

                self._pendente = instalar
                outros = ", ".join(a["nome"] for a in achados if a is not escolhido)[:150]
                self._ui("nota", f"winget: {escolhido['nome']} ({escolhido['id']}) {escolhido['versao']}"
                                 + (f"\nOutros: {outros}" if outros else ""))
                self._falar(f"Achei o {escolhido['nome']}, versão {escolhido['versao']}, no winget. Vou instalar e "
                            "aceitar os termos de uso dele. Confirma?")
                self._estado_parado()

        threading.Thread(target=trabalho, daemon=True).start()
        return f"Procurando {nome} no winget, senhor."

    def _preparar_pc(self):
        """Antes de abrir algo no PC de verdade: o Braga vem para a frente, mostra o mini notebook e fica por cima
        de tudo. A janela nova nasce atrás dele e o senhor a vê (e mexe nela) pelo mini notebook."""
        import notebook
        self.mostrar_principal()
        self._ui("abrirNotebook", "pc")
        notebook.captura.quadro()  # liga a captura, que mantém o Braga por cima enquanto o notebook está aberto
        notebook.primeira_pessoa(True)
        time.sleep(0.4)

    def _modo_isolado(self, ligar):
        import isolamento
        if ligar:
            isolamento.ligar(True)
            self._ui("isolado", True)
            return ("Modo isolado ligado, senhor. Tudo abre só dentro do Braga, no notebook virtual; o seu PC fica "
                    "sem janelas e abas novas.")

        def desligar():
            isolamento.ligar(False)
            self._ui("isolado", False)
            return "Modo isolado desligado, senhor. Agora posso abrir programas e janelas no seu PC de novo."

        self._pendente = desligar
        return ("Desligando o modo isolado, eu volto a abrir sites, pastas e programas no seu PC e posso usar o mouse "
                "e o teclado de verdade. Confirma?")

    def _guardar(self, adicionar, nome):
        try:
            adicionar()
            self._ui("nota", f"Guardado na biblioteca: {nome}. Analisando…")
        except Exception as erro:
            log.exception("Falha ao guardar %s", nome)
            self._ui("nota", f"Não consegui guardar {nome}: {erro}")
        self._ui("biblioteca", biblioteca.listar()[:40])

    def _biblioteca_pronta(self, item):
        self._ui("biblioteca", biblioteca.listar()[:40])
        if item["status"] == "pronto":
            primeira_linha = item["resumo"].split("\n")[0][:160]
            self._ui("nota", f"Analisei {item['nome']}: {primeira_linha}")

    def erro_js(self, mensagem):
        log.warning("Erro na interface: %s", mensagem)

    def desempenho_js(self, texto):
        log.info("Quarto 3D: %s", texto)  # quadros por segundo e resolução, medidos no próprio PC

    # Fotos do quarto 3D para conferir as animações: só quando existe %TEMP%\ryker_fotos\PEDIR (a janela do Braga
    # fica fora das capturas de tela, então é o próprio quarto que se fotografa)
    def fotos_pedidas(self):
        pedido = os.path.join(os.environ.get("TEMP", PASTA), "ryker_fotos", "PEDIR")
        if not os.path.exists(pedido):
            return False
        os.remove(pedido)
        return True

    def foto_js(self, nome, dados_url):
        pasta = os.path.join(os.environ.get("TEMP", PASTA), "ryker_fotos")
        nome = re.sub(r"[^\w-]", "", str(nome))[:40] or "foto"
        with open(os.path.join(pasta, nome + ".jpg"), "wb") as arquivo:
            arquivo.write(base64.b64decode(str(dados_url).split(",", 1)[-1]))

    def tela_cheia(self):
        self._janela.toggle_fullscreen()

    def status(self):
        bateria = psutil.sensors_battery()
        memoria_ram = psutil.virtual_memory()
        disco = psutil.disk_usage(DISCO)
        freq = psutil.cpu_freq()
        # velocidade da rede desde a última consulta (a interface pergunta a cada 2 s)
        rede, agora = psutil.net_io_counters(), time.time()
        bytes_rede = rede.bytes_sent + rede.bytes_recv
        antes = getattr(self, "_rede_antes", None)
        mbps = (bytes_rede - antes[1]) * 8 / 1e6 / max(0.1, agora - antes[0]) if antes else 0.0
        self._rede_antes = (agora, bytes_rede)
        return {
            "cpu": round(psutil.cpu_percent()),
            "ram": round(memoria_ram.percent),
            "disco": round(disco.percent),
            "gpu": None,  # o Windows não informa o uso do vídeo Intel de um jeito leve
            "rede_mbps": round(mbps, 2),
            "os": f"{platform.system()} {platform.release()}",
            "maquina": platform.node(),
            "bateria": round(bateria.percent) if bateria else None,
            "carregando": bool(bateria and bateria.power_plugged),
            "email": enviar_email.configurado(),
            "claude": claude_code.disponivel(),
            # dados completos do notebook: o Jarvis roda nele, então o desempenho é o dele
            "detalhes": {
                "cpu": platform.processor() or "Processador",
                "nucleos": psutil.cpu_count(logical=True),
                "freq_ghz": round(freq.current / 1000, 2) if freq else None,
                "ram_total": round(memoria_ram.total / 1024**3, 1),
                "ram_usada": round(memoria_ram.used / 1024**3, 1),
                "disco_livre": round(disco.free / 1024**3),
                "disco_total": round(disco.total / 1024**3),
                "processos": len(psutil.pids()),
                "uptime_h": round((time.time() - psutil.boot_time()) / 3600, 1),
            },
        }

    # ---------- interface ----------
    def _ui(self, funcao, *args):
        if not self._janela:
            return
        argumentos = ", ".join(json.dumps(a) for a in args)
        try:
            self._janela.evaluate_js(f"window.jarvis && jarvis.{funcao}({argumentos})")
        except Exception:
            log.debug("Falha ao atualizar a interface", exc_info=True)

    def _mudar_estado(self, estado):
        if estado != self._estado:
            self._estado = estado
            self._ui("estado", estado)

    def _estado_parado(self):
        if self._mic_ligado and self._ouvir_agora.is_set():
            self._mudar_estado("escutando")  # esperando a resposta de uma pergunta
        else:
            self._mudar_estado("ouvindo" if self._mic_ligado else "pausado")

    # ---------- fala ----------
    async def _sintetizar(self, texto):
        comunicador = edge_tts.Communicate(texto, VOZ, rate="+5%", pitch="-4Hz")
        audio = b""
        async for parte in comunicador.stream():
            if parte["type"] == "audio":
                audio += parte["data"]
        return audio

    def _falar(self, texto, lembrar=True):
        log.info("Jarvis: %s", texto)
        if lembrar:
            memoria.registrar_fala(identidade.NOME, texto)
        self._mudar_estado("falando")
        self._ui("falaTexto", texto)
        try:
            audio = asyncio.run(self._sintetizar(texto))
        except Exception:
            log.warning("Voz online indisponível, usando a voz do Windows", exc_info=True)
            audio = None

        self._falando.set()
        if audio:
            self._ui("tocarAudio", base64.b64encode(audio).decode("ascii"))
            limite = time.time() + 90
            while self._falando.is_set() and time.time() < limite:
                time.sleep(0.05)
        else:
            _voz_windows(texto)
        self._falando.clear()
        # Fez uma pergunta ("Confirma?"): a resposta vem sem precisar dizer "Jarvis"
        if texto.rstrip().endswith("?") and self._mic_ligado:
            self._ouvir_agora.set()

    # ---------- comandos ----------
    def _processar(self, texto):
        texto = (texto or "").strip()
        if not texto:
            return
        with self._trava:
            log.info("Você: %s", texto)
            memoria.registrar_fala("Usuário", texto)
            self._ui("voceDisse", texto)
            # Tira o "Jarvis" da frase, mantendo os acentos do resto
            comando = separar_chamado(texto)
            if comando is None:
                comando = texto.strip(" ,.!?")

            if SAIR.match(normalizar(comando)):
                self._falar("Encerrando os sistemas. Até logo, senhor.")
                self._janela.destroy()
                return

            # Resposta a uma pergunta de sim/não (ex.: confirmar envio de e-mail)
            if self._pendente:
                n = normalizar(comando)
                if re.search(r"\b(sim|confirm\w*|pode|manda|envia|isso|positivo|ok|claro)\b", n):
                    acao, self._pendente = self._pendente, None
                    self._resposta_pendente = comando  # o "sim" pode vir com detalhes ("sim, manda bom dia")
                    self._mudar_estado("pensando")
                    self._falar(acao())
                    self._estado_parado()
                    return
                if re.search(r"\b(nao|cancel\w*|deixa|para|negativo|esquece)\b", n):
                    self._pendente = None
                    self._falar("Cancelado, senhor.")
                    self._estado_parado()
                    return
                self._pendente = None  # falou outra coisa: segue o fluxo normal

            self._mudar_estado("pensando")
            try:
                # com a mini tela na frente, "pesquisa X", "volta", "clica em..." valem para ela
                resposta = executar(comando, mini_tela=self._aba_ativa == "navegador", url_mini=self._url_mini)
                if isinstance(resposta, dict):
                    resposta = self._acao(resposta)
            except Exception:
                log.exception("Erro ao executar %r", comando)
                resposta = "Desculpe, senhor. Algo deu errado ao executar esse comando."
            self._falar(resposta)
            self._estado_parado()

    def responder(self, texto):
        """Processa um comando vindo do Telegram e devolve a resposta em texto (sem falar)."""
        texto = (texto or "").strip()
        if not texto:
            return "Pois não, senhor?"
        comando = separar_chamado(texto)
        if comando is None:
            comando = texto.strip(" ,.!?")

        # Confirmação de sim/não pendente deste canal
        if self._pendente_tg:
            n = normalizar(comando)
            if re.search(r"\b(sim|confirm\w*|pode|manda|envia|isso|positivo|ok|claro)\b", n):
                acao, self._pendente_tg = self._pendente_tg, None
                return acao()
            if re.search(r"\b(nao|cancel\w*|deixa|para|negativo|esquece)\b", n):
                self._pendente_tg = None
                return "Cancelado, senhor."
            self._pendente_tg = None

        with self._trava:
            log.info("Telegram -> Jarvis: %s", comando)
            memoria.registrar_fala("Usuário (Telegram)", comando)
            try:
                resposta = executar(comando)
                if isinstance(resposta, dict):
                    # isola a confirmação: se _acao pedir "confirma?", ela fica no canal do Telegram
                    antes, self._pendente = self._pendente, None
                    resposta = self._acao(resposta)
                    if self._pendente:
                        self._pendente_tg = self._pendente
                    self._pendente = antes
            except Exception:
                log.exception("Erro no comando do Telegram %r", comando)
                resposta = "Desculpe, senhor. Algo deu errado."
        return resposta

    def _acao(self, pedido):
        """Comandos que usam o Claude Code."""
        acao = pedido["acao"]
        if acao == "biblioteca_link":
            biblioteca.adicionar_link(pedido["url"])
            self._ui("biblioteca", biblioteca.listar()[:40])
            return "Guardei o link na biblioteca, senhor. Vou analisar e aviso no registro."
        if acao == "biblioteca_resumo":
            itens = biblioteca.listar()
            if not itens:
                return "A biblioteca ainda está vazia, senhor. Arraste arquivos e fotos para a minha janela, ou cole um link."
            nomes = ", ".join(i["nome"] if i["tipo"] != "link" else "um link" for i in itens[:3])
            return f"Tenho {len(itens)} itens na biblioteca. Os mais recentes são: {nomes}."
        if acao == "abrir_meus_dados":
            self.abrir_meus_dados()
            return "Abrindo seus dados, senhor. Preencha do seu jeito e salve."
        if acao == "modo_fundo":
            return self._modo_fundo(pedido["ligar"])
        if acao == "instalar_programa":
            return self._instalar_programa(pedido["nome"])
        if acao == "modo_isolado":
            return self._modo_isolado(pedido["ligar"])
        if acao == "modo_tela":
            return self._modo_tela(pedido["tarefa"], pedido.get("virtual", False))
        if acao == "notebook_abrir":
            if pedido.get("flutuante"):
                return self.abrir_notebook_flutuante()
            self._ui("abrirNotebook")
            return "Abri o mini notebook, senhor. O que o senhor fizer nele acontece de verdade no notebook."
        if acao == "notebook_controle":
            return self._notebook_controle(pedido["tipo"], pedido.get("texto", ""))
        if acao == "biblioteca_apagar":
            return self._preparar_apagar(pedido["texto"])
        if acao == "abrir_biblioteca":
            _mostrar_arquivo(biblioteca.ARQUIVOS)
            return "Abrindo a pasta da biblioteca."

        if acao in ("pdf_jarvis", "pdf_biblioteca"):
            import conversor_pdf
        if acao == "pdf_jarvis":
            self._pdf_fundo(conversor_pdf.arquivos_do_jarvis(), "Projeto Jarvis", conversor_pdf.PASTA)
            return ("Vou juntar todo o meu código em um PDF, senhor. A senha do e-mail e as conversas ficam de fora. "
                    "É só mandar esse PDF para o Claude.")
        if acao == "pdf_biblioteca":
            arquivos = [i["arquivo"] for i in biblioteca.listar() if i.get("arquivo")]
            if not arquivos:
                return "A biblioteca não tem arquivos para virar PDF, senhor."
            self._pdf_fundo(arquivos[:conversor_pdf.LIMITE_ARQUIVOS], "Biblioteca")
            return f"Vou juntar {min(len(arquivos), conversor_pdf.LIMITE_ARQUIVOS)} arquivos da biblioteca em um PDF, senhor."
        if acao == "pdf_escolher":
            return self._escolher_para_pdf()
        if acao == "youtube_tocar":
            return self._tocar_youtube(pedido["busca"])
        if acao == "fechar_aba":
            self._ui("fecharAba", pedido.get("todas", False))
            return "Fechei, senhor." if not pedido.get("todas") else "Fechei todas as abas, senhor."
        if acao == "youtube_baixar":
            return self._baixar_youtube(pedido["alvo"], pedido["audio"])
        if acao == "youtube_baixar_varios":
            return self._baixar_varios(pedido["alvo"], pedido["quantidade"], pedido["audio"])
        if acao == "sequencia":
            return self._sequencia(pedido)
        if acao == "comando_criar":
            return self._criar_comando(pedido["prompt"])
        if acao == "comando_apagar":
            return self._apagar_comando(pedido["nome"])
        if acao == "skill_instalar":
            return self._skill_instalar(pedido["link"])
        if acao == "skill_apagar":
            return self._skill_apagar(pedido["nome"])
        if acao == "skill_listar":
            minhas = self.skills_listar()
            self._ui("skills", minhas)
            if not minhas:
                return ("O senhor ainda não tem skills. Cole o link de um repositório do GitHub no painel Skills, ou "
                        "diga: instala a skill, e o link.")
            return f"O senhor tem {len(minhas)} skills: {', '.join(s['nome'] for s in minhas[:8])}."
        if acao == "comando_listar":
            import comandos_usuario
            meus = comandos_usuario.listar()
            self._ui("comandos", meus)
            if not meus:
                return "O senhor ainda não tem comandos. Diga, por exemplo: cria um comando, quando eu disser modo trabalho, abre o gmail na mini tela e liga o modo foco."
            nomes = ", ".join(c["frases"][0] for c in meus[:8])
            return f"O senhor tem {len(meus)} comando{'s' if len(meus) > 1 else ''}: {nomes}."
        if acao == "navegador_abrir":
            return self._abrir_mini_tela(pedido["alvo"], pedido.get("buscador", "bing"))
        if acao == "whatsapp_conectar":
            return self._whatsapp_conectar()
        if acao == "whatsapp_enviar":
            return self._whatsapp_preparar(pedido["alvo"], pedido.get("com_video", False))
        if acao == "pip_abrir":
            return self.abrir_pip()
        if acao == "pip_fechar":
            return self.fechar_pip()
        if acao == "abrir_videos":
            import prospeccao
            pasta = os.path.join(prospeccao.pasta_videos(), "Jarvis")
            os.makedirs(pasta, exist_ok=True)
            self._ui("nota", pasta)
            _mostrar_arquivo(pasta)
            return ("Abri a pasta dos vídeos, senhor. Todos ficam em MP4 no notebook, na pasta Vídeos, Jarvis: "
                    "Prospecção, Sites e os baixados do YouTube.")
        if acao == "prospeccao":
            return self._prospeccao(pedido["busca"], pedido.get("quantidade", 5))
        if acao == "fabrica_sites":
            return self._fabrica_sites(pedido["busca"], pedido.get("quantidade", 3))
        if acao == "venda_700":
            return self._venda_700(pedido["nicho"])
        if acao == "prospeccao_notebook":
            return self._prospeccao_notebook(pedido["busca"])
        if acao == "fabrica_publicar":
            import fabrica_sites
            pasta = fabrica_sites.ultima_execucao()
            if not pasta:
                return "Ainda não fiz nenhum site, senhor. Diga: fábrica de sites de barbearias em Cacoal."
            return self._preparar_publicacao(pasta)
        if acao == "navegador_controle":
            nomes = {"voltar": "Voltando.", "avancar": "Avançando.", "recarregar": "Recarregando a página.",
                     "rolar": "Descendo." if (pedido.get("valor") or 0) > 0 else "Subindo."}
            estado = self.navegador_acao(pedido["tipo"], pedido.get("valor"))
            if isinstance(estado, dict) and estado.get("url"):
                self._url_mini = estado["url"]
            return nomes.get(pedido["tipo"], "Feito.") if not (isinstance(estado, dict) and estado.get("erro")) \
                else "Não consegui fazer isso na mini tela, senhor."
        if acao == "navegador_agente":
            return self._modo_navegador(pedido["tarefa"])
        if acao == "navegador_fechar":
            import navegador
            self._ui("fecharNavegador")
            navegador.desligar()
            return "Fechei a mini tela, senhor."
        if acao == "youtube_relatorio":
            return self._relatorio_youtube(pedido["busca"], pedido.get("quantidade"))
        if acao == "youtube_resumir":
            return self._resumir_videos(pedido["busca"], pedido["quantidade"])
        if acao == "autoatualizar":
            return self._preparar_autoatualizacao(pedido["pedido"])
        if acao == "lembrete":
            return self._criar_lembrete(pedido)
        if acao == "lembretes_listar":
            return self._listar_lembretes()
        if acao == "lembretes_cancelar":
            n = self._cancelar_lembretes("lembrete")
            return f"Cancelei {n} lembrete{'s' if n > 1 else ''}, senhor." if n else "Não havia lembretes, senhor."
        if acao == "foco":
            return self._modo_foco(pedido["ligar"], pedido.get("intervalo", 1800), pedido.get("duracao", 0))
        if acao == "noticias":
            return self._noticias(pedido.get("assunto", ""))
        if acao == "briefing":
            return self._briefing()
        if acao == "erros":
            return self._mostrar_erros()

        if acao == "config_email":
            enviar_email.preparar()
            _editar(enviar_email.CONFIG)
            return ("Abri a configuração de e-mail, senhor. Coloque seu endereço e a senha de app, e salve. "
                    "Nunca me diga a senha em voz alta.")
        if acao == "email":
            return self._preparar_email(pedido["texto"])

        if not claude_code.disponivel():
            return "O Claude Code não está instalado neste notebook, senhor."

        if acao == "perguntar":
            self._ui("atividade", "Consultando o Claude")
            return claude_code.perguntar(pedido["texto"])

        if acao == "onde_ultimo":
            return self._onde_esta(pedido.get("android", False))

        if acao == "engenharia_site":
            self._analisar_fundo(lambda: engenharia.analisar_site(pedido["url"]),
                                 "Analisando o site", pedido["url"])
            return "Vou estudar como esse site foi feito, senhor. Aviso quando o relatório estiver pronto."
        if acao == "engenharia_apk":
            apk = self._achar_apk(pedido.get("alvo"))
            if not apk:
                return ("Não achei um APK para analisar, senhor. Arraste o arquivo APK para a minha janela "
                        "e depois diga: faz engenharia desse apk.")
            self._analisar_fundo(lambda: engenharia.analisar_apk(apk),
                                 "Analisando o APK", os.path.basename(apk))
            return "Vou estudar como esse APK foi construído, senhor. Aviso quando terminar."

        if acao == "abrir_ultimo":
            pasta = claude_code.ultimo_projeto()
            if not pasta:
                return "Ainda não criei nenhum app, senhor."
            index = os.path.join(pasta, "index.html")
            url = servidor.url_de(index) if os.path.exists(index) and not claude_code.eh_android(pasta) else None
            if url:
                self._ui("abrirAba", os.path.basename(pasta), url, "projeto")
                return "Abri o último app numa aba, senhor."
            _abrir_projeto(pasta)
            return "Abrindo o último app que eu criei."

        if claude_code.ocupado():
            return "Ainda estou trabalhando no app anterior, senhor. Aviso quando terminar."
        if acao == "criar_app" and pedido.get("tipo") == "android":
            funcao = lambda texto, ao_evento: claude_code.criar_app(texto, ao_evento, "android")
            titulo = "Construindo APK Android"
            fala = ("Entendido, senhor. Vou criar o app Android com o Claude e gerar o APK. "
                    "Isso pode levar alguns minutos, aviso quando terminar.")
        elif acao == "criar_app":
            funcao, titulo = claude_code.criar_app, "Construindo app"
            fala = "Entendido, senhor. Vou construir isso com o Claude e aviso quando terminar."
        else:
            funcao, titulo = claude_code.editar_ultimo, "Alterando o último app"
            fala = "Entendido, senhor. Vou fazer essa alteração e aviso quando terminar."
        threading.Thread(target=self._trabalhar, args=(funcao, pedido["pedido"], titulo), daemon=True).start()
        return fala

    def _narrar_passo(self, texto, narrado):
        """Enquanto o Claude trabalha, fala de vez em quando o que está fazendo, sem exagerar."""
        agora = time.time()
        if self._falando.is_set() or agora - narrado["quando"] < 22:
            return
        frase = None
        t = normalizar(texto)
        if "criando" in t:
            frase = "Estou criando os arquivos, senhor."
        elif "editando" in t:
            frase = "Estou ajustando o código."
        elif "executando" in t and ("gradlew" in t or "gradle" in t or "assemble" in t or "bundle" in t):
            frase = "Agora estou compilando. Essa parte é a mais demorada."
        elif "executando" in t and ("npm" in t or "npx" in t):
            frase = "Instalando o que o projeto precisa."
        elif "pesquisando" in t:
            frase = "Estou pesquisando uma referência."
        if not frase or frase == narrado["ultimo"]:
            return
        narrado["quando"], narrado["ultimo"] = agora, frase
        self._falar(frase, lembrar=False)

    def _tocar_youtube(self, busca):
        """Toca o primeiro resultado do YouTube numa aba dentro do Jarvis (ou no navegador, se não der)."""
        import youtube
        try:
            if not servidor.url_de(os.path.join(servidor.PASTA, "interface", "v6", "index.html")):
                raise RuntimeError("interface aberta sem o servidor local")
            id_video, titulo = youtube.buscar(busca)
        except Exception:
            log.warning("Não deu para tocar %r dentro do Jarvis; abrindo no navegador", busca, exc_info=True)
            webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(busca))
            return f"Tocando {busca} no YouTube."
        self._ui("abrirAba", titulo, f"https://www.youtube.com/embed/{id_video}?autoplay=1&rel=0", "youtube",
                 f"https://www.youtube.com/watch?v={id_video}")
        return f"Tocando {titulo}."

    def abrir_no_navegador(self, url):
        """Botão ↗ da aba: abre o mesmo endereço no navegador."""
        if str(url).startswith(("http://", "https://")):
            webbrowser.open(url)

    def _baixar_youtube(self, alvo, audio):
        """Baixa do YouTube em segundo plano e mostra o arquivo selecionado na pasta quando terminar."""
        if not alvo:
            return "Qual vídeo, senhor? Diga o nome ou cole o link."
        tipo = "a música" if audio else "o vídeo"

        def tarefa():
            import youtube
            self._ui("tarefa", "Baixando do YouTube", alvo)
            ultimo = {"p": -10}

            def progresso(p):
                if p >= ultimo["p"] + 10:  # avisa de 10 em 10 por cento
                    ultimo["p"] = p
                    self._ui("atividade", f"Baixando… {p}%")

            try:
                arquivo, titulo = youtube.baixar(alvo, audio, progresso)
                self._ui("nota", arquivo)
                _mostrar_arquivo(arquivo)
                fala = f"Pronto, senhor. Baixei {tipo} {titulo}. Está na pasta Vídeos, Jarvis."
            except Exception as erro:
                log.exception("Falha ao baixar do YouTube: %s", alvo)
                fala = f"Não consegui baixar {tipo}, senhor. {str(erro).replace('ERROR: ', '')[:160]}"
            self._ui("tarefa", None, None)
            with self._trava:
                self._falar(fala)
                self._estado_parado()

        threading.Thread(target=tarefa, daemon=True).start()
        return f"Baixando {tipo} {alvo if not alvo.startswith('http') else 'do link'}, senhor. Aviso quando terminar."

    def _baixar_varios(self, alvo, quantidade, audio):
        """Playlist inteira ou vários vídeos de uma busca (só os que têm a busca no título)."""
        if not alvo:
            return "Quais vídeos, senhor? Diga o nome, o que deve ter no título ou cole o link da playlist."
        import youtube
        playlist = youtube.eh_playlist(alvo)
        tipo = "as músicas" if audio else "os vídeos"

        def tarefa():
            self._ui("tarefa", "Baixando vários do YouTube", alvo)
            ultimo = {"chave": None}

            def progresso(n, total, titulo, pct):
                chave = (n, pct // 25)  # avisa no começo de cada vídeo e de 25 em 25 por cento
                if chave != ultimo["chave"]:
                    ultimo["chave"] = chave
                    self._ui("atividade", f"{n}/{total} · {pct}% · {titulo[:60]}")

            try:
                pasta, arquivos, falhas = youtube.baixar_varios(
                    alvo, quantidade, audio, so_com_titulo=not playlist, ao_progresso=progresso)
                self._ui("nota", pasta)
                _mostrar_arquivo(pasta)
                fala = f"Pronto, senhor. Baixei {len(arquivos)} {'músicas' if audio else 'vídeos'} na pasta Vídeos, Jarvis."
                if falhas:
                    fala += f" {falhas} não deram para baixar."
            except Exception as erro:
                log.exception("Falha ao baixar vários do YouTube: %s", alvo)
                fala = f"Não consegui baixar {tipo}, senhor. {str(erro).replace('ERROR: ', '')[:160]}"
            self._ui("tarefa", None, None)
            with self._trava:
                self._falar(fala)
                self._estado_parado()

        threading.Thread(target=tarefa, daemon=True).start()
        if playlist:
            return f"Baixando {tipo} da playlist, senhor. Aviso quando terminar."
        return (f"Vou baixar até {quantidade} {'músicas' if audio else 'vídeos'} com {alvo} no título, senhor. "
                "Aviso quando terminar.")

    def _relatorio_youtube(self, busca, quantidade=None):
        """PDF com tudo da playlist (ou busca), resumido pelo Claude, salvo em pdfs/ e no Google Drive."""
        if not busca:
            return "De qual playlist, senhor? Cole o link no painel do YouTube ou diga o que buscar."

        def tarefa():
            import relatorio_youtube
            self._ui("tarefa", "Relatório do YouTube", busca)
            try:
                r = relatorio_youtube.gerar(busca, quantidade, lambda t: self._ui("atividade", t))
                self._ui("nota", r["drive"] or r["pdf"])
                _mostrar_arquivo(r["drive"] or r["pdf"])
                onde = ("Está no seu Google Drive, na pasta Jarvis." if r["drive"] else
                        "Está na pasta pdfs. Para ir ao Google Drive, abra o Google Drive no computador e entre na sua conta.")
                fala = f"Pronto, senhor. {r['falado']} {onde}"
            except Exception as erro:
                log.exception("Falha no relatório do YouTube: %s", busca)
                fala = f"Não consegui fazer o relatório, senhor. {str(erro).replace('ERROR: ', '')[:160]}"
            self._ui("tarefa", None, None)
            with self._trava:
                self._falar(fala)
                self._estado_parado()

        threading.Thread(target=tarefa, daemon=True).start()
        return ("Vou ler os vídeos e montar o relatório em PDF, senhor. Uma playlist grande leva alguns minutos; "
                "aviso quando terminar.")

    def _resumir_videos(self, busca, quantidade):
        """Lê as legendas dos vídeos, resume com o Claude e guarda as ideias para atualizar o Jarvis."""
        if not busca:
            return "Sobre o que são os vídeos, senhor?"
        if not claude_code.disponivel():
            return "O Claude Code não está instalado neste notebook, senhor."

        def tarefa():
            import autoestudo
            self._ui("tarefa", "Estudando vídeos do YouTube", busca)
            try:
                falado, caminho = autoestudo.resumir_videos(busca, quantidade, lambda t: self._ui("atividade", t))
                self._ui("nota", caminho)
                fala = (f"Pronto, senhor. {falado} Guardei o resumo e as ideias na pasta melhorias. "
                        f"Se quiser, diga: {identidade.NOME}, se atualiza com as ideias.")
            except Exception as erro:
                log.exception("Falha ao resumir os vídeos de %s", busca)
                fala = f"Não consegui resumir os vídeos, senhor. {erro}"
            self._ui("tarefa", None, None)
            with self._trava:
                self._falar(fala)
                self._estado_parado()

        threading.Thread(target=tarefa, daemon=True).start()
        return f"Vou assistir {quantidade} vídeos sobre {busca} e fazer um resumo, senhor. Isso leva alguns minutos."

    def _preparar_autoatualizacao(self, pedido):
        """O Jarvis pede ao Claude Code para mexer no próprio código. Só depois de o usuário confirmar."""
        if not claude_code.disponivel():
            return "O Claude Code não está instalado neste notebook, senhor."
        if claude_code.ocupado():
            return "Ainda estou com outra tarefa do Claude, senhor. Aguarde eu terminar."
        import autoestudo
        resumo = autoestudo.ultimo_resumo()
        # frase genérica ("se atualiza") usa as ideias; frase com pedido específico vai junto
        especifico = len(normalizar(pedido).split()) > 6
        if not resumo and not especifico:
            return ("Ainda não tenho ideias anotadas, senhor. Peça antes, por exemplo: "
                    "resume os vídeos sobre como fazer um Jarvis.")

        def atualizar():
            threading.Thread(target=self._autoatualizar, args=(pedido if especifico else "",), daemon=True).start()
            return "Começando. Fiz um backup antes e aviso quando terminar, senhor."

        self._pendente = atualizar
        origem = f"com as ideias de {os.path.basename(resumo)}" if resumo and not especifico else "com o seu pedido"
        return f"Vou pedir ao Claude para mudar o meu próprio código {origem}. Confirma?"

    def _autoatualizar(self, pedido):
        import autoestudo
        self._ui("tarefa", "Atualizando o Jarvis", pedido or "ideias dos vídeos")
        try:
            deu_certo, fala = autoestudo.atualizar_jarvis(pedido, lambda t: self._ui("atividade", t))
        except Exception:
            log.exception("Falha na autoatualização")
            deu_certo, fala = False, "Algo deu errado na atualização, senhor. Veja o registro."
        self._ui("tarefa", None, None)
        with self._trava:
            if deu_certo:
                self._pendente = self._reiniciar
                fala += " As mudanças valem quando eu reiniciar. Posso reiniciar agora?"
            self._falar(fala)
            self._estado_parado()

    def _reiniciar(self):
        """Abre um Jarvis novo (com o código atualizado) e fecha este."""
        subprocess.Popen([sys.executable, os.path.join(PASTA, "app.py")], cwd=PASTA)
        threading.Timer(2.5, self._janela.destroy).start()
        return "Reiniciando, senhor. Volto em alguns segundos."

    # ---------- lembretes, timer e modo foco ----------
    def _agendar(self, segundos, fala, tipo, descricao=""):
        item = {"quando": time.time() + segundos, "fala": fala, "tipo": tipo, "descricao": descricao}

        def disparar():
            self._lembretes = [i for i in self._lembretes if i is not item]
            self._avisar(fala)

        item["timer"] = threading.Timer(segundos, disparar)
        item["timer"].daemon = True
        item["timer"].start()
        self._lembretes.append(item)

    def _avisar(self, fala):
        """Fala o aviso na hora certa, esperando o Jarvis terminar o que estiver fazendo."""
        log.info("Aviso agendado: %s", fala)
        self._ui("nota", "⏰ " + fala)
        with self._trava:
            self._ui("bip")
            self._falar(fala, lembrar=False)
            self._estado_parado()

    def _cancelar_lembretes(self, tipo):
        cancelados = [i for i in self._lembretes if i["tipo"] == tipo]
        for item in cancelados:
            item["timer"].cancel()
        self._lembretes = [i for i in self._lembretes if i["tipo"] != tipo]
        return len(cancelados)

    def _criar_lembrete(self, pedido):
        segundos, texto, quando = pedido["segundos"], pedido["texto"], pedido["quando"]
        if segundos > 7 * 24 * 3600:
            return "Consigo lembrar só até uma semana adiante, senhor."
        if pedido["timer"]:
            fala, descricao = f"Senhor, o timer de {tempo_falado(segundos)} terminou.", f"timer de {tempo_falado(segundos)}"
        elif texto:
            fala, descricao = f"Senhor, está na hora de {texto}.", texto
        else:
            fala, descricao = "Senhor, o senhor me pediu para avisar agora.", "um aviso"
        self._agendar(segundos, fala, "lembrete", descricao)
        self._ui("nota", f"⏰ {descricao}, {quando} ({time.strftime('%H:%M', time.localtime(time.time() + segundos))})")
        return f"Certo, senhor. Aviso {quando}" + (f": {texto}." if texto and not pedido["timer"] else ".")

    def _listar_lembretes(self):
        lembretes = sorted((i for i in self._lembretes if i["tipo"] == "lembrete"), key=lambda i: i["quando"])
        foco = any(i["tipo"] == "foco" for i in self._lembretes)
        if not lembretes:
            return "Nenhum lembrete agendado, senhor." + (" O modo foco está ligado." if foco else "")
        partes = [f"{i['descricao']} às {time.strftime('%H:%M', time.localtime(i['quando']))}" for i in lembretes[:5]]
        total = len(lembretes)
        fala = f"Tenho {total} lembrete{'s' if total > 1 else ''}: " + "; ".join(partes) + "."
        return fala + (" E o modo foco está ligado." if foco else "")

    def _modo_foco(self, ligar, intervalo=1800, duracao=0):
        """Lembra de beber água a cada tanto tempo; com duração, avisa quando a sessão termina."""
        estava = self._cancelar_lembretes("foco")
        if not ligar:
            return "Modo foco desligado, senhor." if estava else "O modo foco não estava ligado, senhor."
        fim = duracao or 8 * 3600  # sem duração, fica ligado por até 8 horas
        frases = ["Senhor, hora de beber um pouco de água.", "Uma pausa rápida, senhor: beba água.",
                  "Lembrete do modo foco: um copo de água, senhor."]
        n = 1
        while n * intervalo < fim and n <= 60:
            self._agendar(n * intervalo, frases[(n - 1) % len(frases)], "foco")
            n += 1
        if duracao:
            self._agendar(duracao, "O modo foco terminou, senhor. Bom trabalho. Hora de levantar e descansar um pouco.", "foco")
            return (f"Modo foco ligado por {tempo_falado(duracao)}, senhor. "
                    f"Lembro de beber água a cada {tempo_falado(intervalo)}.")
        return f"Modo foco ligado, senhor. Lembro de beber água a cada {tempo_falado(intervalo)}. Diga desliga o modo foco para parar."

    # ---------- notícias, briefing e erros ----------
    def _manchetes(self, assunto="", quantidade=5):
        """Manchetes do Google Notícias; mostra no registro e devolve a lista (vazia se falhar)."""
        import noticias
        try:
            lista = noticias.manchetes(assunto, quantidade)
        except Exception:
            log.warning("Não consegui ler as notícias de %r", assunto, exc_info=True)
            return []
        for titulo, fonte, _ in lista:
            self._ui("nota", f"📰 {titulo}" + (f" ({fonte})" if fonte else ""))
        return lista

    def _noticias(self, assunto):
        self._ui("atividade", "Lendo as notícias")
        lista = self._manchetes(assunto, 5)
        if not lista:
            return "Não consegui ler as notícias agora, senhor. Pode ser a internet."
        sobre = f" sobre {assunto}" if assunto else ""
        return f"As principais notícias{sobre}, senhor: " + ". ".join(t for t, _, _ in lista) + "."

    def _briefing(self):
        """Resumo do dia: data, hora, lembretes, como está o notebook e três manchetes."""
        hora = datetime.datetime.now().hour
        periodo = "Bom dia" if 5 <= hora < 12 else "Boa tarde" if 12 <= hora < 18 else "Boa noite"
        partes = [f"{periodo}, senhor. {executar('que dia é hoje')} {executar('que horas são')}"]
        lembretes = sorted((i for i in self._lembretes if i["tipo"] == "lembrete"), key=lambda i: i["quando"])
        if lembretes:
            proximo = lembretes[0]
            partes.append(f"O senhor tem {len(lembretes)} lembrete{'s' if len(lembretes) > 1 else ''}; o próximo é "
                          f"{proximo['descricao']}, às {time.strftime('%H:%M', time.localtime(proximo['quando']))}.")
        else:
            partes.append("Não há lembretes agendados.")
        partes.append(executar("status do sistema"))
        lista = self._manchetes("", 3)
        if lista:
            partes.append("Nas notícias: " + ". ".join(t for t, _, _ in lista) + ".")
        return " ".join(partes)

    def _mostrar_erros(self):
        """Conta os erros recentes do registro e oferece pedir ao Claude para corrigir (com confirmação)."""
        import diagnostico
        erros = diagnostico.ultimos_erros(5)
        if not erros:
            return "Não encontrei erros nos últimos sete dias do registro, senhor."
        for erro in erros:
            vezes = f" ({erro['vezes']} vezes)" if erro["vezes"] > 1 else ""
            self._ui("nota", f"⚠ {erro['quando']:%d/%m %H:%M} · {erro['mensagem']}{vezes}"
                             + (f" · {erro['excecao']}" if erro["excecao"] else ""))
        ultimo = erros[0]
        fala = (f"Encontrei {len(erros)} tipo{'s' if len(erros) > 1 else ''} de erro recente{'s' if len(erros) > 1 else ''}, "
                f"estão no registro. O último foi {ultimo['quando']:%d/%m às %H:%M}: "
                f"{re.sub(r'https?://\S+', 'um link', ultimo['mensagem'])}.")
        if not claude_code.disponivel() or claude_code.ocupado():
            return fala
        pedido = ("Corrija estes erros que apareceram no registro do Jarvis (jarvis.log). Ache a causa no código e "
                  "conserte só o necessário; se um erro não for do código (microfone desligado, sem internet), "
                  "apenas deixe a mensagem mais clara ou não mude nada.\n\n"
                  + "\n\n".join(f"[{e['quando']:%d/%m %H:%M}, {e['vezes']}x]\n{e['trecho']}" for e in erros))

        def corrigir():
            threading.Thread(target=self._autoatualizar, args=(pedido,), daemon=True).start()
            return "Começando. Fiz um backup antes e aviso quando terminar, senhor."

        self._pendente = corrigir
        return fala + " Quer que eu peça ao Claude para corrigir?"

    def _modo_tela(self, tarefa, virtual=False):
        """Ferramenta controlar_notebook, no mini notebook 3D, passo a passo. O senhor pode pausar, parar ou
        corrigir no meio (botões ou voz).
        Padrão ("no notebook, ...", "usa a tela e ..."): o PC de verdade, mouse e teclado reais; as janelas ficam
        atrás do Braga e aparecem só no mini notebook. virtual=True ("no notebook virtual, ..."): no navegador do
        Braga, sem tocar no PC."""
        import notebook
        if notebook.sessao.controlando:
            if tarefa.strip():  # pedido novo no meio da tarefa = correção
                return self._notebook_controle("corrigir", tarefa)
            return "Já estou controlando o notebook, senhor. Diga: para o notebook, ou mande a correção."
        if claude_code.ocupado():
            return "Ainda estou com outra tarefa, senhor. Aguarde eu terminar."
        if not tarefa.strip():
            return "O que o senhor quer que eu faça no notebook?"
        import isolamento
        if not virtual and isolamento.ligado():
            return isolamento.bloqueado("o mouse e o teclado de verdade", "uso") + " Ou peça no notebook virtual."

        def trabalho():
            import agente_tela
            import pyautogui
            import navegador
            notebook.sessao.comecar(tarefa)
            self._ui("tarefa", "Notebook virtual" if virtual else "Controlando o PC real", tarefa)
            self.mostrar_principal()
            if virtual:
                navegador.preparar()
            self._ui("abrirNotebook", "navegador" if virtual else "pc")
            time.sleep(1.5)
            try:
                deu_certo, resumo = agente_tela.executar_tarefa(
                    tarefa, lambda fala: self._ui("atividade", fala),
                    alvo=notebook.alvo_virtual if virtual else notebook.alvo)
            except pyautogui.FailSafeException:
                resumo = "Parei, senhor: o mouse foi para o canto da tela, o freio de segurança."
            except Exception:
                log.exception("Falha no mini notebook")
                resumo = "Não consegui controlar o notebook, senhor."
            confirmar = notebook.sessao.confirmacao  # o agente parou num botão de enviar/publicar/excluir
            notebook.sessao.confirmacao = None
            notebook.sessao.terminar(resumo)
            self._ui("tarefa", None, None)
            with self._trava:
                if confirmar:
                    confirmar["virtual"] = virtual
                    self._pendente = lambda: self._notebook_confirmado(tarefa, confirmar)
                    self._falar(f"{confirmar['fala']} Confirma?")
                else:
                    if re.search(r"\?\s*$|\bme diga\b|\bquer que\b|\bposso\b", resumo, re.I):
                        # terminou oferecendo algo: o "sim" do senhor continua a mesma tarefa
                        self._pendente = lambda: self._modo_tela(
                            f"{tarefa}\nNa vez anterior você terminou assim: \"{resumo}\". O usuário respondeu: "
                            f"\"{getattr(self, '_resposta_pendente', 'sim')}\". Continue a partir daí.", virtual)
                    self._falar(resumo)
                self._estado_parado()

        threading.Thread(target=trabalho, daemon=True).start()
        if virtual:
            return ("Entendido, senhor. Vou fazer isso no notebook virtual: nada abre no seu PC. Dá para pausar, "
                    "parar ou corrigir por lá.")
        return ("Entendido, senhor. Vou fazer isso no PC real, pelo mini notebook. Dá para pausar, parar ou corrigir "
                "por lá. Freio: mouse no canto superior esquerdo.")

    def _notebook_confirmado(self, tarefa, confirmar):
        """O senhor disse sim: o Braga clica no botão que o agente apontou (enviar, publicar, excluir) e confere."""
        import navegador
        import notebook
        try:
            if confirmar.get("virtual", True):
                navegador.clicar(confirmar["fx"] * navegador.LARGURA, confirmar["fy"] * navegador.ALTURA)
            else:
                notebook.controle.clicar(confirmar["fx"], confirmar["fy"])
            notebook.sessao.registrar(f"Confirmado pelo senhor: {confirmar['fala']}")
        except Exception as erro:
            log.exception("Mini notebook: falha no clique confirmado")
            return f"Não consegui clicar, senhor. {str(erro)[:120]}"
        return self._modo_tela(f"{tarefa}\nO usuário confirmou e o Braga já clicou: {confirmar['fala']} "
                               "Confira na tela se deu certo e conclua (não clique de novo no mesmo botão).",
                               confirmar.get("virtual", True))

    def _modo_fundo(self, ligar):
        import fundo
        hwnd = fundo.achar_janela()
        if not hwnd:
            return "Não encontrei minha janela, senhor."
        if ligar:
            if fundo.ancorar(hwnd):
                return "Pronto, senhor. Agora sou a tela de fundo. Os ícones continuam por cima de mim."
            return "Não consegui me fixar no fundo desta vez, senhor. Veja o registro."
        fundo.soltar(hwnd)
        return "Voltei a ser uma janela normal, senhor."

    def _preparar_apagar(self, texto):
        """Apaga itens da biblioteca, mas só depois de você confirmar."""
        t = normalizar(texto)
        if re.search(r"\d+", t) and not re.search(r"\b(tudo|todas?|todos)\b", t):
            return ("Não sei quais itens são esses, senhor. Diga o nome deles, por exemplo: "
                    "apaga o item logo, ou diga apagar tudo para esvaziar a biblioteca.")
        if re.search(r"\b(tudo|todas?|todos)\b", t):
            alvos = biblioteca.listar()
            descricao = "todos os itens da biblioteca"
        else:
            termo = re.sub(r"\b(apag\w*|remov\w*|tira\w*|exclu\w*|delet\w*|da|de|do|a|o|as|os|biblioteca|bibliotecas|item|itens|arquivo|arquivos)\b", " ", t)
            termo = " ".join(termo.split())
            alvos = biblioteca.buscar(termo) if termo else []
            if not alvos:
                return "Não encontrei esse item na biblioteca, senhor. Diga o nome dele ou diga apagar tudo."
            descricao = f"{len(alvos)} item(ns) com o nome '{termo}'"
        ids = {i["id"] for i in alvos}

        def apagar():
            apagados = biblioteca.remover(ids)
            self._ui("biblioteca", biblioteca.listar()[:40])
            return f"Pronto, senhor. Apaguei {apagados} itens da biblioteca."

        self._pendente = apagar
        return f"Vou apagar {descricao}, incluindo os arquivos guardados. Confirma?"

    def _preparar_email(self, texto):
        """Monta o e-mail e pede confirmação antes de enviar. Nunca envia direto."""
        if not enviar_email.configurado():
            enviar_email.preparar()
            _editar(enviar_email.CONFIG)
            return ("Ainda não configurei seu e-mail, senhor. Abri o arquivo de configuração: coloque seu endereço "
                    "e a senha de app do Gmail, salve, e depois peça de novo.")
        destino, assunto, corpo = enviar_email.interpretar(texto)
        if not destino:
            return "Para quem eu envio, senhor? Diga o e-mail ou um contato salvo."
        if not corpo:
            return "E o que o senhor quer escrever?"

        def enviar():
            try:
                enviar_email.enviar(destino, assunto, corpo)
                return f"E-mail enviado para {destino}, senhor."
            except Exception as erro:
                log.exception("Falha ao enviar e-mail")
                return f"Não consegui enviar, senhor. O erro foi: {erro}"

        self._pendente = enviar
        self._ui("nota", f"✉ Para: {destino}\n{corpo}")
        return f"Vou enviar para {destino} o seguinte: {corpo}. Confirmo o envio?"

    def _achar_apk(self, alvo):
        """Acha um APK para analisar: o que o usuário descreveu, ou o mais recente da biblioteca/projetos."""
        candidatos = [i["arquivo"] for i in biblioteca.listar()
                      if i.get("arquivo", "").lower().endswith(".apk") and os.path.exists(i["arquivo"])]
        for projeto in memoria.projetos():
            candidatos += [a for a in projeto.get("arquivos", []) if a.lower().endswith(".apk")]
        if alvo:
            alvo = alvo.lower()
            for caminho in candidatos:
                if alvo in os.path.basename(caminho).lower():
                    return caminho
        return candidatos[0] if candidatos else None

    def _analisar_fundo(self, funcao, titulo, assunto):
        """Roda uma análise (engenharia) em segundo plano, fala o resumo e salva o relatório."""
        def tarefa():
            self._ui("tarefa", titulo, assunto)
            try:
                deu_certo, texto = funcao()
            except Exception:
                log.exception("Falha na análise de engenharia")
                deu_certo, texto = False, ""
            self._ui("tarefa", None, None)
            if deu_certo:
                destino = os.path.join(claude_code.PROJETOS, "analises")
                os.makedirs(destino, exist_ok=True)
                nome = re.sub(r"[^\w.-]+", "-", assunto)[:60] or "analise"
                caminho = os.path.join(destino, f"engenharia-{nome}.md")
                with open(caminho, "w", encoding="utf-8") as arquivo:
                    arquivo.write(f"# Engenharia: {assunto}\n\n{texto}\n")
                self._ui("nota", caminho)
                resumo = " ".join(texto.split("\n\n")[0].split()[:60])
                with self._trava:
                    self._falar(f"Pronto, senhor. {resumo} O relatório completo está salvo na pasta análises.")
                    self._estado_parado()
            else:
                with self._trava:
                    self._falar(texto or "Não consegui concluir a análise, senhor. Veja o registro.")
                    self._estado_parado()
        threading.Thread(target=tarefa, daemon=True).start()

    def _onde_esta(self, so_android):
        """Diz onde está o último projeto (ou APK) e abre a pasta com o arquivo selecionado."""
        lista = [p for p in memoria.projetos() if os.path.isdir(p["pasta"])]
        if so_android:
            lista = [p for p in lista if p["tipo"] == "android"]
        if not lista:
            return "Ainda não tenho nenhum projeto desse tipo na memória, senhor."
        projeto = lista[0]
        for caminho in projeto["arquivos"] or [projeto["pasta"]]:
            self._ui("nota", caminho)
        principais = [a for a in projeto["arquivos"] if a.endswith((".apk", ".aab"))] or projeto["arquivos"]
        if principais:
            _mostrar_arquivo(principais[-1])
        else:
            _mostrar_arquivo(projeto["pasta"])
        pacotes = [os.path.basename(a) for a in principais if a.endswith((".apk", ".aab"))]
        detalhe = f" Os arquivos são {', '.join(pacotes)}." if pacotes else ""
        return (f"Está na pasta projetos, {projeto['nome']}, dentro de Documentos, Jarvis.{detalhe} "
                "Abri a pasta para o senhor, e o caminho completo está no registro.")

    def _trabalhar(self, funcao, pedido, titulo):
        """Roda uma tarefa longa do Claude Code em segundo plano."""
        self._ui("tarefa", titulo, pedido)
        narrado = {"quando": 0.0, "ultimo": ""}

        def ao_evento(texto):
            log.info("claude: %s", texto)
            self._ui("atividade", texto)
            self._narrar_passo(texto, narrado)

        try:
            deu_certo, resposta, pasta = funcao(pedido, ao_evento)
        except Exception:
            log.exception("Falha na tarefa do Claude")
            deu_certo, resposta, pasta = False, "", None
        log.info("Tarefa do Claude %s: %s", "concluída" if deu_certo else "falhou", resposta)
        self._ui("tarefa", None, None)
        if pasta:
            tipo = "android" if claude_code.eh_android(pasta) else "web"
            memoria.registrar_projeto(pasta, tipo, pedido, resposta if deu_certo else "falhou: " + resposta)
            for caminho in memoria.arquivos_gerados(pasta):
                self._ui("nota", caminho)

        with self._trava:
            if deu_certo:
                if pasta:
                    _abrir_projeto(pasta)
                final = f"Pronto, senhor. {resposta}"
            else:
                final = resposta or "Desculpe, senhor. O Claude não conseguiu terminar a tarefa. Os detalhes estão no registro."
            self._falar(final)
            self._estado_parado()
        # avisa também pelo Telegram, se estiver ligado
        if self._bot:
            self._bot.avisar_todos(final)

    # ---------- escuta ----------
    def _saudar_e_ouvir(self):
        hora = datetime.datetime.now().hour
        if 5 <= hora < 12:
            periodo = "Bom dia"
        elif 12 <= hora < 18:
            periodo = "Boa tarde"
        else:
            periodo = "Boa noite"
        self._falar(f"{periodo}, senhor. Todos os sistemas estão online.", lembrar=False)
        self._estado_parado()
        self._ouvir()

    def _ouvir(self):
        reconhecedor = sr.Recognizer()
        reconhecedor.pause_threshold = 0.9
        reconhecedor.non_speaking_duration = 0.5
        reconhecedor.dynamic_energy_threshold = True
        while True:  # se o microfone cair, tenta abrir de novo
            try:
                with sr.Microphone() as fonte:
                    reconhecedor.adjust_for_ambient_noise(fonte, duration=1.5)
                    calibrado = time.time()
                    log.info("Microfone pronto (sensibilidade %.0f)", reconhecedor.energy_threshold)
                    self._estado_parado()
                    while True:
                        if not self._mic_ligado or self._falando.is_set() or self._trava.locked():
                            time.sleep(0.2)
                            continue
                        if time.time() - calibrado > RECALIBRAR_A_CADA and not self._ouvir_agora.is_set():
                            reconhecedor.adjust_for_ambient_noise(fonte, duration=0.5)
                            calibrado = time.time()
                        try:
                            self._rodada(reconhecedor, fonte)
                        except OSError:
                            raise  # problema no microfone: reabre lá fora
                        except Exception:
                            # um erro numa frase não pode deixar o Jarvis surdo
                            log.exception("Erro ao tratar o que foi ouvido")
                            self._ouvir_agora.clear()
                            time.sleep(0.5)
            except Exception:
                log.exception("Microfone indisponível, tentando de novo em 10 segundos")
                self._mudar_estado("sem-microfone")
                time.sleep(10)

    def _rodada(self, reconhecedor, fonte):
        """Escuta uma frase e decide o que fazer com ela."""
        if not self._ouvir_agora.is_set():
            self._estado_parado()
        alternativas = self._escutar(reconhecedor, fonte, limite=12)
        direto = self._ouvir_agora.is_set()
        if not alternativas:
            return
        log.info("Ouvi: %s", " | ".join(alternativas[:3]))
        self._ui("ouviu", alternativas[0])

        if direto:
            self._ouvir_agora.clear()
            self._processar(alternativas[0])
            return

        chamado = next((a for a in alternativas if separar_chamado(a) is not None), None)
        if not chamado:
            return
        if separar_chamado(chamado):
            self._processar(chamado)
        else:
            # Só chamou "Jarvis": bipa e espera o comando
            self._ouvir_agora.set()
            self._mudar_estado("escutando")
            self._ui("bip")

    def _escutar(self, reconhecedor, fonte, limite):
        """Escuta uma frase e devolve as possíveis transcrições, da mais provável para a menos."""
        try:
            audio = reconhecedor.listen(fonte, timeout=5, phrase_time_limit=limite)
        except sr.WaitTimeoutError:
            if self._ouvir_agora.is_set():
                self._ouvir_agora.clear()  # apertou o botão e não falou nada
            return []
        if self._falando.is_set():
            return []  # ouviu a própria voz
        try:
            resultado = reconhecedor.recognize_google(audio, language="pt-BR", show_all=True)
        except sr.UnknownValueError:
            return []  # barulho que não virou palavra
        except sr.RequestError:
            log.warning("Sem conexão com o reconhecimento de voz", exc_info=True)
            self._mudar_estado("offline")
            time.sleep(3)
            return []
        if not isinstance(resultado, dict):
            return []
        return [a["transcript"] for a in resultado.get("alternative", []) if a.get("transcript")]


def _abrir_projeto(pasta):
    if claude_code.eh_android(pasta):
        studio = os.path.join(claude_code.STUDIO, "bin", "studio64.exe")
        import isolamento
        if os.path.exists(studio) and not isolamento.ligado():  # no modo isolado o Android Studio não abre no PC
            isolamento.antes_de_abrir_no_pc()
            subprocess.Popen([studio, pasta])
        apk = claude_code.apk_de(pasta)
        # mostra o APK selecionado no explorador de arquivos
        _mostrar_arquivo(apk or pasta)
        return
    index = os.path.join(pasta, "index.html")
    try:
        os.startfile(index if os.path.exists(index) else pasta)
    except OSError:
        log.warning("Não consegui abrir %s", pasta, exc_info=True)


def _editar(caminho):
    """Arquivo de configuração para o senhor preencher: Bloco de Notas no PC, ou só a leitura no notebook virtual
    quando o modo isolado está ligado."""
    import isolamento
    if isolamento.ligado():
        isolamento.abrir(caminho)
    else:
        isolamento.antes_de_abrir_no_pc()  # o Bloco de Notas abre atrás do Braga, no mini notebook
        subprocess.Popen(["notepad", caminho])


def _mostrar_arquivo(caminho):
    """Abre o Explorador com o arquivo selecionado (ou a pasta). Se o Windows negar, só registra:
    o trabalho já foi feito, e não pode virar "falhou" por causa da janela que mostra o resultado.
    No modo isolado, o arquivo (ou a pasta) aparece no notebook virtual, e nenhuma janela abre no PC."""
    import isolamento
    if isolamento.ligado():
        isolamento.abrir(caminho)
        return
    isolamento.antes_de_abrir_no_pc()  # o Explorador abre atrás do Braga, no mini notebook
    explorer = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "explorer.exe")
    try:
        if os.path.isfile(caminho):
            subprocess.Popen([explorer, "/select,", caminho])
        else:
            os.startfile(caminho)
    except OSError:
        log.warning("Não consegui mostrar %s no Explorador", caminho, exc_info=True)
        try:
            os.startfile(os.path.dirname(caminho) if os.path.isfile(caminho) else caminho)
        except OSError:
            pass


def _voz_windows(texto):
    """Voz de reserva, sem internet."""
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.Speak($env:JARVIS_FALA)"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        env={**os.environ, "JARVIS_FALA": texto},
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def main():
    logging.basicConfig(
        filename=os.path.join(PASTA, "jarvis.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    if not _sou_o_unico():
        log.info("O Jarvis já estava aberto: trouxe a janela para a frente")
        return
    log.info("Iniciando o Jarvis")
    segredos.preparar()
    jarvis = Jarvis()
    import isolamento  # modo isolado: sites, arquivos e pastas abrem só no notebook virtual, não no PC
    isolamento.instalar()
    isolamento.ao_abrir = jarvis._abrir_no_virtual
    isolamento.ao_bloquear = lambda frase: jarvis._ui("aviso", frase)
    isolamento.ao_abrir_no_pc = jarvis._preparar_pc
    biblioteca.ao_concluir = jarvis._biblioteca_pronta
    biblioteca.preparar()
    enviar_email.preparar()
    # Bot do Telegram (só liga se houver token no .env)
    jarvis._bot = telegram_bot.iniciar(jarvis.responder, jarvis.status)
    import notebook
    notebook.atalho_parar(lambda: jarvis._ui("parado", "Ctrl+Alt+Q"))  # freio pelo teclado, em qualquer janela
    # a interface é a do Jarvis 2 (visual v6): esfera, tela grande e notebook 3D com a tela do PC
    try:
        interface = servidor.iniciar() + "/interface/v6/index.html"
    except Exception:
        log.exception("Servidor local falhou; abrindo a interface direto do arquivo (sem a tela ao vivo)")
        interface = os.path.join(PASTA, "interface", "v6", "index.html")
    janela = webview.create_window(
        identidade.SIGLA,
        interface,
        js_api=jarvis,
        maximized=True,
        min_size=(900, 600),
        background_color="#020a12",
    )
    jarvis._janela = janela
    threading.Thread(target=_vigiar_abertura, args=(jarvis,), daemon=True).start()
    threading.Thread(target=jarvis._vigiar_github, daemon=True).start()
    threading.Thread(target=jarvis._vigiar_respostas, daemon=True).start()
    webview.start()


_trava_unica = None  # fica aberta enquanto o Jarvis roda


def _sou_o_unico():
    """Só um Jarvis por vez: dois brigam pela janela e pelo microfone, e o segundo trava.
    Se já houver um aberto, traz a janela dele para a frente e devolve False."""
    global _trava_unica
    import ctypes
    kernel32, user32 = ctypes.windll.kernel32, ctypes.windll.user32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    reaberto = os.environ.get("JARVIS_REABERTO")
    for _ in range(60):  # até 15 s
        trava = kernel32.CreateMutexW(None, True, "Local\\JarvisAssistenteUnico")
        if kernel32.GetLastError() != 183:  # 183 = ERROR_ALREADY_EXISTS
            _trava_unica = trava
            return True
        kernel32.CloseHandle(ctypes.c_void_p(trava))
        janela = user32.FindWindowW(None, identidade.SIGLA)
        if janela and not reaberto:
            user32.ShowWindow(janela, 9)  # 9 = restaurar, se estiver minimizada
            user32.SetForegroundWindow(janela)
            return False
        # sem janela: o Jarvis antigo está fechando (ou travou e a vigia vai fechá-lo); espera ele sair
        time.sleep(0.25)
    return False


def _vigiar_abertura(jarvis, limite=60):
    """Raramente o Windows trava ao carregar a janela (o .NET do pywebview). Se em 60 s a interface não
    avisou que abriu, o Jarvis se abre de novo, uma vez só, e este processo encerra."""
    time.sleep(limite)
    if jarvis._iniciado:
        return
    if os.environ.get("JARVIS_REABERTO"):
        log.error("A janela não abriu de novo em %d s. Feche o Jarvis e abra pelo atalho.", limite)
        return
    log.warning("A janela não abriu em %d s; abrindo o Jarvis de novo", limite)
    subprocess.Popen([sys.executable, os.path.join(PASTA, "app.py")], cwd=PASTA,
                     env={**os.environ, "JARVIS_REABERTO": "1"})
    os._exit(1)


if __name__ == "__main__":
    main()
