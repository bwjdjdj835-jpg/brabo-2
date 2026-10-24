from PIL import Image, ImageDraw, ImageFont
import sys
F="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"; f=lambda s: ImageFont.truetype(F,s)
im=Image.new("RGB",(512,512),(0,104,181)); d=ImageDraw.Draw(im)
d.rectangle([14,14,497,497],outline=(120,190,255),width=10)
d.text((60,50),"intel",font=f(110),fill="white")
d.text((60,190),"CORE",font=f(70),fill="white"); d.text((300,165),"i5",font=f(130),fill="white")
d.rectangle([0,360,512,512],fill=(0,60,120)); d.text((50,385),"13th GEN",font=f(80),fill="white")
im.save(sys.argv[1])
