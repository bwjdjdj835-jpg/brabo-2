# J.A.R.V.I.S. — Estação Zero (v3: Ryker no Quarto do Braga)

Assistente estilo Jarvis feito em **Python** (FastAPI) com interface 3D futurista (Three.js):
uma sala 3D onde o agente Jarvis está sentado em frente a um notebook Intel Core i5 13ª geração,
com câmera virtual, HUD holográfico, chat e animação de fala (boca, cabeça, olhos e brilho).

## Estrutura
```
app/brain.py     -> "cérebro": interpreta comandos em português (troque por um LLM depois)
app/server.py    -> servidor FastAPI (API /api/chat e /api/status + arquivos da interface)
web/index.html   -> HUD (painéis, chat, indicador de fala)
web/style.css    -> visual holográfico
web/scene.js     -> cena 3D: sala, mesa, notebook, cadeira, agente, holograma, bloom
web/main.js      -> chat, voz (TTS do navegador pt-BR ou modo simulado), animações do HUD
run.py           -> inicia o servidor e abre o navegador
tools_screenshots.py -> gera capturas com Playwright (opcional)
```

## Como rodar
Requer Python 3.10+ e internet (o Three.js é carregado via CDN).

**Windows (PowerShell):**
```
cd jarvis
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

**Linux:**
```
cd jarvis
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```
Abre em http://127.0.0.1:8000.

## Uso
- Digite no chat: "oi", "que horas são", "que dia é hoje", "status do sistema", "conte uma piada".
- Caixa **Voz real**: marcada usa a voz pt-BR do navegador; desmarcada usa fala simulada (só animação).
- Mouse: arraste para girar a câmera, roda para zoom.
- No console do navegador: `jarvis.cena.vista(0|1|2)` troca o enquadramento da câmera.

## Próximos passos
Reconhecimento de voz (microfone), ligar o `brain.py` a um LLM, e captura da tela real do notebook.

## v2 — Cena modelada no Blender

A sala, a mesa, a cadeira, o notebook e o androide agora são modelados no **Blender 4.2** (por script Python/bpy) e exportados como `web/assets/jarvis_cena.glb`. O `web/scene.js` carrega o GLB com `GLTFLoader`; se o arquivo não carregar (ou se abrir `http://127.0.0.1:8000/?v1`), a cena antiga (v1) aparece como reserva.

- **Androide**: corpo orgânico (modificador Skin + Subdivision), visor escuro, olhos e reator neon, juntas escuras. A boca tem a *shape key* `Fala`, e a cabeça é um nó separado (`Cabeca`) com pivô no pescoço. O navegador anima os dois enquanto ele fala.
- **Notebook**: corpo de alumínio com cantos arredondados, 70 teclas, touchpad, webcam, adesivo **intel CORE i5 13th GEN** e tela com material próprio (`TelaAoVivo`, objeto `Tela`). No navegador essa tela recebe a textura ao vivo.
- **Sala**: mesa de madeira com fita de LED, cadeira de escritório (base estrela e rodinhas), painéis acústicos, estante com livros, luminária, caneca, mouse e planta.

Arquivos:
- `blender/build_scene.py`: gera tudo. Rode `blender -b -P blender/build_scene.py` (só exporta) ou com `-- --render` (exporta e gera as renders em `renders/`).
- `blender/jarvis_cena.blend`: o arquivo pronto pra abrir e editar no Blender.
- `blender/make_sticker.py`: gera o adesivo i5.

Licença dos assets: tudo foi modelado do zero neste projeto, sem modelos de terceiros, então é seu. Three.js usa licença MIT.

## v3 — Ryker no Quarto do Braga (seguindo as fichas técnicas)

A v3 refaz tudo a partir das 4 fichas de referência (personagem, quarto, notebook e câmera). O visual é **anime estilizado** (toon/cel com contorno), não fotorrealista.

**O que tem na cena** (tudo gerado por `blender/build_scene_v3.py`, Blender 4.2):
- **Ryker**: rapaz de 19 anos, atlético, cabelo vermelho espetado, moletom preto sem manga com zíper, frisos vermelhos, capuz e emblema vermelho no peito, cinto com fivela, calça preta com listra vermelha lateral, luvas sem dedos e tênis vermelho/preto com sola branca. Olhos grandes estilo anime.
- **Rig (armadura)** com 23 ossos (quadril, coluna, peito, pescoço, cabeça, ombros, braços, antebraços, mãos, dedos, polegares, coxas, canelas, pés), pesos automáticos, modelado já sentado digitando.
- **Shape keys**: `Fala` (boca e queixo abrem) e `Piscar` (olhos).
- **Quarto do Braga** 3,5 × 3,0 × 2,6 m: paredes azuis, piso de cerâmica branca, porta de madeira, janela com grade e cortinas escuras, cama de solteiro com lençol camuflado, mesa com cadeira, guarda-roupa, cômoda, ventilador, prateleiras com livros, pôsteres, tapete e plafon no teto.
- **Notebook Lenovo ThinkPad** preto: teclado, TrackPoint vermelho, touchpad com listras vermelhas, logos "ThinkPad" e "lenovo", selo i5 e a tela `Tela` (material `TelaAoVivo`) que recebe a textura ao vivo no navegador.
- **Webcam 1080p** (estilo Logitech, "logi", "HD 1080p", LED) num mini tripé na mesa, virada pro Ryker. O ponto `WebcamOlho` define a câmera LIVE.

**Interface** (`web/`):
- Visão principal = **LIVE da webcam** (selo LIVE, cantos de visor, CAM 01 · 1080p · 30 fps, relógio).
- Botões de vista: **LIVE webcam**, **360° órbita** (gira sozinha em volta dele; dá pra arrastar), **Quarto** e **Rosto**.
- Chat em pt-BR: você manda mensagem, o Jarvis responde, o Ryker vira pra câmera, abre a boca no ritmo da fala e gesticula com a mão direita. A conversa também aparece na tela do notebook.
- Parado, ele digita (dedos e mãos), respira e pisca sozinho.
- Caixa **Voz real**: usa a voz pt-BR do navegador (desmarcada = fala simulada).
- No console: `jarvis.cena.vista('live'|'orbita'|'quarto'|'rosto')`.

**Arquivos da v3**:
- `blender/build_scene_v3.py`: gera tudo. `blender -b -P blender/build_scene_v3.py` só exporta; com `-- --render` também gera as renders.
- `blender/jarvis_cena_v3.blend`: arquivo pronto pra abrir no Blender.
- `web/assets/jarvis_v3.glb`: cena + personagem rigado exportados.
- `renders/v3_0*.png`: renders do Blender. `screenshots/v3_0*.png`: capturas da interface.

**Limitações conhecidas**: o corpo é feito de tubos suavizados (modificador Skin), então ombros e axilas ainda ficam simples, sem dedos individuais articulados (os 4 dedos dobram juntos). O cabelo é um conjunto de mechas em cone. As animações são procedurais no navegador, não são clipes do Blender.

## v4 — O Ryker mexe no SEU PC (tela espelhada + controle real)

**A ideia:** a tela do ThinkPad 3D é a **sua tela de verdade, ao vivo**. O que o Ryker clica lá, clica no seu PC.

### O que mudou
- **ThinkPad realista** (`blender/build_scene_v4.py` + `blender/make_teclado.py`): proporções de um T15 de 15,6", materiais PBR (`TP_*`), teclado ABNT2 com 81 teclas legendadas (Ç, Fn, PrtSc...), TrackPoint vermelho, 3 botões com faixas vermelhas, touchpad, moldura com webcam, logos Lenovo/ThinkPad, LEDs, portas laterais. O Ryker continua no estilo toon.
- **Câmera padrão por cima do ombro**: a tela fica grande e legível. Vistas disponíveis: *Ombro (padrão)*, *Tela de frente* (a melhor para clicar), *LIVE webcam*, *360° órbita*, *Quarto* e *Rosto*.
- **Espelho ao vivo**: `app/captura.py` captura a tela com mss + Pillow, até 1920 px, ~10 fps, em JPEG. Os quadros vão pelo WebSocket `/ws/tela` e são desenhados num canvas 1920×1080, que é a textura da tela 3D, com anisotropia máxima.
- **Cursor 3D grande + anel de mira** (verde se o controle estiver ligado, amarelo se desligado) e uma onda vermelha a cada clique, tudo bem visível.
- **Clique direto na tela 3D**: o raycast acha a coordenada UV da tela 3D, e ela é convertida em pixel da tela real (`Controle.uv_para_px`) para o pyautogui clicar no PC. Funciona com clique, duplo clique e botão direito.
- **O Ryker anima em sincronia**: a mão direita vai até o touchpad/TrackPoint, o cursor 3D desliza até o alvo e, quando o dedo "clica", a ação é enviada (`POST /api/acao`). Para digitar, os dedos das duas mãos se mexem.
- **Chat que vira ação** (`app/brain.py`, `CerebroRegras`), com comandos encadeados. Exemplos: "clica no meio da tela e digita olá mundo", "clica em 500 300", "clica em 30% 70%", "duplo clique no centro", "aperta ctrl+c", "aperta alt+tab", "abre youtube.com", "rola pra baixo". Para plugar uma IA depois, troque `cerebro` por qualquer objeto com `interpretar(texto, alvos, tela) -> (resposta, acoes)`.

### Segurança (leia!)
- **O controle começa DESLIGADO.** Ligue no botão grande **CONTROLE DO PC**; ele pede confirmação antes.
- **PARAR**: o botão vermelho, **Esc 3 vezes** (na janela do Jarvis) ou **Ctrl+Alt+Q** (atalho global, que funciona com o pynput no Windows). Qualquer um deles desliga o controle na hora.
- **Failsafe do pyautogui**: jogue o mouse num **canto da tela** para parar e desligar.
- O **LOG DE AÇÕES** (painel à esquerda) registra tudo o que foi feito e o que foi recusado.
- Ações com o controle desligado são recusadas pelo servidor, não só pela interface.

### Rodar no Windows
```
pip install -r requirements.txt
python run.py          # abre http://127.0.0.1:8000
```
Requer internet para baixar o three.js do CDN (unpkg).

### Testes feitos (display virtual :7, 1920×1080)
`tools/teste_v4_desktop_falso.py` abre uma "área de trabalho" de teste com botões grandes e um contador de cliques. `tools/teste_v4_espelho_clique.py` liga o controle, clica no botão **YouTube** dentro da tela 3D e prova que o clique chegou ao PC: o contador passou de 0 para 1 e o botão ficou com contorno amarelo.
- `screenshots/v4_01_ombro_espelho_ao_vivo.png`: vista do ombro com a tela real espelhada.
- `screenshots/v4_02_tela_de_frente.png`
- `screenshots/v4_03_ryker_clicando.png`: cursor 3D e mira no botão.
- `screenshots/v4_04_clique_refletido.png`, `v4_06_ombro_apos_clique.png`: "Cliques: 1" já aparece no espelho.
- `screenshots/v4_05_desktop_real_x7_apos_clique.png`: captura da tela "real", com o clique registrado.
- `screenshots/v4_07_parado.png`: depois do PARAR.
- Renders do Blender: `renders/v4_01_CamOmbro.png`, `v4_02_CamNotebook.png`, `v4_03_CamPorta.png`.

### Limitações
- Ainda **não há OCR nem visão**: "clica no botão Salvar" pelo nome não funciona. Use coordenadas, lugares nomeados (meio, cantos...) ou o dicionário `alvos`. Esse é o ponto para plugar uma IA com visão.
- **Só o monitor principal** é espelhado e controlado.
- Texto com acento é colado pela área de transferência (pyperclip + Ctrl+V), então ela é sobrescrita.
- No Linux o pynput é opcional, e sem ele não existe o atalho global (Ctrl+Alt+Q). Esc×3 funciona só com a janela do Jarvis em foco. O failsafe do canto funciona sempre.
- Há uma latência de cerca de 100 a 300 ms (10 fps em JPEG). Para mais fluidez, ajuste `CapturaTela(fps=..., qualidade=...)`.
- Se o espelho estiver aberto na mesma tela que está sendo capturada, aparece o "efeito túnel" (a tela dentro da tela). Isso é normal; o ideal é usar em tela cheia com a vista *Tela de frente*.

## v5 — "Live" pela câmera 5D no tripé (versão final)

> Os screenshots `v4_*` foram substituídos pelos `v5_*` abaixo. Toda a funcionalidade da v4 continua: espelho ao vivo, clique na tela 3D = clique no PC, controle desligado por padrão, PARAR/Esc×3/Ctrl+Alt+Q, failsafe e log.

### O que mudou
- **Câmera 5D no tripé** modelada no quarto (`blender/build_scene_v5.py`, objetos `Cam5D_*`), atrás e ao lado do Ryker. Tem tripé de 3 pernas, corpo, lente, monitor traseiro, LED REC vermelho e antenas.
- **A vista padrão agora é a LIVE da câmera 5D.** Nela aparecem o Ryker sentado da cintura pra cima, as **mãos no teclado/touchpad** e a **tela do notebook espelhando a sua tela**. A posição vem do objeto `Cam5DOlho` do modelo.
- **Botões de vista iguais à referência:** **1. Medium shot** (por trás do Ryker), **2. Close-up na tela** (tela + mãos; a melhor para clicar) e **3. Over-the-shoulder**. Continuam Tela de frente, LIVE webcam, 360°, Quarto e Rosto.
- **Ryker melhorado:** corpo mais atlético (peito e ombros maiores, cintura menor), **cabelo espetado anime penteado pra trás** (não é mais "coroa"), e **dedos com ossos separados** (`Finger0..3_L/R`), animados com defasagem ao digitar e ao clicar.
- Renders: `renders/v5_01_Cam5DLive.png`, `v5_02_CamCloseTela.png`, `v5_03_CamOmbro.png`, `v5_04_CamPorta.png` (nesta última a câmera 5D aparece no tripé).

### Testes (display virtual :7)
- `screenshots/v5_01_LIVE_camera5D_padrao.png`: a vista padrão, com mãos, notebook e tela visíveis.
- `screenshots/v5_02_medio.png`, `v5_03_close.png`, `v5_04_ombro.png`
- `screenshots/v5_05_live_ryker_clicando.png`, `v5_06_live_clique_refletido.png`: clique dado na tela 3D dentro da vista LIVE.
- `screenshots/v5_07_desktop_real_x7_apos_clique.png`: o clique chegou à tela "real" (o contador subiu e o botão YouTube ficou destacado).
- `screenshots/v5_08_parado.png`: depois do PARAR.


## ⚙️ Motor do agente (v6)
O Ryker agora tem uma "engrenagem" em Python com ferramentas: pesquisa web, comércios sem site, gerador de sites, Blender, anime 2D, Godot e controle do PC (local ou na nuvem). Veja **[motor/README.md](motor/README.md)**, com diagrama, chaves e segurança.
