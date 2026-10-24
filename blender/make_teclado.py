"""Gera o atlas de legendas do teclado ThinkPad (ABNT2) + layout JSON usado pelo build_scene_v4.py.
Uso: python make_teclado.py  (requer Pillow)"""
import json, os
from PIL import Image, ImageDraw, ImageFont
D = os.path.dirname(os.path.abspath(__file__)); os.makedirs(os.path.join(D, 'tex'), exist_ok=True)
# (legenda, largura em unidades). Linha 0 = teclas de função (meia altura)
LINHAS = [
    [('Esc',1),('F1',1),('F2',1),('F3',1),('F4',1),('F5',1),('F6',1),('F7',1),('F8',1),('F9',1),('F10',1),('F11',1),('F12',1),('Ins',1),('Del',1)],
    [("'\n\"",1),('1\n!',1),('2\n@',1),('3\n#',1),('4\n$',1),('5\n%',1),('6\n¨',1),('7\n&',1),('8\n*',1),('9\n(',1),('0\n)',1),('-\n_',1),('=\n+',1),('⟵',2)],
    [('Tab',1.5),('Q',1),('W',1),('E',1),('R',1),('T',1),('Y',1),('U',1),('I',1),('O',1),('P',1),('´\n`',1),('[\n{',1),('Enter',1.5)],
    [('Caps Lock',1.75),('A',1),('S',1),('D',1),('F',1),('G',1),('H',1),('J',1),('K',1),('L',1),('Ç',1),('~\n^',1),(']\n}',1.25)],
    [('Shift',1.25),('\\\n|',1),('Z',1),('X',1),('C',1),('V',1),('B',1),('N',1),('M',1),(',\n<',1),('.\n>',1),(';\n:',1),('/\n?',1),('Shift',1.75)],
    [('Fn',1),('Ctrl',1.25),('⊞',1),('Alt',1),('',5.25),('Alt Gr',1),('PrtSc',1),('Ctrl',1),('◀',1),('▲▼',1),('▶',1)],
]
U = 128; ALT = [U // 2] + [U] * 5
W = int(15 * U); H = sum(ALT)
img = Image.new('RGB', (W, H), (14, 14, 16)); dr = ImageDraw.Draw(img)
def fonte(px):
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf', 'DejaVuSans.ttf'):
        try: return ImageFont.truetype(f, px)
        except OSError: pass
    return ImageFont.load_default()
layout = []; y = 0
for r, linha in enumerate(LINHAS):
    tot = sum(w for _, w in linha); esc = 15 / tot; x = 0
    for leg, w in linha:
        ww = w * esc * U
        layout.append({'leg': leg, 'r': r, 'x': x / W, 'w': ww / W, 'y': y / H, 'h': ALT[r] / H})
        cx, cy = x + ww / 2, y + ALT[r] / 2
        if '\n' in leg:
            a, b = leg.split('\n'); f = fonte(34)
            dr.text((x + 22, y + ALT[r] * .62), a, fill=(225, 225, 225), font=f, anchor='lm')
            dr.text((x + 22, y + ALT[r] * .3), b, fill=(225, 225, 225), font=f, anchor='lm')
        elif leg:
            f = fonte(46 if len(leg) == 1 else 30 if r else 22)
            dr.text((cx, cy) if len(leg) <= 2 or r == 0 else (x + 18, cy), leg, fill=(230, 230, 230), font=f, anchor='mm' if len(leg) <= 2 or r == 0 else 'lm')
        if leg in ('F', 'J'): dr.line((cx - 12, y + ALT[r] - 26, cx + 12, y + ALT[r] - 26), fill=(200, 200, 200), width=4)
        x += ww
    y += ALT[r]
img.save(os.path.join(D, 'tex', 'teclado.png'))
json.dump(layout, open(os.path.join(D, 'tex', 'teclado.json'), 'w'), ensure_ascii=False)
print(len(layout), 'teclas', img.size)
