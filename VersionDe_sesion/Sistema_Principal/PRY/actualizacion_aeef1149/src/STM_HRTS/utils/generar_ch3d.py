"""Genera los *Ch3D.tscn jugables de los 16 avatares nuevos.

Toma como plantilla AVH1Ch3D.tscn (CharacterBody3D + capsula + camara +
AnimationTree con los 5 clips retargeteados) y la instancia sobre cada
*_anim.glb. Los nombres de escena siguen la convencion del proyecto:
AVMJ = mujer, AVH = hombre, numeracion 5..12. Boot.gd distingue el saludo
por el literal "AVMJ" de la ruta, asi que la convencion importa.

Uso: python tools/generar_ch3d.py
"""

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
AVATARES = RAIZ / "avtrnCRS/GTLF_GODOT/GltfIMP/AVATARES"
SALIDA_M = RAIZ / "SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVHMBSC"
SALIDA_F = RAIZ / "SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/AVMJRSC/USERSMJ/MDLMJ"
SCRIPT_UID = "uid://blglsbol7iwh4"
SCRIPT_PATH = ("res://SLCAV/AVATARESCONANIMACION/USERBS/sceneuserBS/"
               "AVMJRSC/USERSMJ/MDLMJ/gdscripuser/AVMJ1Ch3D.gd")

# (archivo origen sin _anim, nombre de escena, genero, escala visual)
# Los numeros siguen el orden del carrusel: turno 2 = 5..8, turno 3 = 9..12.
# La escala solo corrige los dos modelos que vienen un 15 % mas altos que el resto.
AVATARES_NUEVOS = [
    ("avhm1", "AVH5", "M", 1.0),
    ("avhm2", "AVH6", "M", 1.0),
    ("avhm3", "AVH7", "M", 1.0),
    ("avhm5", "AVH8", "M", 1.0),
    ("AVmj4", "AVH9", "M", 1.0),
    ("AVmj5", "AVH10", "M", 1.0),
    ("AVmj6", "AVH11", "M", 1.0),
    ("AVmj7", "AVH12", "M", 1.0),
    ("avhm4", "AVMJ5", "F", 1.0),
    ("AVmj1", "AVMJ6", "F", 1.0),
    ("AVmj2", "AVMJ7", "F", 1.0),
    ("AVmj3", "AVMJ8", "F", 1.0),
    ("avhm6", "AVMJ9", "F", 0.84),
    ("avhm7", "AVMJ10", "F", 1.0),
    ("avhm8", "AVMJ11", "F", 1.0),
    ("avhm9", "AVMJ12", "F", 0.87),
]


def ruta_glb(nombre: str) -> pathlib.Path:
    carpeta = AVATARES / ("AVHM" if nombre.startswith("AVmj") else "AVMJ")
    return carpeta / (nombre + "_anim.glb")


def uid_de(ruta: pathlib.Path) -> str:
    texto = pathlib.Path(str(ruta) + ".import").read_text(encoding="utf-8")
    hallado = re.search(r'^uid="(uid://[^"]+)"', texto, re.MULTILINE)
    if not hallado:
        raise SystemExit("sin uid en " + str(ruta))
    return hallado.group(1)


def escena(glb: pathlib.Path, uid: str, nombre: str, escala: float) -> str:
    res_glb = "res://" + glb.relative_to(RAIZ).as_posix()
    raiz = nombre + "Ch3D"
    cs = "CS3D" + nombre
    e = "" if escala == 1.0 else "%.2f" % escala
    transform = ("Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, -0.85827637, 0)"
                 if escala == 1.0 else
                 "Transform3D(%s, 0, 0, 0, %s, 0, 0, 0, %s, 0, -0.85827637, 0)"
                 % (e, e, e))
    return f'''[gd_scene format=3]

[ext_resource type="PackedScene" uid="{uid}" path="{res_glb}" id="1_8njtr"]
[ext_resource type="Script" uid="{SCRIPT_UID}" path="{SCRIPT_PATH}" id="1_i373r"]

[sub_resource type="CapsuleShape3D" id="CapsuleShape3D_xrivr"]
radius = 0.37548828
height = 1.8156738

[sub_resource type="AnimationNodeBlend2" id="AnimationNodeBlend2_i373r"]

[sub_resource type="AnimationNodeAdd2" id="AnimationNodeAdd2_iewkt"]

[sub_resource type="AnimationNodeAnimation" id="AnimationNodeAnimation_tayul"]
animation = &"correrMJ1_3"

[sub_resource type="AnimationNodeAnimation" id="AnimationNodeAnimation_d5glh"]
animation = &"correrMJ1_3"

[sub_resource type="AnimationNodeAnimation" id="AnimationNodeAnimation_pa0k2"]
animation = &"left_StrafeMJ1_4"

[sub_resource type="AnimationNodeAnimation" id="AnimationNodeAnimation_fuxqw"]
animation = &"rightstrafeMJ1_5"

[sub_resource type="AnimationNodeAnimation" id="AnimationNodeAnimation_ngbxm"]
animation = &"caminarMJ1_2"

[sub_resource type="AnimationNodeBlend2" id="AnimationNodeBlend2_fq7sk"]

[sub_resource type="AnimationNodeBlend2" id="AnimationNodeBlend2_nt3t7"]

[sub_resource type="AnimationNodeBlend2" id="AnimationNodeBlend2_v2ogq"]

[sub_resource type="AnimationNodeAnimation" id="AnimationNodeAnimation_2kkfp"]
animation = &"paradoMJ1_1"

[sub_resource type="AnimationNodeBlendTree" id="AnimationNodeBlendTree_xrivr"]
graph_offset = Vector2(-576.5283, -260.0468)
nodes/output/position = Vector2(840, -240)
nodes/PRMJ1/node = SubResource("AnimationNodeAnimation_2kkfp")
nodes/PRMJ1/position = Vector2(-900, -420)
nodes/ANMJ/node = SubResource("AnimationNodeBlend2_i373r")
nodes/ANMJ/position = Vector2(-640, -400)
nodes/Animation/node = SubResource("AnimationNodeAnimation_ngbxm")
nodes/Animation/position = Vector2(-900, -220)
nodes/Add2/node = SubResource("AnimationNodeAdd2_iewkt")
nodes/Add2/position = Vector2(-260, -420)
"nodes/Animation 2/node" = SubResource("AnimationNodeAnimation_tayul")
"nodes/Animation 2/position" = Vector2(-260, -100)
nodes/Blend2/node = SubResource("AnimationNodeBlend2_v2ogq")
nodes/Blend2/position = Vector2(0, -420)
"nodes/Animation 3/node" = SubResource("AnimationNodeAnimation_d5glh")
"nodes/Animation 3/position" = Vector2(-640, -100)
"nodes/Animation 4/node" = SubResource("AnimationNodeAnimation_pa0k2")
"nodes/Animation 4/position" = Vector2(20, -140)
"nodes/Blend2 2/node" = SubResource("AnimationNodeBlend2_fq7sk")
"nodes/Blend2 2/position" = Vector2(300, -360)
"nodes/Animation 5/node" = SubResource("AnimationNodeAnimation_fuxqw")
"nodes/Animation 5/position" = Vector2(340, -80)
"nodes/Blend2 3/node" = SubResource("AnimationNodeBlend2_nt3t7")
"nodes/Blend2 3/position" = Vector2(620, -320)
node_connections = [&"output", 0, &"Blend2 3", &"ANMJ", 0, &"PRMJ1", &"ANMJ", 1, &"Animation", &"Add2", 0, &"ANMJ", &"Add2", 1, &"Animation 3", &"Blend2", 0, &"Add2", &"Blend2", 1, &"Animation 2", &"Blend2 2", 0, &"Blend2", &"Blend2 2", 1, &"Animation 4", &"Blend2 3", 0, &"Blend2 2", &"Blend2 3", 1, &"Animation 5"]

[node name="{raiz}" type="CharacterBody3D"]
script = ExtResource("1_i373r")

[node name="{cs}" type="CollisionShape3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.87194824, 0)
shape = SubResource("CapsuleShape3D_xrivr")

[node name="{nombre}" parent="{cs}" instance=ExtResource("1_8njtr")]
transform = {transform}

[node name="AnimationPlayer" parent="{cs}/{nombre}" index="1"]
autoplay = &"paradoMJ1_1"

[node name="Camera3D" type="Camera3D" parent="{cs}/{nombre}"]
transform = Transform3D(-1, 0, -1.5179343e-06, 0, 1, 0, 1.5179343e-06, 0, -1, 0, 0.98910654, -1.4097605)

[node name="AnimationTree" type="AnimationTree" parent="{cs}/{nombre}"]
tree_root = SubResource("AnimationNodeBlendTree_xrivr")
anim_player = NodePath("../AnimationPlayer")
parameters/ANMJ/blend_amount = 0.0
parameters/Add2/add_amount = 0.0
parameters/Blend2/blend_amount = 0.0
"parameters/Blend2 2/blend_amount" = 0.0
"parameters/Blend2 3/blend_amount" = 0.0

[editable path="{cs}/{nombre}"]
'''


def main() -> None:
    for nombre, escena_id, genero, escala in AVATARES_NUEVOS:
        glb = ruta_glb(nombre)
        if not glb.exists():
            raise SystemExit("falta " + str(glb))
        carpeta = SALIDA_M if genero == "M" else SALIDA_F
        destino = carpeta / (escena_id + "Ch3D.tscn")
        destino.write_text(escena(glb, uid_de(glb), escena_id, escala),
                           encoding="utf-8", newline="\n")
        print("OK", destino.relative_to(RAIZ).as_posix())


if __name__ == "__main__":
    main()
