"""Anime 2D: (a) quadros desenhados por código com Pillow -> sprite sheet PNG + GIF animado;
(b) SVG animado escrito pelo LLM (ou um modelo pronto se não houver LLM)."""
import math, os, re
from PIL import Image, ImageDraw
from ..registro import ferramenta
from .util import pasta, slug


def _hex(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _quadro(t, tam, cabelo, roupa):
    """Personagem chibi: pulo/respiração + piscar + cabelo balançando. t em [0,1)."""
    S = 4; W = tam * S
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    pulo = abs(math.sin(t * 2 * math.pi)) * .08 * W
    cx, base = W / 2, W * .95 - pulo
    sq = 1 + .05 * math.cos(t * 4 * math.pi)
    L = 6 * S; preto = (20, 16, 24)
    d.ellipse([cx - W * .2, W * .93, cx + W * .2, W * .97], fill=(0, 0, 0, 60))            # sombra
    for s in (-1, 1):                                                                         # pernas
        d.rounded_rectangle([cx + s * W * .07 - W * .045, base - W * .2, cx + s * W * .07 + W * .045, base], 8 * S, fill=preto)
    d.rounded_rectangle([cx - W * .17, base - W * .45 * sq, cx + W * .17, base - W * .17], 30 * S, fill=_hex(roupa), outline=preto, width=L // 2)
    ang = math.sin(t * 2 * math.pi) * .4
    for s in (-1, 1):                                                                         # braços
        x0, y0 = cx + s * W * .17, base - W * .4
        x1, y1 = x0 + s * W * .12 * math.cos(ang * s), y0 + W * .14 + W * .05 * math.sin(ang)
        d.line([x0, y0, x1, y1], fill=_hex(roupa), width=int(W * .07)); d.ellipse([x1 - W * .04, y1 - W * .04, x1 + W * .04, y1 + W * .04], fill=(242, 201, 160), outline=preto, width=L // 3)
    hy = base - W * .66 * sq; r = W * .25
    bal = math.sin(t * 2 * math.pi + 1) * W * .02
    pts = []                                                                                  # cabelo espetado (estrela)
    for k in range(15):
        a = math.pi * (1.05 + k / 14 * .9 - 1) - math.pi / 2 + math.pi
        rr = r * (1.55 if k % 2 == 0 else 1.0)
        pts.append((cx + math.cos(a) * rr * 1.05 + (bal if k % 2 == 0 else 0), hy - r * .1 + math.sin(a) * rr))
    d.polygon(pts, fill=_hex(cabelo), outline=preto)
    d.ellipse([cx - r, hy - r, cx + r, hy + r], fill=(242, 201, 160), outline=preto, width=L // 2)
    d.chord([cx - r * 1.02, hy - r * 1.05, cx + r * 1.02, hy + r * .5], 180, 360, fill=_hex(cabelo), outline=preto, width=L // 2)
    for k in range(5):                                                                        # franja
        x = cx - r * .8 + k * r * .4
        d.polygon([(x - r * .22, hy - r * .35), (x + r * .22, hy - r * .35), (x + bal * .5, hy + r * .05)], fill=_hex(cabelo))
    piscar = (t % 1) > .9
    for s in (-1, 1):                                                                         # olhos grandes
        ex, ey = cx + s * r * .42, hy + r * .25
        if piscar: d.arc([ex - r * .18, ey - r * .1, ex + r * .18, ey + r * .15], 200, 340, fill=preto, width=L // 2)
        else:
            d.ellipse([ex - r * .17, ey - r * .26, ex + r * .17, ey + r * .26], fill="white", outline=preto, width=L // 3)
            d.ellipse([ex - r * .12, ey - r * .17, ex + r * .12, ey + r * .24], fill=(42, 109, 244))
            d.ellipse([ex - r * .05, ey - r * .14, ex + r * .03, ey - r * .04], fill="white")
    d.arc([cx - r * .15, hy + r * .5, cx + r * .15, hy + r * .7], 20, 160, fill=preto, width=L // 3)
    return im.resize((tam, tam), Image.LANCZOS)


@ferramenta(risco="arquivo")
def anime2d_sprites(nome: str = "anime2d", quadros: int = 12, tamanho: int = 256, cor_cabelo: str = "#e01b24", cor_roupa: str = "#22263a"):
    """Gera animação 2D estilo anime (Pillow): quadros PNG, sprite sheet e GIF em saidas/anime2d/."""
    d = pasta("anime2d", slug(nome))
    fr = [_quadro(i / quadros, tamanho, cor_cabelo, cor_roupa) for i in range(quadros)]
    for i, f in enumerate(fr): f.save(os.path.join(d, f"quadro_{i:02d}.png"))
    sheet = Image.new("RGBA", (tamanho * quadros, tamanho))
    for i, f in enumerate(fr): sheet.paste(f, (i * tamanho, 0))
    sheet.save(os.path.join(d, "spritesheet.png"))
    fundo = [Image.alpha_composite(Image.new("RGBA", f.size, (255, 236, 210, 255)), f).convert("P", palette=Image.ADAPTIVE) for f in fr]
    fundo[0].save(os.path.join(d, "animacao.gif"), save_all=True, append_images=fundo[1:], duration=80, loop=0, disposal=2)
    return {"ok": True, "pasta": d, "spritesheet": os.path.join(d, "spritesheet.png"), "gif": os.path.join(d, "animacao.gif"), "quadros": quadros}


SVG_PADRAO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><style>
.c{animation:p 1s ease-in-out infinite alternate;transform-origin:100px 190px}@keyframes p{to{transform:translateY(-12px) scaleY(1.03)}}
.o{animation:b 4s infinite}@keyframes b{0%,92%,100%{transform:scaleY(1)}95%{transform:scaleY(.1)}}</style>
<rect width="200" height="200" fill="#ffe9cf"/><g class="c"><rect x="68" y="110" width="64" height="70" rx="26" fill="#22263a" stroke="#111" stroke-width="3"/>
<polygon points="50,70 62,25 80,55 95,10 108,52 128,18 135,58 155,35 150,80" fill="#e01b24" stroke="#111" stroke-width="3"/>
<circle cx="100" cy="85" r="45" fill="#f2c9a0" stroke="#111" stroke-width="3"/><path d="M55 80 Q100 20 145 80 L130 70 L118 82 L100 66 L84 82 L70 70Z" fill="#e01b24" stroke="#111" stroke-width="3"/>
<g class="o" style="transform-origin:100px 95px"><ellipse cx="82" cy="95" rx="8" ry="12" fill="#2a6df4" stroke="#111" stroke-width="2"/><ellipse cx="118" cy="95" rx="8" ry="12" fill="#2a6df4" stroke="#111" stroke-width="2"/></g>
<path d="M92 115 Q100 121 108 115" stroke="#111" stroke-width="3" fill="none"/></g></svg>"""


@ferramenta(risco="arquivo")
def anime2d_svg(descricao: str, nome: str = "svg_anime"):
    """Pede ao LLM um SVG animado (CSS) de um personagem/cena anime; sem LLM usa um modelo pronto."""
    svg = None
    try:
        from ..llm import escolher_provedor
        p = escolher_provedor()
        if p.nome != "regras":
            r = p.pensar([{"papel": "usuario", "texto": f"Crie um único SVG animado com CSS (viewBox 0 0 200 200), estilo anime, de: {descricao}. Responda só o código <svg>...</svg>."}], [])
            m = re.search(r"<svg.*</svg>", r["texto"], re.S); svg = m.group(0) if m else None
    except Exception:
        svg = None
    svg = svg or SVG_PADRAO
    if re.search(r"<script|on\w+=", svg, re.I): svg = SVG_PADRAO        # não aceita JS dentro do SVG gerado
    arq = os.path.join(pasta("anime2d"), slug(nome) + ".svg")
    open(arq, "w", encoding="utf-8").write(svg)
    return {"ok": True, "svg": arq, "fonte": "llm" if svg is not SVG_PADRAO else "modelo"}
