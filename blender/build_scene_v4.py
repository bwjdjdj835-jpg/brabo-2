# Jarvis v4 — Quarto do Braga + Ryker (rigado) + ThinkPad + webcam.  Uso: blender -b -P build_scene_v3.py [-- --render]
import bpy, bmesh, math, os, sys, random
import numpy as np
from mathutils import Vector, Matrix
random.seed(7); np.random.seed(7)
D=os.path.dirname(os.path.abspath(__file__)); WEB=os.path.join(D,'..','web','assets'); TEX=os.path.join(D,'tex')
os.makedirs(TEX,exist_ok=True); os.makedirs(WEB,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
S=bpy.context.scene; VL=bpy.context.view_layer

# ---------------- materiais ----------------
def M(name,col,rough=.6,metal=0.,emit=None,es=0.,img=None,spec=.3):
    m=bpy.data.materials.new(name); m.use_nodes=True; nt=m.node_tree; b=nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(*col,1); b.inputs['Roughness'].default_value=rough; b.inputs['Metallic'].default_value=metal
    b.inputs['Specular IOR Level'].default_value=spec
    if img:
        t=nt.nodes.new('ShaderNodeTexImage'); t.image=bpy.data.images.load(img); nt.links.new(t.outputs['Color'],b.inputs['Base Color'])
        if emit=='img': nt.links.new(t.outputs['Color'],b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value=es
    if emit and emit!='img': b.inputs['Emission Color'].default_value=(*emit,1); b.inputs['Emission Strength'].default_value=es
    return m
def salvar_img(nome,arr):
    h,w=arr.shape[:2]; img=bpy.data.images.new(nome,w,h,alpha=False)
    a=np.ones((h,w,4),np.float32); a[...,:3]=arr[::-1]; img.pixels.foreach_set(a.ravel())
    p=os.path.join(TEX,nome+'.png'); img.filepath_raw=p; img.file_format='PNG'; img.save(); bpy.data.images.remove(img); return p
def srgb2lin(c): c=np.asarray(c,np.float32); return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
# piso de cerâmica branca
t=np.ones((512,512,3))*srgb2lin([.86,.85,.82]); t+=np.random.rand(512,512,1)*.03
t[:6]=t[-6:]=t[:,:6]=t[:,-6:]=srgb2lin([.55,.53,.5]); P_PISO=salvar_img('piso',t)
# lençol camuflado
cam=np.zeros((512,512)); 
for k in range(4):
    n=np.random.rand(16*(k+1),16*(k+1)); cam+=np.kron(n,np.ones((512//(16*(k+1))+1,)*2))[:512,:512]*(1/(k+1))
from math import floor
cols=srgb2lin([[.18,.19,.2],[.42,.44,.46],[.68,.7,.72],[.28,.3,.33]]); q=np.digitize(cam,np.quantile(cam,[.25,.5,.75]))
P_CAMO=salvar_img('camuflado',cols[q])
# pôsteres
P_POST=[]
for i,(a,b) in enumerate([([.9,.2,.1],[.05,.05,.1]),([.1,.5,.9],[.0,.0,.05]),([.95,.8,.2],[.3,.05,.05]),([.2,.8,.5],[.02,.05,.1])]):
    y=np.linspace(0,1,256)[:,None,None]; g=srgb2lin(np.array(a))*(1-y)+srgb2lin(np.array(b))*y; g=np.repeat(g,180,1)
    yy,xx=np.mgrid[:256,:180]; m=((xx-90)**2+(yy-110)**2)<(40+i*8)**2; g[m]=g[m]*.3+srgb2lin([.95,.95,.9])*.7*(i%2)
    P_POST.append(salvar_img(f'poster{i}',g))

mParede=M('Parede',(.10,.20,.42),.85); mTeto=M('Teto',(.75,.76,.78),.9)
mPiso=M('Piso',(1,1,1),.25,img=P_PISO); mMadeira=M('MadeiraPorta',(.36,.15,.06),.5)
mMDF=M('MDFEscuro',(.10,.07,.05),.5); mBranco=M('Branco',(.8,.8,.8),.5); mPreto=M('PretoFosco',(.015,.015,.017),.65)
mCortina=M('Cortina',(.03,.04,.06),.9); mVidro=M('VidroNoite',(.02,.04,.09),.1,emit=(.05,.1,.25),es=.6)
mCamo=M('Camuflado',(1,1,1),.9,img=P_CAMO); mTapete=M('Tapete',(.12,.12,.13),1.)
mLuz=M('LuzTeto',(1,1,1),emit=(1,.92,.8),es=12); mAluminio=M('Aluminio',(.6,.6,.62),.3,1.)
mGuarda=M('GuardaRoupa',(.72,.68,.68),.5)
# notebook / webcam
mNote=M('ThinkPadPreto',(.012,.012,.013),.7,spec=.2); mTecla=M('TeclaPreta',(.02,.02,.022),.55)
mTeclaTxt=M('TeclaTexto',(.7,.7,.7),.5); mVermelho=M('VermelhoTP',(.75,.02,.02),.4)
mVidroLente=M('Lente',(.01,.01,.03),.05,.3,spec=1); mLed=M('LedBranco',(1,1,1),emit=(1,1,1),es=4)
mIntel=M('IntelAzul',(.0,.16,.45),.4)
# personagem (prefixo Ryker_ -> toon no navegador)
R_PELE=M('Ryker_Pele',(.42,.2,.11),.55,spec=.2); R_CAB=M('Ryker_Cabelo',(.75,.012,.01),.5)
R_EMB=M('Ryker_Emblema',(.85,.02,.02),.4)
R_ROUPA=M('Ryker_Roupa',(.025,.025,.03),.8,spec=.15); R_ACENTO=M('Ryker_Acento',(.32,.01,.015),.6)
R_LUVA=M('Ryker_Luva',(.035,.035,.04),.5); R_SOLA=M('Ryker_Sola',(.85,.85,.82),.6)
R_TENIS=M('Ryker_Tenis',(.6,.02,.03),.45); R_OLHOB=M('Ryker_OlhoBranco',(.95,.95,.95),.3)
R_IRIS=M('Ryker_Iris',(.12,.05,.03),.2); R_PUPILA=M('Ryker_Pupila',(0,0,0),.2)
R_BRILHO=M('Ryker_Brilho',(1,1,1),emit=(1,1,1),es=2); R_BOCA=M('Ryker_Boca',(.15,.03,.03),.7)
R_LINHA=M('Ryker_Linha',(.04,.02,.02),.7); R_METAL=M('Ryker_Metal',(.6,.6,.6),.3,1.)

# ---------------- helpers ----------------
def link(o,parent=None):
    S.collection.objects.link(o)
    if parent: o.parent=parent
    return o
def caixa(name,size,loc,mat,bev=0.,parent=None,rot=(0,0,0),seg=2):
    me=bpy.data.meshes.new(name); bm=bmesh.new(); bmesh.ops.create_cube(bm,size=1)
    bmesh.ops.scale(bm,vec=size,verts=bm.verts); bm.to_mesh(me); bm.free()
    o=link(bpy.data.objects.new(name,me),parent); o.location=loc; o.rotation_euler=rot; me.materials.append(mat)
    if bev: m=o.modifiers.new('b','BEVEL'); m.width=bev; m.segments=seg; m.limit_method='ANGLE'
    return o
def cil(name,r,h,loc,mat,parent=None,v=32,rot=(0,0,0),r2=None):
    me=bpy.data.meshes.new(name); bm=bmesh.new()
    bmesh.ops.create_cone(bm,cap_ends=True,segments=v,radius1=r,radius2=r if r2 is None else r2,depth=h); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth=len(p.vertices)==4
    o=link(bpy.data.objects.new(name,me),parent); o.location=loc; o.rotation_euler=rot; me.materials.append(mat); return o
def esf(name,r,loc,mat,scale=(1,1,1),parent=None,seg=24,rings=12):
    me=bpy.data.meshes.new(name); bm=bmesh.new(); bmesh.ops.create_uvsphere(bm,u_segments=seg,v_segments=rings,radius=r)
    bmesh.ops.scale(bm,vec=scale,verts=bm.verts); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth=True
    o=link(bpy.data.objects.new(name,me),parent); o.location=loc; me.materials.append(mat); return o
def plano(name,w,h,loc,rot,mat,rep=(1,1),parent=None):
    me=bpy.data.meshes.new(name); me.from_pydata([(-w/2,-h/2,0),(w/2,-h/2,0),(w/2,h/2,0),(-w/2,h/2,0)],[],[(0,1,2,3)])
    uv=me.uv_layers.new(); 
    for i,c in enumerate([(0,0),(rep[0],0),(rep[0],rep[1]),(0,rep[1])]): uv.data[i].uv=c
    o=link(bpy.data.objects.new(name,me),parent); o.location=loc; o.rotation_euler=rot; me.materials.append(mat); return o
def texto(name,s,size,loc,rot,mat,parent=None,ext=0.0005,align='CENTER',font_bold=False):
    cu=bpy.data.curves.new(name,'FONT'); cu.body=s; cu.size=size; cu.extrude=ext; cu.align_x=align; cu.align_y='CENTER'
    o=bpy.data.objects.new(name+'_tmp',cu); S.collection.objects.link(o); o.data.materials.append(mat)
    VL.objects.active=o; o.select_set(True); bpy.ops.object.convert(target='MESH'); o.select_set(False); o.name=name
    o.location=loc; o.rotation_euler=rot
    if parent: o.parent=parent
    return o
def juntar(objs,name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    VL.objects.active=objs[0]; bpy.ops.object.join(); objs[0].name=name; return objs[0]
def aplicar(o):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); VL.objects.active=o
    for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)

# ---------------- QUARTO 3,5 x 3,0 x 2,6 ----------------
W,L,H=3.5,3.0,2.6; x0,x1,y0,y1=-W/2,W/2,-L/2,L/2
plano('Piso',W,L,(0,0,0),(0,0,0),mPiso,(W/.5,L/.5))
plano('Teto',W,L,(0,0,H),(math.pi,0,0),mTeto)
plano('ParedeFundo',W,H,(0,y1,H/2),(math.pi/2,0,math.pi),mParede)   # normal -> -Y (para dentro)
plano('ParedeFrente',W,H,(0,y0,H/2),(math.pi/2,0,0),mParede)
plano('ParedeEsq',L,H,(x0,0,H/2),(math.pi/2,0,-math.pi/2),mParede)
plano('ParedeDir',L,H,(x1,0,H/2),(math.pi/2,0,math.pi/2),mParede)
for nm,ln,lc,rz in [('RodapeF',W,(0,y1-.006,.04),0),('RodapeT',W,(0,y0+.006,.04),0),('RodapeE',L,(x0+.006,0,.04),math.pi/2),('RodapeD',L,(x1-.006,0,.04),math.pi/2)]:
    caixa(nm,(ln,.012,.08),lc,mBranco,rot=(0,0,rz))
# luz de teto
cil('Plafon',.16,.04,(0,0,H-.02),mBranco,v=48); cil('PlafonLuz',.13,.01,(0,0,H-.045),mLuz,v=48)
# janela no fundo (sobre a cama) com grade e cortinas escuras
JX=.85
caixa('JanelaMoldura',(1.0,.06,1.0),(JX,y1-.02,1.5),mAluminio,.005)
plano('JanelaVidro',.92,.92,(JX,y1-.055,1.5),(math.pi/2,0,math.pi),mVidro)
for i in range(7): caixa('Grade',(.012,.012,.92),(JX-.39+i*.13,y1-.07,1.5),mBranco)
for i in range(6): caixa('GradeH',(.92,.012,.012),(JX,y1-.07,1.1+i*.16),mBranco)
cil('VaraCortina',.012,1.7,(JX,y1-.13,2.12),mPreto,rot=(0,math.pi/2,0))
for s in (-1,1):
    me=bpy.data.meshes.new('Cortina'); vs=[];fs=[]; nx,nz=16,2
    for j in range(nz):
        for i in range(nx): vs.append((i*.024,.025*math.sin(i*1.4),-j*1.9))
    for i in range(nx-1): fs.append((i,i+1,nx+i+1,nx+i))
    me.from_pydata(vs,[],fs); o=link(bpy.data.objects.new('Cortina',me)); me.materials.append(mCortina)
    o.location=(JX+s*.62-.18,y1-.14,2.1); o.modifiers.new('s','SOLIDIFY').thickness=.01
# porta de madeira (frente, esquerda)
PX=-1.15
caixa('PortaBatente',(.92,.06,2.12),(PX,y0+.02,1.06),mBranco,.004)
caixa('Porta',(.82,.04,2.05),(PX,y0+.04,1.03),mMadeira,.004)
for z in (.6,1.5): caixa('PortaPainel',(.6,.01,.6 if z<1 else .8),(PX,y0+.062,z),mMadeira,.01)
cil('Macaneta',.022,.06,(PX+.32,y0+.09,1.0),mAluminio,rot=(math.pi/2,0,0))
# cama de solteiro (direita, cabeceira na parede do fundo)
BX,BW,BL=1.22,.95,2.0; by1=y1-.02; bc=by1-BL/2
caixa('CamaEstrutura',(BW,BL,.3),(BX,bc,.17),mMDF,.01)
caixa('Colchao',(BW-.04,BL-.04,.18),(BX,bc,.41),mCamo,.03,seg=3)
caixa('Cabeceira',(BW,.04,.75),(BX,by1-.01,.4),mMDF,.01)
caixa('Travesseiro',(.6,.35,.12),(BX,by1-.27,.55),mCamo,.05,seg=4)
caixa('Edredom',(BW,1.2,.06),(BX,bc-.35,.52),mCamo,.03,seg=3)
# guarda-roupa (canto frente-direita) e cômoda (parede esquerda)
caixa('GuardaRoupa',(.55,.6,2.0),(x1-.3,y0+.33,1.0),mGuarda,.01)
caixa('GuardaRoupaPorta',(.01,.28,1.85),(x1-.578,y0+.33-.145,1.02),mPreto); caixa('GuardaRoupaPorta2',(.01,.28,1.85),(x1-.578,y0+.33+.145,1.02),mGuarda)
caixa('Comoda',(.45,.8,.8),(x0+.24,-.35,.4),mMDF,.01)
for i in range(3): caixa('Gaveta',(.01,.72,.22),(x0+.47,-.35,.15+i*.25),mMDF,.003); cil('Puxador',.012,.03,(x0+.48,-.35,.2+i*.25),mAluminio,rot=(0,math.pi/2,0))
cil('Abajur',.06,.25,(x0+.24,-.55,.93),mBranco,r2=.04); 
# ventilador de coluna (ao lado da mesa)
FX,FY=-.15,y1-.3
cil('VentBase',.16,.03,(FX,FY,.015),mPreto); cil('VentHaste',.015,1.0,(FX,FY,.52),mPreto)
cil('VentMotor',.06,.1,(FX,FY-.03,1.05),mPreto,rot=(math.pi/2,0,0))
cil('VentGrade',.2,.08,(FX,FY-.1,1.05),mPreto,v=48,rot=(math.pi/2,0,0)).modifiers.new('w','WIREFRAME').thickness=.004
# tapete
caixa('Tapete',(1.4,1.0,.01),(0.0,-.45,.005),mTapete,.004)
# prateleiras acima da mesa com livros e enfeites
for k,z in enumerate((1.45,1.8)):
    caixa('Prateleira',(.9,.22,.025),(-1.05,y1-.12,z),mMDF,.004)
    for j in range(6):
        c=[(.5,.05,.05),(.05,.1,.3),(.6,.55,.5),(.05,.25,.1),(.2,.2,.2),(.5,.3,.05)][(j+k)%6]
        caixa('Livro',(.035,.16,.18+.03*(j%3)),(-1.4+j*.045+k*.4,y1-.13,z+.105+.015*(j%3)),M('Livro',c,.7),.003)
# pôsteres
for i,(p,loc,rot) in enumerate([(P_POST[0],(-1.6+.0,y1-.005,1.95),(math.pi/2,0,math.pi)),(P_POST[1],(-.45,y1-.005,1.95),(math.pi/2,0,math.pi)),
                                  (P_POST[2],(x1-.005,.2,1.6),(math.pi/2,0,math.pi/2)),(P_POST[3],(x0+.005,-.4,1.55),(math.pi/2,0,-math.pi/2))]):
    plano('Poster',.32,.45,loc,rot,M('Poster',(1,1,1),.6,img=p))

# ---------------- MESA + CADEIRA ----------------
CX=-1.0   # x do personagem/mesa
caixa('MesaTampo',(1.2,.6,.03),(CX,y1-.3,.735),mMDF,.003)
for dx in (-.57,.57):
    for dy in (-.27,.27): caixa('MesaPerna',(.035,.035,.72),(CX+dx,y1-.3+dy,.36),mPreto,.003)
caixa('MesaGaveteiro',(.35,.5,.25),(CX+.38,y1-.3,.6),mMDF,.003)
cad=bpy.data.objects.new('Cadeira',None); link(cad); cad.location=(CX,.38,0)
caixa('CadAssento',(.48,.46,.07),(0,0,.45),mPreto,.03,cad,seg=3)
caixa('CadEncosto',(.46,.06,.6),(0,-.27,.85),mPreto,.03,cad,rot=(math.radians(-8),0,0),seg=3)
#caixa('CadEncostoV',(.06,.065,.25),(0,-.29,.85),mVermelho,.01,cad,rot=(math.radians(-8),0,0))
cil('CadPistao',.025,.35,(0,0,.24),mAluminio,cad)
for k in range(5):
    a=k*2*math.pi/5; caixa('CadPe',(.28,.035,.03),(.14*math.cos(a),.14*math.sin(a),.06),mPreto,.008,cad,rot=(0,0,a))
    esf('CadRoda',.025,(.28*math.cos(a),.28*math.sin(a),.025),mPreto,parent=cad)
# mouse + mousepad
caixa('Mousepad',(.25,.2,.003),(CX+.33,1.0,.752),mPreto,.002); esf('Mouse',.03,(CX+.33,.98,.765),mPreto,(1,1.6,.5))

# ---------------- NOTEBOOK LENOVO THINKPAD 15,6" (realista, PBR) ----------------
import json
mCorpoTP=M('TP_Corpo',(.016,.016,.018),.58,spec=.35)          # plástico soft-touch
mCorpoTP.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value=.08
mTampaTP=M('TP_Tampa',(.013,.013,.015),.5,spec=.4); mTampaTP.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value=.15
mMolduraTP=M('TP_Moldura',(.012,.012,.013),.72,spec=.25)
mPocoTP=M('TP_PocoTeclado',(.008,.008,.009),.8,spec=.2)
mTecTP=M('TP_Teclas',(1,1,1),.42,img=os.path.join(TEX,'teclado.png'),spec=.4)
mTouchTP=M('TP_Touchpad',(.02,.02,.022),.68,spec=.3); mBotTP=M('TP_Botoes',(.018,.018,.02),.45)
mVermTP=M('TP_Vermelho',(.62,.01,.015),.55); mBorrTP=M('TP_Borracha',(.01,.01,.01),.9,spec=.1)
mLogoTP=M('TP_Logo',(.62,.62,.64),.35,.6); mVidroCam=M('TP_VidroCam',(.0,.0,.0),.05,spec=1.)
mPortaTP=M('TP_Porta',(.0,.0,.0),.9); mUSB=M('TP_USBAzul',(.0,.12,.55),.4); mDobTP=M('TP_Dobradica',(.03,.03,.032),.35,.5)
mIntelTP=M('TP_SeloIntel',(.02,.2,.55),.25,spec=.6); mLedTP=M('TP_Led',(1,1,1),emit=(.3,1,.4),es=3)
note=bpy.data.objects.new('Notebook',None); link(note); note.location=(CX,1.08,.75)
NW,ND,NH=.377,.250,.026
caixa('NoteBase',(NW,ND,NH),(0,0,NH/2),mCorpoTP,.0045,note,seg=4)
for x in (-1,1):
    for y in (-1,1): cil('Pe',.006,.002,(x*.16,y*.1,-.001),mBorrTP,note,16)
# poço do teclado (levemente rebaixado)
KW,KD=.300,.108; KY=.052
caixa('PocoTeclado',(KW+.008,KD+.008,.0012),(0,KY,NH-.0002),mPocoTP,.0015,note)
lay=json.load(open(os.path.join(TEX,'teclado.json'),encoding='utf-8'))
teclas=[]; GAP=.0028
for k in lay:
    w=k['w']*KW-GAP; h=k['h']*KD-GAP
    cx=-KW/2+(k['x']+k['w']/2)*KW; cy=KY+KD/2-(k['y']+k['h']/2)*KD
    me=bpy.data.meshes.new('Tecla'); bm=bmesh.new(); bmesh.ops.create_cube(bm,size=1)
    bmesh.ops.scale(bm,vec=(w,h,.0028),verts=bm.verts)
    uvl=bm.loops.layers.uv.new()
    for f in bm.faces:
        for l in f.loops:
            lx,ly=l.vert.co.x,l.vert.co.y
            l[uvl].uv=(k['x']+(lx/w+.5)*k['w'], 1-(k['y']+(.5-ly/h)*k['h']))
    bm.to_mesh(me); bm.free(); o=link(bpy.data.objects.new('Tecla',me),note); me.materials.append(mTecTP)
    o.location=(cx,cy,NH+.0012); bv=o.modifiers.new('b','BEVEL'); bv.width=.0009; bv.segments=2
    teclas.append(o)
for o in teclas:
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); VL.objects.active=o; bpy.ops.object.modifier_apply(modifier='b')
tecl=juntar(teclas,'Teclado')
# TrackPoint vermelho entre G, H e B
pos={k['leg']:k for k in lay}; g=pos['G']
tpx=-KW/2+(g['x']+g['w'])*KW; tpy=KY+KD/2-(g['y']+g['h'])*KD
cil('TrackPoint',.0034,.0075,(tpx,tpy,NH+.0035),mVermTP,note,20); esf('TrackPointTopo',.0034,(tpx,tpy,NH+.0072),mVermTP,(1,1,.35),note)
# botões do TrackPoint (3) com listras vermelhas e touchpad
BY=-.0135
for i in (-1,0,1): caixa('BotaoTP',(.03 if i==0 else .033,.012,.0016),(i*.0335,BY,NH+.0006),mBotTP,.0012,note)
for i in (-1,1): caixa('ListraTP',(.0016,.012,.0018),(i*.0165,BY,NH+.0008),mVermTP,0,note)
caixa('ListraTP2',(.1,.0012,.0017),(0,BY-.0066,NH+.0007),mVermTP,0,note)
caixa('Touchpad',(.092,.056,.0008),(0,-.055,NH+.0001),mTouchTP,.002,note)
# logos / adesivos / LEDs / botão power
texto('LogoThinkPadBase','ThinkPad',.0105,(.112,-.107,NH+.0002),(0,0,0),mLogoTP,note,align='LEFT')
cil('PingoI',.0011,.0006,(.1205,-.1028,NH+.0006),mVermTP,note,12)
caixa('SeloIntel',(.02,.024,.0003),(-.15,-.098,NH+.0002),mIntelTP,.001,note)
texto('SeloIntelTxt','intel\nCORE i5',.0038,(-.15,-.098,NH+.0005),(0,0,0),mBranco,note)
caixa('Power',(.012,.006,.0015),(.165,.112,NH+.0006),mBotTP,.001,note); esf('LedPower',.0012,(.177,.112,NH+.0006),mLedTP,parent=note)
for i in range(3): esf('Led',.0009,(-.16+i*.006,.112,NH+.0004),mLedTP,parent=note)
# portas laterais (esq.: energia, VGA, rede, USB 3.0 azul; dir.: USB, áudio, Kensington)
for i,(w,mat) in enumerate([(.008,mPortaTP),(.016,mPortaTP),(.013,mPortaTP),(.013,mUSB),(.013,mUSB),(.022,mPortaTP)]):
    caixa('PortaE',(.0015,w,.006),(-NW/2-.0003,.07-i*.028,NH*.5),mat,0,note)
for i,(w,mat) in enumerate([(.013,mPortaTP),(.013,mPortaTP),(.006,mPortaTP),(.008,mPortaTP)]):
    caixa('PortaD',(.0015,w,.006),(NW/2+.0003,.05-i*.03,NH*.5),mat,0,note)
# tampa
tampa=bpy.data.objects.new('Tampa',None); link(tampa,note); tampa.location=(0,ND/2-.008,NH-.002); tampa.rotation_euler=(math.radians(-17),0,0)
LH,LT=.234,.0075
caixa('TampaTraseira',(NW,LT,LH),(0,LT/2,LH/2),mTampaTP,.004,tampa,seg=4)
caixa('Moldura',(NW-.006,.0012,LH-.006),(0,-.0004,LH/2),mMolduraTP,.0015,tampa)
SW,SH=.3445,.1938; SZ=.022+SH/2
caixa('BordaTela',(SW+.003,.0006,SH+.003),(0,-.0012,SZ),mPocoTP,0,tampa)
texto('LogoLenovoMoldura','Lenovo',.0085,(-.15,-.0016,.011),(math.pi/2,0,0),mLogoTP,tampa,align='LEFT')
texto('LogoThinkPadMoldura','ThinkPad',.0075,(.15,-.0016,.011),(math.pi/2,0,0),mLogoTP,tampa,align='RIGHT')
cil('CamNote',.0024,.0008,(0,-.0014,LH-.0075),mVidroCam,tampa,20,(math.pi/2,0,0))
cil('CamNoteAro',.0034,.0006,(0,-.0012,LH-.0075),mBorrTP,tampa,20,(math.pi/2,0,0))
for x in (-.17,.17):
    for z in (.008,LH-.008): esf('Batente',.0018,(x,-.0014,z),mBorrTP,(1,.5,1),tampa)
texto('LogoThinkPadTampa','ThinkPad',.026,(.115,LT+.0006,.045),(math.pi/2,math.radians(30),math.pi),mLogoTP,tampa)
esf('LedTampa',.0016,(.1,LT+.0008,.034),mVermTP,parent=tampa)
texto('LogoLenovoTampa','lenovo',.022,(-.115,LT+.0006,LH-.03),(math.pi/2,0,math.pi),mLogoTP,tampa)
for d in (-1,1): cil('Dobradica',.0075,.05,(d*.13,ND/2-.008,NH-.002),mDobTP,note,20,(0,math.pi/2,0))
mt=M('TelaAoVivo',(1,1,1),.2,emit='img',es=1.0,img=os.environ.get('TELA_IMG',os.path.join(D,'tela_preview.png')))
o=plano('Tela',SW,SH,(0,-.0016,SZ),(math.pi/2,0,0),mt,parent=tampa)

# ---------------- WEBCAM 1080p (estilo Logitech) no mini tripé, ~50 cm do rosto ----------------
wc=bpy.data.objects.new('Webcam',None); link(wc); wc.location=(CX+.13,1.40,.75)
for k in range(3):
    a=k*2*math.pi/3+.5; cil('TripePerna',.004,.17,(.05*math.cos(a),.05*math.sin(a),.075),mPreto,wc,8,(math.cos(a+math.pi/2)*.6,math.sin(a+math.pi/2)*.6,0)) 
cil('TripeHaste',.006,.28,(0,0,.28),mPreto,wc,12)
cab_cam=bpy.data.objects.new('WebcamCorpo',None); link(cab_cam,wc); cab_cam.location=(0,0,.45)
# orientada para o rosto do Ryker
alvo=Vector((CX,.55,1.25)); dirc=(alvo-(wc.location+Vector((0,0,.45)))).normalized()
cab_cam.rotation_euler=dirc.to_track_quat('-Y','Z').to_euler()
caixa('WebcamClip',(.04,.03,.025),(0,.0,-.025),mPreto,.004,cab_cam)
caixa('WebcamCaixa',(.092,.031,.031),(0,0,0),mNote,.012,cab_cam,seg=4)
cil('WebcamAro',.0115,.004,(0,-.0165,0),mAluminio,cab_cam,32,(math.pi/2,0,0))
cil('WebcamLente',.009,.004,(0,-.0175,0),mVidroLente,cab_cam,32,(math.pi/2,0,0))
esf('WebcamLed',.0018,(-.028,-.016,.004),mLed,parent=cab_cam)
texto('WebcamLogi','logi',.008,(.03,-.0158,-.002),(math.pi/2,0,0),mTeclaTxt,cab_cam)
texto('WebcamHD','HD 1080p',.0035,(-.03,-.0158,-.004),(math.pi/2,0,0),mTeclaTxt,cab_cam)
wc_ref=bpy.data.objects.new('WebcamOlho',None); link(wc_ref,cab_cam); wc_ref.location=(0,-.03,0)   # ponto de vista do LIVE

# ---------------- RYKER (corpo Skin -> malha, armadura, pesos automáticos) ----------------
P={}; RAD={}; E=[]
def n(k,p,r): P[k]=Vector(p); RAD[k]=r if isinstance(r,tuple) else (r,r)
n('pelvis',(0,.40,.56),(.15,.11)); n('cintura',(0,.42,.74),(.125,.09)); n('peito',(0,.44,.95),(.165,.105)); n('peito2',(0,.45,1.06),(.15,.095))
n('pesc',(0,.47,1.13),.05); n('pesc2',(0,.49,1.2),.045)
for s,L in ((-1,'L'),(1,'R')):
    n('quad'+L,(s*.095,.42,.53),.09); n('coxa'+L,(s*.105,.64,.54),.083); n('joel'+L,(s*.11,.86,.54),.064)
    n('canela'+L,(s*.11,.89,.32),.06); n('torn'+L,(s*.11,.92,.11),.05); n('calc'+L,(s*.11,.89,.05),(.048,.04)); n('pe'+L,(s*.11,1.07,.04),(.05,.033))
    n('ombro'+L,(s*.19,.45,1.075),.063); n('delt'+L,(s*.215,.53,.98),.056); n('cot'+L,(s*.24,.63,.86),.043)
    n('ante'+L,(s*.2,.78,.83),.042); n('pulso'+L,(s*.155,.92,.81),.033); n('mao'+L,(s*.135,1.0,.80),(.042,.02))
    for f in range(4):
        fx=s*(.115+f*.014) if s>0 else s*(.115+f*.014)
        n(f'dedo{f}{L}',(fx,1.035,.795),.011); n(f'ponta{f}{L}',(fx,1.07,.778-.002*abs(f-1.5)),.009)
        E+= [('mao'+L,f'dedo{f}{L}'),(f'dedo{f}{L}',f'ponta{f}{L}')]
    n('pol'+L,(s*.11,.97,.795),.013); n('polp'+L,(s*.095,1.01,.785),.01)
    E+=[('pelvis','quad'+L),('quad'+L,'coxa'+L),('coxa'+L,'joel'+L),('joel'+L,'canela'+L),('canela'+L,'torn'+L),('torn'+L,'calc'+L),('calc'+L,'pe'+L),
        ('peito2','ombro'+L),('ombro'+L,'delt'+L),('delt'+L,'cot'+L),('cot'+L,'ante'+L),('ante'+L,'pulso'+L),('pulso'+L,'mao'+L),('pulso'+L,'pol'+L),('pol'+L,'polp'+L)]
E+=[('pelvis','cintura'),('cintura','peito'),('peito','peito2'),('peito2','pesc'),('pesc','pesc2')]
ks=list(P); me=bpy.data.meshes.new('RykerCorpo'); me.from_pydata([P[k] for k in ks],[(ks.index(a),ks.index(b)) for a,b in E],[])
corpo=link(bpy.data.objects.new('Ryker_Corpo',me)); corpo.modifiers.new('skin','SKIN').use_smooth_shade=True
for i,k in enumerate(ks): me.skin_vertices[0].data[i].radius=RAD[k]
me.skin_vertices[0].data[ks.index('pelvis')].use_root=True
corpo.modifiers.new('sub','SUBSURF').levels=2
aplicar(corpo)
for m in (R_ROUPA,R_PELE,R_LUVA,R_ACENTO,R_TENIS,R_SOLA): corpo.data.materials.append(m)
ROUPA,PELE,LUVA,ACENTO,TENIS,SOLA=range(6)
# acessórios do moletom (fixos no osso Peito)
def sup(x,z,y0=.9):
    ok,loc,nr,_=corpo.ray_cast(Vector((x,y0,z)),Vector((0,-1,0)))
    return loc,nr
pecas_peito=[]
lz=[]
for z in np.linspace(.68,1.12,12):
    l,_=sup(0,z); lz.append(l)
for i in range(len(lz)-1):
    a,b=lz[i],lz[i+1]; m=(a+b)/2; o=cil('Ziper',.004,(b-a).length+.002,m+Vector((0,.003,0)),R_METAL,v=8)
    o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler(); pecas_peito.append(o)
    for s in (-1,1):
        o2=cil('Friso',.0025,(b-a).length+.002,m+Vector((s*.012,.002,0)),R_ACENTO,v=6); o2.rotation_euler=o.rotation_euler; pecas_peito.append(o2)
l,nr=sup(.075,1.0); em=bpy.data.objects.new('Emblema',None)
o=texto('Ryker_EmblemaR','R',.05,l+Vector((0,.007,0)),(math.pi/2,0,math.pi),R_EMB)
o.rotation_euler=nr.to_track_quat('Z','Y').to_euler(); bpy.ops.object.select_all(action='DESELECT'); pecas_peito.append(o)
# capuz
cap=esf('Ryker_Capuz',.1,(0,.375,1.1),R_ROUPA,(1.1,.5,.55),seg=32,rings=16); pecas_peito.append(cap)
for s in (-1,1):
    o=cil('Cordao',.003,.13,(s*.04,.565,1.02),R_ACENTO,v=6,rot=(math.radians(10),0,0)); pecas_peito.append(o)
# cinto
cint=cil('Ryker_Cinto',.128,.035,(0,.415,.64),R_LUVA,v=40); cint.scale=(1,.75,1); pecas_peito.append(cint)
l,_=sup(0,.64); caixa('Fivela',(.04,.008,.03),l+Vector((0,.006,0)),R_METAL,.002); pecas_peito.append(S.objects['Fivela'])

# ---------------- CABEÇA anime (shape keys Fala, Piscar) ----------------
HC=Vector((0,.50,1.30))
cabeca=esf('Ryker_Cabeca',.1,HC,R_PELE,seg=48,rings=32)
for v in cabeca.data.vertices:
    x,y,z=v.co; z*=1.12; x*=.86; y*=.95
    if z<0:  # mandíbula/queixo anime
        t=min(1,-z/.11); x*=1-.45*t*t; y=y*(1-.25*t) + .028*t*(1 if y>0 else 0)
        if y<0: y*=1-.2*t
    if y>0 and z>-0.02: y*=.93      # face mais plana
    v.co=(x,y,z)
VL.update()
bmx=cabeca.matrix_world
def face_pt(x,z):
    o=HC+Vector((x,.3,z)); ok,loc,nr,_=cabeca.ray_cast(o-HC,Vector((0,-1,0))); return loc+HC,nr
# chave de forma "Fala": queixo desce
cabeca.shape_key_add(name='Basis'); kf=cabeca.shape_key_add(name='Fala')
MZ=-.045
for i,v in enumerate(cabeca.data.vertices):
    x,y,z=v.co
    if z<MZ+.005 and y>-.03:
        w=min(1,(MZ+.005-z)/.04)*min(1,(y+.03)/.06); kf.data[i].co=(x,y-.004*w,z-.016*w)
# nariz, orelhas
l,nr=face_pt(0,-.015); nar=cil('Ryker_Nariz',.008,.022,l+Vector((0,.006,0)),R_PELE,v=8,r2=.001); nar.rotation_euler=(math.radians(-60),0,0)
for s in (-1,1): esf('Ryker_Orelha',.022,HC+Vector((s*.083,-.01,0)),R_PELE,(.35,.8,1.15))
# olhos (objeto único com chave Piscar)
olhos=[]
for s in (-1,1):
    l,nr=face_pt(s*.036,.008); rot=nr.to_track_quat('Z','Y').to_euler()
    for nm,r,sc,mat,off in [('Branco',.019,(1.15,1.0,.12),R_OLHOB,.001),('Iris',.0125,(.95,1.25,.12),R_IRIS,.0025),('Pupila',.006,(.9,1.3,.12),R_PUPILA,.0033),
                             ('Brilho',.0035,(1,1,.12),R_BRILHO,.0038),('Cilio',.02,(1.25,.18,.15),R_LINHA,.0028)]:
        o=esf('Olho'+nm,r,(0,0,0),mat,sc,seg=24,rings=10)
        dy=.011 if nm=='Cilio' else (.006 if nm=='Brilho' else -.001 if nm in('Iris','Pupila') else 0)
        dx=-s*.004 if nm=='Brilho' else 0
        o.matrix_world=Matrix.Translation(l+nr*off)@rot.to_matrix().to_4x4()@Matrix.Translation((dx,dy,0))
        olhos.append(o)
    # sobrancelha (cor do cabelo, inclinada = olhar determinado)
    lb,nb=face_pt(s*.038,.035); o=esf('Sobr',.022,(0,0,0),R_CAB,(1.1,.13,.15))
    o.matrix_world=Matrix.Translation(lb+nb*.002)@nb.to_track_quat('Z','Y').to_matrix().to_4x4()@Matrix.Rotation(-s*.18,4,'Z'); olhos.append(o)
VL.update()
for o in olhos:
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); VL.objects.active=o; bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
olhos_o=juntar(olhos,'Ryker_Olhos')
olhos_o.shape_key_add(name='Basis'); kp=olhos_o.shape_key_add(name='Piscar')
ztop=HC.z+.008+.02
for i,v in enumerate(olhos_o.data.vertices):
    if abs(v.co.z-(HC.z+.008))<.03 and v.co.z< HC.z+.03: kp.data[i].co.z = HC.z+.003 + (v.co.z-(HC.z+.008))*.08
# boca
l,nr=face_pt(0,MZ); boca=esf('Ryker_Boca',.012,l+nr*.0015,R_BOCA,(1,.25,.12),seg=16,rings=8)
boca.rotation_euler=nr.to_track_quat('Y','Z').to_euler(); boca.rotation_euler=(0,0,0); 
boca.shape_key_add(name='Basis'); kb=boca.shape_key_add(name='Fala')
for v in kb.data: v.co.z*=1.0; 
for i,v in enumerate(boca.data.vertices): kb.data[i].co=(v.co.x*.75,v.co.y,v.co.z*5.5 - .006)
# ---------------- CABELO espetado vermelho ----------------
mech=[]
capa=esf('CabeloCapa',.104,HC+Vector((0,-.006,.012)),R_CAB,(.9,.98,1.1),seg=32,rings=16)
bm=bmesh.new(); bm.from_mesh(capa.data)
bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.co.z< -.02 or (v.co.y>.04 and v.co.z<.055)],context='VERTS'); bm.to_mesh(capa.data); bm.free()
capa.modifiers.new('s','SOLIDIFY').thickness=.003; mech.append(capa)
def mecha(base,dirv,comp,r):
    o=cil('Mecha',r,comp,(0,0,0),R_CAB,v=6,r2=.0008); dirv=dirv.normalized()
    o.matrix_world=Matrix.Translation(base+dirv*comp/2)@dirv.to_track_quat('Z','Y').to_matrix().to_4x4(); mech.append(o)
for i in range(95):
    u=random.uniform(0,2*math.pi); w=random.uniform(.15,1.)   # w: altura na esfera
    d=Vector((math.cos(u)*math.sqrt(1-w*w)*.9,math.sin(u)*math.sqrt(1-w*w),w*1.1)).normalized()
    if d.y>.45 and d.z<.6: continue
    base=HC+Vector((d.x*.09,d.y*.09-.006,d.z*.1+.012))
    out=(d+Vector((0,-.25,.55))+Vector((random.uniform(-.3,.3),random.uniform(-.3,.3),0))).normalized()
    mecha(base,out,random.uniform(.07,.12),random.uniform(.018,.027))
for i in range(13):   # franja sobre a testa
    x=-.066+i*.011; base=HC+Vector((x,.068,.082+random.uniform(-.006,.006)))
    mecha(base,Vector((x*2.5+random.uniform(-.1,.1),.55,-1)),random.uniform(.055,.085),.014)
for s in (-1,1):     # costeletas
    mecha(HC+Vector((s*.075,.03,.03)),Vector((s*.15,.25,-1)),.06,.012)
for o in mech:
    VL.update(); bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); VL.objects.active=o; bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
aplicar(capa); cabelo=juntar(mech,'Ryker_Cabelo')
for p in cabelo.data.polygons: p.use_smooth=False

# ---------------- ARMADURA ----------------
ad=bpy.data.armatures.new('RykerRig'); rig=link(bpy.data.objects.new('Ryker',ad)); VL.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
def osso(nm,h,t,pai=None,conn=False):
    b=ad.edit_bones.new(nm); b.head=h; b.tail=t; b.roll=0
    if pai: b.parent=ad.edit_bones[pai]; b.use_connect=conn
    return b
osso('Hips',P['pelvis'],P['cintura']); osso('Spine',P['cintura'],P['peito'],'Hips',True); osso('Chest',P['peito'],P['pesc'],'Spine',True)
osso('Neck',P['pesc'],P['pesc2'],'Chest',True); osso('Head',P['pesc2'],P['pesc2']+Vector((0,0,.2)),'Neck',True)
for L in 'LR':
    osso('Shoulder_'+L,P['peito2']+Vector((P['ombro'+L].x*.25,0,0)),P['ombro'+L],'Chest')
    osso('UpperArm_'+L,P['ombro'+L],P['cot'+L],'Shoulder_'+L,True); osso('ForeArm_'+L,P['cot'+L],P['pulso'+L],'UpperArm_'+L,True)
    osso('Hand_'+L,P['pulso'+L],P['mao'+L],'ForeArm_'+L,True); osso('Fingers_'+L,P['mao'+L],(P['ponta1'+L]+P['ponta2'+L])/2,'Hand_'+L,True)
    osso('Thumb_'+L,P['pol'+L],P['polp'+L],'Hand_'+L)
    osso('Thigh_'+L,P['quad'+L],P['joel'+L],'Hips'); osso('Shin_'+L,P['joel'+L],P['torn'+L],'Thigh_'+L,True); osso('Foot_'+L,P['torn'+L],P['pe'+L],'Shin_'+L,True)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT'); corpo.select_set(True); rig.select_set(True); VL.objects.active=rig
bpy.ops.object.parent_set(type='ARMATURE_AUTO')
VL.update()
# materiais por osso dominante (pesos automáticos)
gn={g.index:g.name for g in corpo.vertex_groups}
bn={b.name:b for b in ad.bones}
for poly in corpo.data.polygons:
    acc={}
    for vi in poly.vertices:
        for g in corpo.data.vertices[vi].groups: acc[gn[g.group]]=acc.get(gn[g.group],0)+g.weight
    bone=max(acc,key=acc.get) if acc else 'Chest'; c=poly.center; nrm=poly.normal; mi=ROUPA
    B=bn[bone]; hb,tb=B.head_local,B.tail_local; t=(c-hb).dot(tb-hb)/(tb-hb).length_squared
    side=1 if c.x>0 else -1
    if bone.startswith(('Thigh','Shin')) or (bone=='Hips' and c.z<.6):
        mi=ACENTO if (nrm.x*side>.82 and (bone!='Hips')) else ROUPA
    elif bone.startswith('Foot') or (bone.startswith('Shin') and c.z<.09):
        mi=SOLA if c.z<.03 else TENIS
    elif bone in ('Neck','Head'): mi=PELE
    elif bone.startswith('UpperArm'): mi=ROUPA if t<.12 else PELE
    elif bone.startswith('ForeArm'): mi=PELE if t<.8 else LUVA
    elif bone.startswith(('Hand','Thumb')): mi=LUVA
    elif bone.startswith('Fingers'): mi=LUVA if t<.45 else PELE
    if bone.startswith('Shin') and c.z<.13: mi=TENIS if c.z>.03 else SOLA
    poly.material_index=mi
def prender(o,bone):
    mw=o.matrix_world.copy(); o.parent=rig; o.parent_type='BONE'; o.parent_bone=bone; VL.update(); o.matrix_world=mw
for o in [cabeca,olhos_o,boca,cabelo,nar]+[x for x in S.objects if x.name.startswith('Ryker_Orelha')]: prender(o,'Head')
for o in pecas_peito:
    prender(o,'Hips' if o.name.startswith(('Ryker_Cinto','Fivela')) else 'Chest')
rig.location=(CX,0,0)

# ---------------- LUZES / CÂMERAS (só render) ----------------
Wd=S.world=bpy.data.worlds.new('W'); Wd.use_nodes=True; Wd.node_tree.nodes['Background'].inputs[0].default_value=(.01,.015,.03,1)
def luz(t,loc,e,c=(1,1,1),size=.5,alvo=None):
    l=bpy.data.lights.new('L',t); l.energy=e; l.color=c
    if t=='AREA': l.size=size
    o=bpy.data.objects.new('Luz',l); link(o); o.location=loc; o['render_only']=1
    if alvo: o.rotation_euler=(Vector(alvo)-Vector(loc)).to_track_quat('-Z','Y').to_euler()
    return o
luz('POINT',(0,0,2.45),60,(1,.88,.72))
luz('AREA',(CX,1.05,1.0),6,(.55,.7,1),.3,(CX,.5,1.3))     # brilho da tela no rosto
luz('AREA',(CX+.8,-.3,1.6),12,(1,.9,.85),.8,(CX,.5,1.2))  # preenchimento
luz('POINT',(JX,y1-.3,1.6),8,(.4,.55,1))
def camera(nm,pos,alvo,lens=28):
    c=bpy.data.objects.new(nm,bpy.data.cameras.new(nm)); c.data.lens=lens; c.data.clip_start=.01; link(c); c.location=pos
    c.rotation_euler=(Vector(alvo)-Vector(pos)).to_track_quat('-Z','Y').to_euler(); c['render_only']=1; return c
VL.update()
wpos=wc_ref.matrix_world.translation
cams=[camera('CamOmbro',(CX+.2,.42,1.42),(CX,1.22,.86),42),camera('CamNotebook',(CX+.42,.72,1.02),(CX+.02,1.12,.82),45),camera('CamPorta',(-1.2,-1.35,1.75),(-.5,.7,.9),18),
      camera('CamWebcamLIVE',tuple(wpos),(CX+.04,.6,.98),17)]
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(D,'jarvis_cena_v4.blend'))
for o in S.objects: o.select_set('render_only' not in o)
bpy.ops.export_scene.gltf(filepath=os.path.join(WEB,'jarvis_v4.glb'),use_selection=True,export_apply=True,export_morph=True,export_skins=True,
                          export_lights=False,export_cameras=False,export_yup=True,export_animations=False)
if '--render' in sys.argv:
    S.render.engine='CYCLES'; S.cycles.device='CPU'; S.cycles.samples=int(os.environ.get('SAMPLES',64)); S.cycles.use_denoising=True
    S.render.resolution_x,S.render.resolution_y=int(os.environ.get('RX',1280)),int(os.environ.get('RY',720))
    S.view_settings.view_transform='AgX'; S.view_settings.look='AgX - Punchy'; S.view_settings.exposure=float(os.environ.get('EXPO',-.6))
    S.render.use_freestyle=True; S.render.line_thickness=1.0
    fs=VL.freestyle_settings; ls=fs.linesets.new('Contorno') if not fs.linesets else fs.linesets[0]
    ls.linestyle=bpy.data.linestyles.new('Anime'); ls.linestyle.color=(.02,.01,.01); ls.select_by_visibility=True
    so=os.environ.get('CAMS','012')
    for i,c in enumerate(cams):
        if str(i) not in so: continue
        S.camera=c; S.render.filepath=os.path.join(D,'..','renders',f'v4_0{i+1}_{c.name}.png'); bpy.ops.render.render(write_still=True)
