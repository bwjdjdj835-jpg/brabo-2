"""Gerador de site profissional (estático, responsivo, interativo) para um comércio.

Pipeline: dados do comércio -> textos (LLM se houver, senão modelos por categoria) -> template HTML/CSS/JS
-> pasta saidas/sites/<slug>/ (index.html, style.css, app.js, dados.json) -> preview local opcional.
Recursos do site: menu fixo + menu mobile, hero com CTA WhatsApp, seções Sobre / Produtos (com filtro),
Depoimentos (carrossel), Horários (aberto/fechado agora), Mapa OpenStreetMap embutido, formulário que abre
o WhatsApp com a mensagem pronta, animações de rolagem, botão flutuante do WhatsApp, SEO (meta + JSON-LD).
"""
import html, json, os, re, socket, threading, functools, http.server
from ..registro import ferramenta
from .util import pasta, slug

TEMAS = {
    "padaria": dict(cor="#c26a1b", cor2="#3b2314", emoji="🥖", lema="Pão quentinho toda hora",
                    itens=[("Pão francês", "Crocante por fora, macio por dentro", "Pães"), ("Pão de queijo", "Receita mineira, sai do forno a toda hora", "Salgados"),
                           ("Bolo caseiro", "Cenoura, chocolate, milho e fubá", "Doces"), ("Sonho", "Recheio generoso de creme", "Doces"),
                           ("Café coado", "Grãos selecionados", "Bebidas"), ("Salgados", "Coxinha, esfiha e enroladinho", "Salgados")]),
    "restaurante": dict(cor="#b3261e", cor2="#2a1110", emoji="🍽️", lema="Comida caseira com sabor de verdade",
                        itens=[("Prato do dia", "Arroz, feijão, salada e mistura", "Pratos"), ("Peixe regional", "Tambaqui assado na brasa", "Pratos"),
                               ("Sobremesa", "Pudim da casa", "Doces"), ("Sucos naturais", "Cupuaçu, acerola, maracujá", "Bebidas")]),
    "padrao": dict(cor="#1f6feb", cor2="#0d1b2a", emoji="⭐", lema="Qualidade e atendimento que você merece",
                   itens=[("Atendimento", "Rápido e atencioso", "Serviços"), ("Qualidade", "Produtos selecionados", "Produtos"),
                          ("Preço justo", "Ótimo custo-benefício", "Produtos"), ("Entrega", "Consulte pelo WhatsApp", "Serviços")]),
}
TEMAS["padarias"] = TEMAS["padaria"]; TEMAS["restaurantes"] = TEMAS["restaurante"]


def _textos_llm(dados, tema):
    """Pede ao LLM configurado textos em JSON. Retorna None se não houver LLM ou der erro."""
    try:
        from ..llm import escolher_provedor
        p = escolher_provedor()
        if p.nome == "regras": return None
        pedido = (f"Escreva textos de marketing em pt-BR para o site do comércio abaixo. Responda APENAS JSON com as chaves "
                  f"lema, sobre (2 frases), itens (lista de 6 objetos nome/descricao/grupo), depoimentos (3 objetos nome/texto).\n{json.dumps(dados, ensure_ascii=False)}")
        r = p.pensar([{"papel": "usuario", "texto": pedido}], [])
        m = re.search(r"\{.*\}", r["texto"], re.S)
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def _wa(tel):
    d = re.sub(r"\D", "", tel or "")
    if d and not d.startswith("55"): d = "55" + d
    return d


@ferramenta(risco="arquivo")
def gerar_site(nome: str, categoria: str = "padrao", cidade: str = "", endereco: str = "", telefone: str = "",
               horario: str = "", lat: float = 0.0, lon: float = 0.0):
    """Gera um site profissional responsivo e interativo (HTML/CSS/JS) para um comércio e salva em saidas/sites/."""
    tema = TEMAS.get(categoria.lower(), TEMAS["padrao"])
    dados = dict(nome=nome, categoria=categoria, cidade=cidade, endereco=endereco, telefone=telefone, horario=horario, lat=lat, lon=lon)
    llm = _textos_llm(dados, tema) or {}
    lema = llm.get("lema") or tema["lema"]
    sobre = llm.get("sobre") or (f"A {nome} é referência em {categoria} {('em ' + cidade) if cidade else ''}. "
                                 f"Trabalhamos com ingredientes frescos, atendimento próximo e aquele cuidado de quem conhece cada cliente pelo nome.")
    itens = [(i["nome"], i["descricao"], i.get("grupo", "Produtos")) for i in llm.get("itens", [])] or tema["itens"]
    depo = [(d["nome"], d["texto"]) for d in llm.get("depoimentos", [])] or [
        ("Maria S.", f"Melhor {categoria} do bairro, atendimento nota 10!"), ("João P.", "Tudo sempre fresquinho. Virei cliente fiel."),
        ("Ana L.", "Preço justo e qualidade. Recomendo demais!")]
    wa = _wa(telefone); e = html.escape
    d = pasta("sites", slug(nome))
    grupos = list(dict.fromkeys(g for _, _, g in itens))
    mapa = (f'<iframe title="Mapa" loading="lazy" src="https://www.openstreetmap.org/export/embed.html?bbox={lon-.004}%2C{lat-.003}%2C{lon+.004}%2C{lat+.003}&layer=mapnik&marker={lat}%2C{lon}"></iframe>'
            if lat and lon else f'<div class="sem-mapa">{e(endereco or cidade)}</div>')
    jsonld = json.dumps({"@context": "https://schema.org", "@type": "LocalBusiness", "name": nome, "telephone": telefone,
                         "address": {"@type": "PostalAddress", "streetAddress": endereco, "addressLocality": cidade, "addressCountry": "BR"},
                         "openingHours": horario, "geo": {"@type": "GeoCoordinates", "latitude": lat, "longitude": lon}}, ensure_ascii=False)
    pagina = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(nome)} — {e(lema)}</title><meta name="description" content="{e(nome)}: {e(lema)}. {e(endereco)} {e(cidade)}">
<meta property="og:title" content="{e(nome)}"><meta property="og:description" content="{e(lema)}">
<link rel="stylesheet" href="style.css"><script type="application/ld+json">{jsonld}</script></head>
<body style="--cor:{tema['cor']};--cor2:{tema['cor2']}">
<header class="topo"><a class="marca" href="#inicio"><span>{tema['emoji']}</span>{e(nome)}</a>
<button class="burger" aria-label="Abrir menu" aria-expanded="false"><i></i><i></i><i></i></button>
<nav><a href="#sobre">Sobre</a><a href="#produtos">Produtos</a><a href="#depoimentos">Clientes</a><a href="#horarios">Horários</a><a href="#contato" class="btn">Fale conosco</a></nav></header>
<section id="inicio" class="hero"><div class="hero-txt revela"><p class="tag">{e(categoria.title())} {('· ' + e(cidade)) if cidade else ''}</p>
<h1>{e(nome)}</h1><p class="lema">{e(lema)}</p>
<div class="ctas"><a class="btn grande" href="{'https://wa.me/' + wa if wa else '#contato'}" target="_blank" rel="noopener">Pedir pelo WhatsApp</a><a class="btn fantasma" href="#produtos">Ver produtos</a></div>
<p id="status" class="status"></p></div><div class="hero-arte revela" aria-hidden="true"><span>{tema['emoji']}</span></div></section>
<section id="sobre" class="sec revela"><h2>Sobre nós</h2><p class="larga">{e(sobre)}</p>
<div class="numeros"><div><b data-n="10">0</b><span>anos de tradição</span></div><div><b data-n="500">0</b><span>clientes por dia</span></div><div><b data-n="100">0</b><span>% feito aqui</span></div></div></section>
<section id="produtos" class="sec"><h2 class="revela">Nossos produtos</h2><div class="filtros">{''.join(f'<button data-g="{e(g)}">{e(g)}</button>' for g in ['Todos'] + grupos)}</div>
<div class="grade">{''.join(f'<article class="card revela" data-g="{e(g)}"><div class="ic">{tema["emoji"]}</div><h3>{e(n)}</h3><p>{e(dsc)}</p><a href="#contato" class="pedir" data-item="{e(n)}">Quero este →</a></article>' for n, dsc, g in itens)}</div></section>
<section id="depoimentos" class="sec escura"><h2>O que dizem nossos clientes</h2><div class="carrossel">{''.join(f'<blockquote class="dep"><p>“{e(t)}”</p><cite>— {e(n)} ★★★★★</cite></blockquote>' for n, t in depo)}</div>
<div class="pontos"></div></section>
<section id="horarios" class="sec duas revela"><div><h2>Horários</h2><p class="hor">{e(horario or 'Seg a Sáb: 6h às 20h · Dom: 6h às 12h')}</p>
<h2>Endereço</h2><p>{e(endereco or 'Consulte pelo WhatsApp')}{(' — ' + e(cidade)) if cidade else ''}</p></div><div class="mapa">{mapa}</div></section>
<section id="contato" class="sec revela"><h2>Faça seu pedido</h2><form id="form"><input name="nome" placeholder="Seu nome" required><input name="pedido" id="pedido" placeholder="O que você deseja?" required>
<select name="tipo"><option>Retirar na loja</option><option>Entrega</option></select><button class="btn grande">Enviar pelo WhatsApp</button></form>
<p class="tel">{('📞 ' + e(telefone)) if telefone else ''}</p></section>
<footer>© <span id="ano"></span> {e(nome)} · Site criado pelo Jarvis</footer>
{f'<a class="wa-flutuante" href="https://wa.me/{wa}" target="_blank" rel="noopener" aria-label="WhatsApp">💬</a>' if wa else ''}
<script>window.NEGOCIO={json.dumps({"nome": nome, "wa": wa, "horario": horario}, ensure_ascii=False)}</script><script src="app.js"></script></body></html>"""
    css = """*{box-sizing:border-box;margin:0}html{scroll-behavior:smooth}body{font:16px/1.6 system-ui,Segoe UI,Roboto,sans-serif;color:#222;background:#fffaf5}
a{color:inherit}.topo{position:fixed;inset:0 0 auto;display:flex;align-items:center;justify-content:space-between;padding:14px 5vw;background:#fffaf5e6;backdrop-filter:blur(8px);z-index:10;transition:box-shadow .3s}
.topo.sombra{box-shadow:0 4px 20px #0002}.marca{font-weight:800;font-size:1.3rem;text-decoration:none;display:flex;gap:8px;align-items:center}
nav{display:flex;gap:22px;align-items:center}nav a{text-decoration:none;font-weight:600}.btn{background:var(--cor);color:#fff!important;padding:10px 18px;border-radius:999px;text-decoration:none;border:0;font-weight:700;cursor:pointer;transition:transform .2s,box-shadow .2s;display:inline-block}
.btn:hover{transform:translateY(-2px);box-shadow:0 8px 20px #0003}.btn.grande{padding:15px 28px;font-size:1.1rem}.btn.fantasma{background:transparent;color:var(--cor2)!important;border:2px solid var(--cor2)}
.burger{display:none;background:none;border:0;cursor:pointer}.burger i{display:block;width:26px;height:3px;background:#222;margin:5px;border-radius:2px;transition:.3s}
.hero{min-height:100vh;display:grid;grid-template-columns:1.2fr 1fr;align-items:center;gap:4vw;padding:110px 7vw 60px;background:radial-gradient(circle at 80% 30%,color-mix(in srgb,var(--cor) 25%,#fff),#fffaf5 60%)}
.tag{color:var(--cor);font-weight:700;letter-spacing:.08em;text-transform:uppercase}h1{font-size:clamp(2.4rem,6vw,4.6rem);line-height:1.05;color:var(--cor2);margin:.2em 0}
.lema{font-size:1.35rem;margin-bottom:1.4em}.ctas{display:flex;gap:14px;flex-wrap:wrap}.status{margin-top:18px;font-weight:700}.status.aberto{color:#1a7f37}.status.fechado{color:#b3261e}
.hero-arte{aspect-ratio:1;border-radius:40% 60% 55% 45%;background:linear-gradient(135deg,var(--cor),var(--cor2));display:grid;place-items:center;animation:flutua 6s ease-in-out infinite;box-shadow:0 30px 60px #0003}
.hero-arte span{font-size:clamp(6rem,16vw,12rem);filter:drop-shadow(0 10px 20px #0005)}@keyframes flutua{50%{transform:translateY(-14px) rotate(2deg);border-radius:55% 45% 40% 60%}}
.sec{padding:90px 7vw}h2{font-size:clamp(1.8rem,3.5vw,2.6rem);color:var(--cor2);margin-bottom:.6em}.larga{max-width:780px;font-size:1.15rem}
.numeros{display:flex;gap:40px;margin-top:40px;flex-wrap:wrap}.numeros b{font-size:2.8rem;color:var(--cor);display:block}
.filtros{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:26px}.filtros button{border:2px solid var(--cor);background:#fff;color:var(--cor);padding:8px 16px;border-radius:999px;font-weight:700;cursor:pointer}
.filtros button.on{background:var(--cor);color:#fff}.grade{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:22px}
.card{background:#fff;border-radius:20px;padding:26px;box-shadow:0 6px 24px #0001;transition:transform .3s,box-shadow .3s}.card:hover{transform:translateY(-6px);box-shadow:0 16px 40px #0002}
.card .ic{font-size:2.6rem}.card h3{margin:.4em 0 .2em}.pedir{color:var(--cor);font-weight:700;text-decoration:none}.card.oculto{display:none}
.escura{background:var(--cor2);color:#fff}.escura h2{color:#fff}.carrossel{position:relative;min-height:150px;max-width:760px}
.dep{position:absolute;inset:0;opacity:0;transform:translateX(30px);transition:.6s}.dep.on{opacity:1;transform:none}.dep p{font-size:1.4rem}.dep cite{color:#ffd27a}
.pontos{display:flex;gap:8px;margin-top:20px}.pontos button{width:12px;height:12px;border-radius:50%;border:0;background:#fff5;cursor:pointer}.pontos button.on{background:#fff}
.duas{display:grid;grid-template-columns:1fr 1.3fr;gap:40px}.mapa iframe,.sem-mapa{width:100%;height:340px;border:0;border-radius:20px;box-shadow:0 6px 24px #0002}.sem-mapa{display:grid;place-items:center;background:#eee}
#form{display:grid;gap:12px;max-width:560px}#form input,#form select{padding:14px;border-radius:12px;border:2px solid #ddd;font:inherit}#form input:focus{border-color:var(--cor);outline:0}
footer{text-align:center;padding:30px;background:#111;color:#aaa}.wa-flutuante{position:fixed;right:22px;bottom:22px;width:62px;height:62px;border-radius:50%;background:#25d366;display:grid;place-items:center;font-size:30px;text-decoration:none;box-shadow:0 8px 24px #0004;animation:pulsa 2s infinite;z-index:20}
@keyframes pulsa{50%{transform:scale(1.08)}}.revela{opacity:0;transform:translateY(30px);transition:opacity .8s,transform .8s}.revela.vis{opacity:1;transform:none}
@media(max-width:820px){.burger{display:block}nav{position:fixed;inset:64px 0 auto;flex-direction:column;background:#fffaf5;padding:20px;transform:translateY(-130%);transition:.35s;box-shadow:0 10px 30px #0002}
nav.aberto{transform:none}.hero,.duas{grid-template-columns:1fr}.hero-arte{max-width:300px;margin:auto}}"""
    js = """const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
$('#ano').textContent=new Date().getFullYear();
addEventListener('scroll',()=>$('.topo').classList.toggle('sombra',scrollY>10));
$('.burger').onclick=e=>{const n=$('nav');n.classList.toggle('aberto');e.currentTarget.setAttribute('aria-expanded',n.classList.contains('aberto'))};
$$('nav a').forEach(a=>a.onclick=()=>$('nav').classList.remove('aberto'));
const io=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){x.target.classList.add('vis');io.unobserve(x.target)}}),{threshold:.15});$$('.revela').forEach(el=>io.observe(el));
const io2=new IntersectionObserver(es=>es.forEach(x=>{if(!x.isIntersecting)return;const b=x.target,n=+b.dataset.n;let i=0;const t=setInterval(()=>{i+=Math.ceil(n/40);b.textContent=Math.min(i,n);if(i>=n)clearInterval(t)},30);io2.unobserve(b)}));$$('[data-n]').forEach(b=>io2.observe(b));
$$('.filtros button').forEach((b,i)=>{if(!i)b.classList.add('on');b.onclick=()=>{$$('.filtros button').forEach(x=>x.classList.toggle('on',x===b));$$('.card').forEach(c=>c.classList.toggle('oculto',b.dataset.g!=='Todos'&&c.dataset.g!==b.dataset.g))}});
const deps=$$('.dep'),pts=$('.pontos');let k=0;deps.forEach((d,i)=>{const b=document.createElement('button');b.setAttribute('aria-label','Depoimento '+(i+1));b.onclick=()=>mostra(i);pts.append(b)});
function mostra(i){k=i;deps.forEach((d,j)=>d.classList.toggle('on',j===i));$$('.pontos button').forEach((b,j)=>b.classList.toggle('on',j===i))}mostra(0);setInterval(()=>mostra((k+1)%deps.length),5000);
$$('.pedir').forEach(a=>a.onclick=()=>{$('#pedido').value=a.dataset.item;setTimeout(()=>$('#pedido').focus(),400)});
(function(){const h=new Date().getHours(),d=new Date().getDay();const ab=d===0?(h>=6&&h<12):(h>=6&&h<20);const s=$('#status');s.textContent=ab?'● Aberto agora':'● Fechado agora';s.className='status '+(ab?'aberto':'fechado')})();
$('#form').onsubmit=e=>{e.preventDefault();const f=new FormData(e.target);const msg=`Olá, ${NEGOCIO.nome}! Sou ${f.get('nome')}. Gostaria de: ${f.get('pedido')} (${f.get('tipo')}).`;
if(NEGOCIO.wa)open('https://wa.me/'+NEGOCIO.wa+'?text='+encodeURIComponent(msg),'_blank');else alert('Pedido anotado:\\n'+msg)};"""
    for n, c in (("index.html", pagina), ("style.css", css), ("app.js", js), ("dados.json", json.dumps(dados, ensure_ascii=False, indent=1))):
        with open(os.path.join(d, n), "w", encoding="utf-8") as f: f.write(c)
    return {"ok": True, "pasta": d, "index": os.path.join(d, "index.html"), "textos": "llm" if llm else "modelo"}


_servidores = {}


@ferramenta(risco="leitura")
def site_preview(pasta_site: str, porta: int = 0):
    """Sobe um servidor local (só 127.0.0.1) para pré-visualizar um site gerado; devolve a URL."""
    if pasta_site in _servidores: return {"ok": True, "url": _servidores[pasta_site]}
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=pasta_site)
    h.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", porta), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"; _servidores[pasta_site] = url
    return {"ok": True, "url": url}
