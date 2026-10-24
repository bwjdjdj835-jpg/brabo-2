"""Ponte com o Godot 4: gera um projeto de jogo 3D (cena, jogador em 3ª pessoa com GDScript, colisão, luz,
moedas coletáveis, HUD) e, se o Godot estiver instalado, valida/importa e exporta em modo headless."""
import glob, os, shutil, subprocess
from ..registro import ferramenta
from .util import pasta, slug


def achar_godot():
    cands = [os.environ.get("GODOT_BIN"), shutil.which("godot"), shutil.which("godot4")]
    cands += sorted(glob.glob("/tmp/godot/Godot_v4*")) + sorted(glob.glob(r"C:\Godot\Godot_v4*.exe"))
    return next((c for c in cands if c and os.path.exists(c)), None)


PROJETO = """; Gerado pelo Jarvis
config_version=5

[application]
config/name="{nome}"
run/main_scene="res://main.tscn"
config/features=PackedStringArray("4.3", "Forward Plus")

[input]
frente={{"deadzone": 0.5, "events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":87,"key_label":0,"unicode":119,"location":0,"echo":false,"script":null)]}}
tras={{"deadzone": 0.5, "events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":83,"key_label":0,"unicode":115,"location":0,"echo":false,"script":null)]}}
esquerda={{"deadzone": 0.5, "events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":65,"key_label":0,"unicode":97,"location":0,"echo":false,"script":null)]}}
direita={{"deadzone": 0.5, "events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":68,"key_label":0,"unicode":100,"location":0,"echo":false,"script":null)]}}
pular={{"deadzone": 0.5, "events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":32,"key_label":0,"unicode":32,"location":0,"echo":false,"script":null)]}}
"""

PLAYER_GD = """extends CharacterBody3D
## Jogador em 3ª pessoa: WASD anda (relativo à câmera), Espaço pula, mouse gira a câmera, Esc solta o mouse.
@export var velocidade := 6.0
@export var pulo := 5.5
@export var sensibilidade := 0.003
var gravidade: float = ProjectSettings.get_setting("physics/3d/default_gravity")
@onready var pivo: Node3D = $Pivo
@onready var corpo: Node3D = $Corpo
signal moeda_coletada(total)
var moedas := 0

func _ready():
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _unhandled_input(e):
	if e is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		pivo.rotate_y(-e.relative.x * sensibilidade)
		pivo.rotation.x = clamp(pivo.rotation.x - e.relative.y * sensibilidade, -1.2, 0.4)
	if e.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _physics_process(dt):
	if not is_on_floor():
		velocity.y -= gravidade * dt
	elif Input.is_action_just_pressed("pular"):
		velocity.y = pulo
	var dir2 := Input.get_vector("esquerda", "direita", "frente", "tras")
	var dir := (pivo.global_transform.basis * Vector3(dir2.x, 0, dir2.y))
	dir.y = 0
	dir = dir.normalized()
	if dir:
		velocity.x = dir.x * velocidade
		velocity.z = dir.z * velocidade
		corpo.rotation.y = lerp_angle(corpo.rotation.y, atan2(-dir.x, -dir.z), 12 * dt)
	else:
		velocity.x = move_toward(velocity.x, 0, velocidade)
		velocity.z = move_toward(velocity.z, 0, velocidade)
	move_and_slide()

func coletar():
	moedas += 1
	moeda_coletada.emit(moedas)
"""

MOEDA_GD = """extends Area3D
func _ready():
	body_entered.connect(func(b):
		if b.has_method("coletar"):
			b.coletar()
			queue_free())

func _process(dt):
	rotate_y(2.5 * dt)
"""

MAIN_GD = """extends Node3D
## Espalha moedas e atualiza o HUD.
const MOEDA := preload("res://moeda.tscn")
@onready var hud: Label = $HUD/Placar

func _ready():
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	for i in 12:
		var m := MOEDA.instantiate()
		m.position = Vector3(rng.randf_range(-12, 12), 1.0, rng.randf_range(-12, 12))
		add_child(m)
	$Jogador.moeda_coletada.connect(func(t): hud.text = "Moedas: %d / 12" % t)
"""

MOEDA_TSCN = """[gd_scene load_steps=5 format=3]
[ext_resource type="Script" path="res://moeda.gd" id="1"]
[sub_resource type="CylinderMesh" id="m"]
top_radius = 0.35
bottom_radius = 0.35
height = 0.08
[sub_resource type="StandardMaterial3D" id="mat"]
albedo_color = Color(1, 0.8, 0.1, 1)
metallic = 1.0
roughness = 0.25
emission_enabled = true
emission = Color(0.6, 0.4, 0, 1)
[sub_resource type="SphereShape3D" id="s"]
radius = 0.5
[node name="Moeda" type="Area3D"]
script = ExtResource("1")
[node name="Malha" type="MeshInstance3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 0, -1, 0, 1, 0, 0, 0, 0)
mesh = SubResource("m")
surface_material_override/0 = SubResource("mat")
[node name="Col" type="CollisionShape3D" parent="."]
shape = SubResource("s")
"""

MAIN_TSCN = """[gd_scene load_steps=14 format=3]
[ext_resource type="Script" path="res://player.gd" id="1"]
[ext_resource type="Script" path="res://main.gd" id="2"]
[sub_resource type="ProceduralSkyMaterial" id="ceu"]
sky_top_color = Color(0.35, 0.55, 0.95, 1)
sky_horizon_color = Color(1, 0.75, 0.55, 1)
[sub_resource type="Sky" id="sky"]
sky_material = SubResource("ceu")
[sub_resource type="Environment" id="env"]
background_mode = 2
sky = SubResource("sky")
tonemap_mode = 2
glow_enabled = true
ssao_enabled = true
[sub_resource type="PlaneMesh" id="chao"]
size = Vector2(40, 40)
[sub_resource type="StandardMaterial3D" id="mchao"]
albedo_color = Color(0.3, 0.65, 0.35, 1)
[sub_resource type="BoxShape3D" id="cchao"]
size = Vector3(40, 0.2, 40)
[sub_resource type="CapsuleMesh" id="corpo"]
[sub_resource type="StandardMaterial3D" id="mcorpo"]
albedo_color = Color(0.12, 0.12, 0.18, 1)
[sub_resource type="SphereMesh" id="cabelo"]
radius = 0.32
height = 0.5
[sub_resource type="StandardMaterial3D" id="mcabelo"]
albedo_color = Color(0.88, 0.1, 0.12, 1)
[sub_resource type="CapsuleShape3D" id="ccorpo"]
[node name="Main" type="Node3D"]
script = ExtResource("2")
[node name="Ambiente" type="WorldEnvironment" parent="."]
environment = SubResource("env")
[node name="Sol" type="DirectionalLight3D" parent="."]
transform = Transform3D(0.8, -0.4, 0.45, 0, 0.75, 0.66, -0.6, -0.53, 0.6, 0, 10, 0)
shadow_enabled = true
[node name="Chao" type="StaticBody3D" parent="."]
[node name="Malha" type="MeshInstance3D" parent="Chao"]
mesh = SubResource("chao")
surface_material_override/0 = SubResource("mchao")
[node name="Col" type="CollisionShape3D" parent="Chao"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, -0.1, 0)
shape = SubResource("cchao")
[node name="Jogador" type="CharacterBody3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1.2, 0)
script = ExtResource("1")
[node name="Col" type="CollisionShape3D" parent="Jogador"]
shape = SubResource("ccorpo")
[node name="Corpo" type="Node3D" parent="Jogador"]
[node name="Malha" type="MeshInstance3D" parent="Jogador/Corpo"]
mesh = SubResource("corpo")
surface_material_override/0 = SubResource("mcorpo")
[node name="Cabelo" type="MeshInstance3D" parent="Jogador/Corpo"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.85, 0.05)
mesh = SubResource("cabelo")
surface_material_override/0 = SubResource("mcabelo")
[node name="Pivo" type="Node3D" parent="Jogador"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.8, 0)
[node name="Braco" type="SpringArm3D" parent="Jogador/Pivo"]
transform = Transform3D(1, 0, 0, 0, 0.94, 0.34, 0, -0.34, 0.94, 0, 0, 0)
spring_length = 5.0
[node name="Camera" type="Camera3D" parent="Jogador/Pivo/Braco"]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 5)
[node name="HUD" type="CanvasLayer" parent="."]
[node name="Placar" type="Label" parent="HUD"]
offset_left = 20.0
offset_top = 16.0
theme_override_font_sizes/font_size = 32
text = "Moedas: 0 / 12"
"""

EXPORT = """[preset.0]
name="Linux"
platform="Linux"
runnable=true
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="build/{slug}.x86_64"
[preset.0.options]
binary_format/embed_pck=true
[preset.1]
name="Windows Desktop"
platform="Windows Desktop"
runnable=true
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="build/{slug}.exe"
[preset.1.options]
binary_format/embed_pck=true
"""


@ferramenta(risco="arquivo")
def criar_jogo_godot(nome: str = "JogoJarvis", exportar: bool = False):
    """Cria projeto Godot 4 de jogo 3D (3ª pessoa, pulo, câmera com mouse, moedas, HUD). Valida/exporta headless se houver Godot."""
    d = pasta("godot", slug(nome))
    arqs = {"project.godot": PROJETO.format(nome=nome), "main.tscn": MAIN_TSCN, "main.gd": MAIN_GD, "player.gd": PLAYER_GD,
            "moeda.gd": MOEDA_GD, "moeda.tscn": MOEDA_TSCN, "export_presets.cfg": EXPORT.format(slug=slug(nome)),
            "LEIA-ME.txt": "Abra no Godot 4.3+: Importar -> project.godot. WASD anda, Espaço pula, mouse gira a câmera, Esc solta o mouse.\n"}
    for n, c in arqs.items():
        open(os.path.join(d, n), "w", encoding="utf-8").write(c)
    r = {"ok": True, "pasta": d, "arquivos": sorted(arqs)}
    g = achar_godot()
    if not g:
        r["godot"] = "não instalado (defina GODOT_BIN para validar/exportar)"; return r
    p = subprocess.run([g, "--headless", "--path", d, "--import", "--quit"], capture_output=True, text=True, timeout=300)
    saida = p.stdout + p.stderr
    erros = [l for l in saida.splitlines() if "ERROR" in l or "SCRIPT ERROR" in l or "Parse Error" in l]
    r.update(godot=g, validacao="ok" if not erros else "erros", erros=erros[:15])
    if exportar:
        os.makedirs(os.path.join(d, "build"), exist_ok=True)
        p = subprocess.run([g, "--headless", "--path", d, "--export-release", "Linux"], capture_output=True, text=True, timeout=600)
        r["export"] = "ok" if p.returncode == 0 else (p.stdout + p.stderr)[-800:]
    return r
