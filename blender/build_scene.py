# Gera a cena do Jarvis no Blender (bpy). Uso: blender -b -P build_scene.py
import bpy, bmesh, math, os
from mathutils import Vector
D=os.path.dirname(os.path.abspath(__file__)); WEB=os.path.join(D,'..','web','assets')
bpy.ops.wm.read_factory_settings(use_empty=True)
S=bpy.context.scene
def V(x,y,z): return Vector((x,-z,y))   # coords three.js (Y-up) -> Blender (Z-up)

def M(name,col,rough=.5,metal=0.,emit=None,es=0.,coat=0.):
    m=bpy.data.materials.get(name)
    if m: return m
    m=bpy.data.materials.new(name); m.use_nodes=True; b=m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value=(*col,1); b.inputs['Roughness'].default_value=rough; b.inputs['Metallic'].default_value=metal
    b.inputs['Coat Weight'].default_value=coat
    if emit: b.inputs['Emission Color'].default_value=(*emit,1); b.inputs['Emission Strength'].default_value=es
    return m
CY=(.24,.9,1.)
mCasco=M('Casco',(.82,.85,.88),.22,.15,coat=.6); mJunta=M('Junta',(.05,.06,.07),.35,.8)
mVisor=M('Visor',(.005,.008,.012),.08,.3,coat=1.); mNeon=M('Neon',(0,0,0),emit=CY,es=6)
mAlu=M('Aluminio',(.55,.57,.6),.28,1.); mTecla=M('Tecla',(.02,.02,.025),.55)
mMesa=M('Madeira',(.16,.09,.05),.35,coat=.3); mPerna=M('Aco',(.08,.08,.09),.3,1.)
mTecido=M('Tecido',(.03,.035,.04),.85); mPlast=M('Plastico',(.02,.02,.02),.4)
mParede=M('Parede',(.06,.075,.09),.85); mPiso=M('Piso',(.04,.045,.05),.18,.3)
mVaso=M('Vaso',(.85,.85,.82),.4); mFolha=M('Folha',(.05,.25,.08),.6)

def obj(me,name,mat=None,parent=None):
    o=bpy.data.objects.new(name,me); S.collection.objects.link(o)
    if mat: o.data.materials.append(mat)
    if parent: o.parent=parent
    return o
def cubo(name,size,loc,mat,bev=0.,parent=None,seg=3):
    me=bpy.data.meshes.new(name); bm=bmesh.new(); bmesh.ops.create_cube(bm,size=1); bm.to_mesh(me); bm.free()
    o=obj(me,name,mat,parent); o.scale=size; o.location=loc
    if bev: m=o.modifiers.new('b','BEVEL'); m.width=bev; m.segments=seg; m.limit_method='NONE'; m.affect='EDGES'
    bpy.context.view_layer.objects.active=o; o.select_set(True); bpy.ops.object.transform_apply(scale=True,location=False); o.select_set(False)
    for p in o.data.polygons: p.use_smooth=True
    return o
def cil(name,r,h,loc,mat,parent=None,v=48,rot=(0,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r,depth=h,vertices=v,location=loc,rotation=rot); o=bpy.context.object; o.name=name
    o.data.materials.append(mat); o.parent=parent; bpy.ops.object.shade_smooth(); return o
def esfera(name,r,loc,mat,scale=(1,1,1),parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r,location=loc,segments=48,ring_count=24); o=bpy.context.object; o.name=name
    o.scale=scale; o.data.materials.append(mat); o.parent=parent; bpy.ops.object.shade_smooth(); return o

# ---------- SALA ----------
piso=cubo('Piso',(12,12,.02),V(0,-.01,0),mPiso)
cubo('ParedeFundo',(12,.1,5),V(0,2.5,-4),mParede); cubo('ParedeLado',(.1,12,5),V(-5,2.5,0),mParede)
for i in range(7): cubo(f'NeonV{i}',(.03,.03,3.2),V(-4.5+i*1.5,2.3,-3.94),mNeon)
cubo('NeonRodape',(12,.03,.03),V(0,.06,-3.94),mNeon); cubo('NeonRodapeL',(.03,12,.03),V(-4.94,.06,0),mNeon)
# painéis acústicos na parede lateral
for i in range(4):
    for j in range(2): cubo(f'Painel{i}{j}',(.04,.7,.7),V(-4.93,1.3+j*.8,-2.4+i*.8),mTecido,.01)
# estante
est=cubo('Estante',(1.6,.35,.04),V(1.8,1.6,-3.8),mMesa,.005); cubo('Estante2',(1.6,.35,.04),V(1.8,2.1,-3.8),mMesa,.005)
for k in range(6): cubo(f'Livro{k}',(.05,.25,.22+.03*(k%3)),V(1.2+k*.07,1.74+.015*(k%3),-3.8),M(f'Livro{k}',[(.5,.1,.1),(.1,.2,.5),(.8,.7,.6),(.1,.4,.3),(.3,.3,.3),(.6,.4,.1)][k],.6),.004)
esfera('Globo',.1,V(2.3,1.72,-3.8),mNeon)
# planta
cil('Vaso',.18,.4,V(3.9,.2,-3.3),mVaso); cil('Terra',.17,.02,V(3.9,.4,-3.3),M('Terra',(.05,.03,.02),.9))
for k in range(9):
    a=k*2.4; bpy.ops.mesh.primitive_cone_add(radius1=.06,depth=.7,location=V(3.9+.12*math.cos(a),.72,-3.3+.12*math.sin(a)),rotation=(math.cos(a)*.5,math.sin(a)*.5,0))
    bpy.context.object.data.materials.append(mFolha)

# ---------- MESA ----------
mesa=cubo('Tampo',(2.4,1.2,.05),V(0,.75,0),mMesa,.012)
for x,z in [(-1.1,-.5),(1.1,-.5),(-1.1,.5),(1.1,.5)]: cubo(f'PernaMesa',(.05,.05,.72),V(x,.37,z),mPerna,.008)
cubo('FitaLed',(2.36,.01,.01),V(0,.72,.58),mNeon)
# acessórios
cil('Caneca',.04,.1,V(.7,.83,.15),mVaso); cil('Cafe',.036,.005,V(.7,.875,.15),M('Cafe',(.05,.02,.01),.1))
mouse=esfera('Mouse',.035,V(.62,.79,.05),mPlast,(1,1.6,.45))
cubo('Mousepad',(.3,.25,.004),V(.62,.777,.05),mTecido,.002)
cil('LuminariaBase',.08,.02,V(-.95,.785,-.4),mPerna); cil('LuminariaHaste',.012,.55,V(-.95,1.06,-.4),mPerna)
cubo('LuminariaCabeca',(.08,.22,.04),V(-.95,1.33,-.3),mPerna,.01); cubo('LuminariaLuz',(.06,.2,.005),V(-.95,1.308,-.3),M('LuzQuente',(0,0,0),emit=(1,.8,.6),es=8))

# ---------- NOTEBOOK ----------
note=bpy.data.objects.new('Notebook',None); S.collection.objects.link(note); note.location=V(0,.775,-.05)
base=cubo('NoteBase',(.36,.25,.018),(0,0,.009),mAlu,.006,note)
for r in range(5):
    for c in range(14):
        cubo('Tecla',(.022,.02,.006),(-.195+c*.03,-(-.105+r*.026),.019),mTecla,.002,note,2)
cubo('Touchpad',(.12,.07,.002),(0,-.085,.0185),M('Touchpad',(.4,.42,.45),.35,1.),.002,note)
# adesivo i5 13ª geração
st=bpy.data.images.load(os.path.join(D,'sticker.png')); st.pack()
ms=bpy.data.materials.new('AdesivoI5'); ms.use_nodes=True; nt=ms.node_tree; tx=nt.nodes.new('ShaderNodeTexImage'); tx.image=st
nt.links.new(tx.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color']); nt.nodes['Principled BSDF'].inputs['Roughness'].default_value=.25
bpy.ops.mesh.primitive_plane_add(size=.032,location=(.145,-.095,.0186)); a=bpy.context.object; a.name='AdesivoI5'; a.parent=note; a.data.materials.append(ms)
# tampa (dobradiça)
tampa=bpy.data.objects.new('Tampa',None); S.collection.objects.link(tampa); tampa.parent=note; tampa.location=(0,.125,.018); tampa.rotation_euler=(math.radians(-16),0,0)
cubo('TampaTraseira',(.36,.006,.235),(0,.003,.1175),mAlu,.004,tampa)
cubo('Moldura',(.355,.001,.23),(0,-.0005,.1175),mTecla,.0,tampa)
cil('Webcam',.002,.001,(0,-.0012,.226),mNeon,tampa,16,(math.pi/2,0,0))
# tela: material separado "TelaAoVivo" (textura ao vivo no navegador)
mt=bpy.data.materials.new('TelaAoVivo'); mt.use_nodes=True; nt=mt.node_tree; b=nt.nodes['Principled BSDF']
tg=nt.nodes.new('ShaderNodeTexImage'); scr=bpy.data.images.load(os.path.join(D,'tela_preview.png')); scr.pack(); tg.image=scr
nt.links.new(tg.outputs['Color'],b.inputs['Base Color']); nt.links.new(tg.outputs['Color'],b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value=1.5; b.inputs['Roughness'].default_value=.1
bpy.ops.mesh.primitive_plane_add(size=1,location=(0,-.0012,.122),rotation=(math.pi/2,0,0)); t=bpy.context.object; t.name='Tela'; t.scale=(.336,.21,1); t.parent=tampa; t.data.materials.append(mt)

# ---------- CADEIRA ----------
cad=bpy.data.objects.new('Cadeira',None); S.collection.objects.link(cad); cad.location=V(0,0,.85)
cubo('Assento',(.52,.5,.09),(0,0,.5),mTecido,.04,cad,4)
enc=cubo('Encosto',(.5,.08,.72),(0,-.27,.95),mTecido,.04,cad,4); enc.rotation_euler=(math.radians(-10),0,0)
cubo('EncostoLed',(.46,.01,.012),(0,-.33,1.3),mNeon,0,cad)
cil('Pistao',.03,.4,(0,0,.27),mPerna,cad)
for k in range(5):
    a=k*2*math.pi/5; p=cubo('PeEstrela',(.3,.04,.03),(.15*math.cos(a),.15*math.sin(a),.07),mPerna,.01,cad); p.rotation_euler=(0,0,a)
    esfera('Rodinha',.03,(.3*math.cos(a),.3*math.sin(a),.03),mPlast,parent=cad)
for s in (-1,1):
    cubo('ApoioBraco',(.06,.3,.03),(s*.29,-.02,.72),mPlast,.012,cad); cubo('ApoioHaste',(.03,.04,.2),(s*.29,-.08,.61),mPerna,.005,cad)

# ---------- AGENTE (androide, modificador Skin + Subdivision) ----------
ag=bpy.data.objects.new('Agente',None); S.collection.objects.link(ag)
P={'pelvis':V(0,.6,.8),'cintura':V(0,.78,.82),'peito':V(0,1.02,.8),'pescoco':V(0,1.3,.78),
   'qe':V(-.1,.6,.8),'je':V(-.11,.6,.38),'te':V(-.11,.12,.4),'pe':V(-.11,.04,.27),
   'qd':V(.1,.6,.8),'jd':V(.11,.6,.38),'td':V(.11,.12,.4),'pd':V(.11,.04,.27),
   'oe':V(-.2,1.2,.78),'ce':V(-.25,.97,.56),'me':V(-.14,.82,.2),'od':V(.2,1.2,.78),'cd':V(.25,.97,.56),'md':V(.14,.82,.2)}
R={'pelvis':(.13,.09),'cintura':(.095,.075),'peito':(.15,.1),'pescoco':(.045,.045),'qe':(.075,.075),'je':(.05,.05),'te':(.04,.04),'pe':(.04,.025),
   'qd':(.075,.075),'jd':(.05,.05),'td':(.04,.04),'pd':(.04,.025),'oe':(.05,.05),'ce':(.035,.035),'me':(.035,.02),'od':(.05,.05),'cd':(.035,.035),'md':(.035,.02)}
E=[('pelvis','cintura'),('cintura','peito'),('peito','pescoco'),('pelvis','qe'),('qe','je'),('je','te'),('te','pe'),('pelvis','qd'),('qd','jd'),('jd','td'),('td','pd'),
   ('peito','oe'),('oe','ce'),('ce','me'),('peito','od'),('od','cd'),('cd','md')]
k=list(P); me=bpy.data.meshes.new('Corpo'); me.from_pydata([P[n] for n in k],[(k.index(a),k.index(b)) for a,b in E],[])
corpo=obj(me,'Corpo',mCasco,ag); sk=corpo.modifiers.new('skin','SKIN'); sk.use_smooth_shade=True
for i,n in enumerate(k): me.skin_vertices[0].data[i].radius=R[n]
me.skin_vertices[0].data[0].use_root=True
corpo.modifiers.new('sub','SUBSURF').levels=2
# juntas escuras (ombros, cotovelos, joelhos) e reator no peito
for n in ['oe','od','ce','cd','je','jd']: esfera('Junta_'+n,{'o':.055,'c':.04,'j':.05}[n[0]],P[n],mJunta,parent=ag)
for n in ['ce','cd']: 
    o=cil('AnelPulso',.047,.012,P[n].lerp(P['m'+n[1]],.55),mNeon,ag,32); o.rotation_euler=(P['m'+n[1]]-P[n]).to_track_quat('Z','Y').to_euler()
pl=esfera('PlacaPeito',.13,V(0,1.07,.72),mJunta,(.75,.3,.5),ag)
for s_ in (-1,1): cubo('LinhaTorso',(.006,.006,.18),V(s_*.07,.86,.73),mNeon,0,ag)
r=cil('Reator',.028,.01,V(0,1.06,.675),mNeon,ag,32,(math.pi/2,0,0))
for s in (-1,1): esfera('Mao',.04,P['me' if s<0 else 'md'],mJunta,(1,1.4,.6),ag)
# cabeça: pivô no pescoço
cab=bpy.data.objects.new('Cabeca',None); S.collection.objects.link(cab); cab.parent=ag; cab.location=V(0,1.34,.78)
cr=esfera('Cranio',.13,(0,0,.14),mCasco,(.86,1.,1.12),cab)
vi=esfera('VisorRosto',.115,(0,.07,.13),mVisor,(.86,.62,.62),cab)
for s in (-1,1):
    cil('Orelha',.035,.03,(s*.11,0,.14),mJunta,cab,32,(0,math.pi/2,0)); cil('OrelhaLed',.022,.032,(s*.11,0,.14),mNeon,cab,32,(0,math.pi/2,0))
    o=esfera('Olho',.018,(s*.04,.14,.15),mNeon,(1.5,.35,.45),cab); o.name='Olho_'+('E' if s<0 else 'D')
# boca com shape key "Fala"
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,.122,.055)); b=bpy.context.object; b.name='Boca'; b.scale=(.05,.008,.004); b.parent=cab
bpy.ops.object.transform_apply(scale=True,location=False); b.data.materials.append(mNeon)
b.shape_key_add(name='Basis'); kf=b.shape_key_add(name='Fala')
for v in kf.data: v.co.z*=6; v.co.x*=.7
cil('Pescoco',.04,.12,(0,0,0),mJunta,cab,32)
for i in range(3): cil('AnelPescoco',.046,.008,(0,0,-.03+i*.03),mCasco,cab,32)
cab.rotation_euler=(math.radians(-12),0,0)

# ---------- LUZES / CÂMERAS (só para render) ----------
W=S.world=bpy.data.worlds.new('W'); W.use_nodes=True; W.node_tree.nodes['Background'].inputs[0].default_value=(.004,.008,.014,1)
def luz(t,loc,e,c=(1,1,1),size=1,rot=(0,0,0)):
    l=bpy.data.lights.new('L',t); l.energy=e; l.color=c
    if t=='AREA': l.size=size
    o=bpy.data.objects.new('Luz',l); S.collection.objects.link(o); o.location=loc; o.rotation_euler=rot; o['render_only']=1; return o
k1=luz('AREA',V(2.5,3.5,2.5),400,size=2); k1.rotation_euler=(V(0,1,0)-k1.location).to_track_quat('-Z','Y').to_euler()
luz('POINT',V(-2.5,2.5,-2),150,CY); luz('POINT',V(0,1.1,.4),8,(.5,.85,1))
f=luz('AREA',V(-1,2,3),120,(.6,.8,1),3); f.rotation_euler=(V(0,1,0)-f.location).to_track_quat('-Z','Y').to_euler()
def cam(n,pos,alvo,lens=35):
    c=bpy.data.objects.new(n,bpy.data.cameras.new(n)); c.data.lens=lens; S.collection.objects.link(c); c.location=V(*pos)
    c.rotation_euler=(V(*alvo)-c.location).to_track_quat('-Z','Y').to_euler(); c['render_only']=1; return c
cams=[cam('CamGeral',(3.2,2.3,3.8),(0,1.,0),32),cam('CamRosto',(-.9,1.55,-.55),(0,1.3,.75),50),cam('CamOmbro',(.9,1.7,1.9),(0,.95,-.1),40)]

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(D,'jarvis_cena.blend'))

# ---------- EXPORT GLB (sem luzes/câmeras) ----------
for o in S.objects: o.select_set('render_only' not in o)
bpy.ops.export_scene.gltf(filepath=os.path.join(WEB,'jarvis_cena.glb'),use_selection=True,export_apply=True,export_morph=True,export_lights=False,export_cameras=False,export_yup=True)

# ---------- RENDERS ----------
import sys
if '--render' in sys.argv:
    S.render.engine='CYCLES'; S.cycles.device='CPU'; S.cycles.samples=int(os.environ.get('SAMPLES',96)); S.cycles.use_denoising=True
    S.render.resolution_x,S.render.resolution_y=1280,720; S.view_settings.view_transform='AgX'; S.view_settings.look='AgX - Punchy'
    for i,c in enumerate(cams):
        S.camera=c; S.render.filepath=os.path.join(D,'..','renders',f'blender_0{i+1}_{c.name}.png'); bpy.ops.render.render(write_still=True)
