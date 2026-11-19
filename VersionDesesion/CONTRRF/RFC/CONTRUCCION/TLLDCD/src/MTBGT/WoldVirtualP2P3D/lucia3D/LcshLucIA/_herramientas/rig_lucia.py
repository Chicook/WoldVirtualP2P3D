import bpy
import json
import os
from mathutils import Matrix, Vector

# ============================================================================
# Rigging de LucIA con el esqueleto Mixamo (Blender headless).
#
#   blender --background --python _herramientas/rig_lucia.py
#
# Por qué existe: el .glb original (LucIA.glb) es una malla fusionada sin
# esqueleto. El módulo anterior se fabricaba un rig de 10 huesos y calculaba
# los pesos por radio en GDScript; los hombros se inflaban, el cuello se
# estiraba y la manga no seguía al brazo. Este script hornea un rig real:
#
#   1. Normaliza la malla a 1,75 m con los pies en z=0 (conserva BOCA).
#   2. Importa el esqueleto Mixamo y le CORRIGE las longitudes de hueso:
#      el importador glTF las deja ~100x más largas (Hips 9,1 m en vez de
#      9 cm), lo que rompe el bone-heat y hace que la cadera domine la cabeza.
#   3. Padres con pesos automáticos y normaliza a 1,0.
#   4. Exporta GLB con skin + morphs + el clip Mixamo (Blender 5 exige
#      asignar el "slot" de la acción, si no la animación no viaja).
#
# Salida: GLTF_lucIA/AreaDeTrabajo/LucIA3D/LucIA_rig.glb
# ============================================================================

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLEND = os.path.join(BASE, "GLTF_lucIA", "AreaDeTrabajo", "ImportlucIA", "LucIA3D.blend")
SKEL = os.path.join(BASE, "GLTF_lucIA", "AreaDeTrabajo", "LucIA3D", "esqueleto.glb")
OUT = os.path.join(BASE, "GLTF_lucIA", "AreaDeTrabajo", "LucIA3D", "LucIA_rig.glb")
WORK = os.path.join(BASE, "_work_rig.blend")
ALTO = 1.75
log = {}


def bbox(me):
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def transformar(me, M):
    for v in me.vertices:
        v.co = M @ v.co
    if me.shape_keys:
        for kb in me.shape_keys.key_blocks:
            for pt in kb.data:
                pt.co = M @ pt.co


def corto(n):
    for pre in ("mixamorig8:", "mixamorig:", "mixamorig8_", "mixamorig_"):
        if n.startswith(pre):
            return n[len(pre):]
    return n


CONTINUA = {
    "Hips": "Spine", "Spine": "Spine1", "Spine1": "Spine2", "Spine2": "Neck",
    "Neck": "Head", "Head": "HeadTop_End",
    "LeftShoulder": "LeftArm", "LeftArm": "LeftForeArm", "LeftForeArm": "LeftHand",
    "RightShoulder": "RightArm", "RightArm": "RightForeArm", "RightForeArm": "RightHand",
    "LeftUpLeg": "LeftLeg", "LeftLeg": "LeftFoot", "LeftFoot": "LeftToeBase", "LeftToeBase": "LeftToe_End",
    "RightUpLeg": "RightLeg", "RightLeg": "RightFoot", "RightFoot": "RightToeBase", "RightToeBase": "RightToe_End",
}


def continuacion(nombre):
    c = corto(nombre)
    if c in CONTINUA:
        return CONTINUA[c]
    # dedos: Xxx1 -> Xxx2 -> Xxx3 -> Xxx4
    if len(c) > 1 and c[-1] in "123":
        return c[:-1] + str(int(c[-1]) + 1)
    return None


bpy.ops.wm.open_mainfile(filepath=BLEND)
cuerpo = bpy.data.objects["cuerpo"]
me = cuerpo.data
transformar(me, cuerpo.matrix_world)
cuerpo.matrix_world = Matrix.Identity(4)
mn, mx = bbox(me)
escala = ALTO / (mx[2] - mn[2])
transformar(me, Matrix.Scale(escala, 4) @ Matrix.Translation((0.0, 0.0, -mn[2])))
bpy.context.view_layer.update()
mn, mx = bbox(me)
log["malla"] = {"min": [round(v, 4) for v in mn], "max": [round(v, 4) for v in mx]}
log["shape_keys"] = [k.name for k in me.shape_keys.key_blocks]

bpy.ops.import_scene.gltf(filepath=SKEL)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for o in list(bpy.data.objects):
    if o.type == "MESH" and o is not cuerpo:
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.object.select_all(action="DESELECT")
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ---------------------------------------------------------- corregir longitudes
antes = {}
for b in arm.data.bones:
    antes[corto(b.name)] = round(b.length, 3)

bpy.ops.object.mode_set(mode="EDIT")
ebs = arm.data.edit_bones
por_corto = {corto(eb.name): eb for eb in ebs}

corregidos = 0
for nombre_c, eb in por_corto.items():
    destino = continuacion(eb.name)
    largo = None
    if destino and destino in por_corto:
        destino_eb = por_corto[destino]
        if destino_eb.parent == eb:
            largo = (destino_eb.head - eb.head).length
    if largo is None or largo < 1e-4:
        direccion = (eb.tail - eb.head)
        if direccion.length < 1e-9:
            direccion = Vector((0.0, 0.0, 1.0))
        largo = 0.05
        eb.tail = eb.head + direccion.normalized() * largo
    else:
        eb.tail = eb.head + (destino_eb.head - eb.head).normalized() * largo
    corregidos += 1

bpy.ops.object.mode_set(mode="OBJECT")
bpy.context.view_layer.update()

despues = {}
for b in arm.data.bones:
    despues[corto(b.name)] = round(b.length, 3)
log["huesos_corregidos"] = corregidos
log["largo_antes"] = {k: antes[k] for k in ["Hips", "Spine", "Head", "LeftArm", "LeftForeArm", "LeftHand"] if k in antes}
log["largo_despues"] = {k: despues[k] for k in ["Hips", "Spine", "Head", "LeftArm", "LeftForeArm", "LeftHand"] if k in despues}
log["largo_max"] = max(despues.values())

# segmentos en mundo para comprobar
seg = {}
for b in arm.data.bones:
    if corto(b.name) in ("Hips", "Spine2", "Head", "LeftArm", "LeftForeArm", "LeftHand"):
        seg[corto(b.name)] = {
            "head": [round(v, 3) for v in b.head_local],
            "tail": [round(v, 3) for v in b.tail_local],
            "len": round(b.length, 3),
        }
log["segmentos"] = seg

# Pose limpia
arm.data.pose_position = "POSE"
arm.animation_data_clear()
for pb in arm.pose.bones:
    pb.rotation_mode = "QUATERNION"
    pb.location = (0, 0, 0)
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.scale = (1, 1, 1)
bpy.context.view_layer.update()

# ---------------------------------------------------------- binding
bpy.ops.object.select_all(action="DESELECT")
cuerpo.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type="ARMATURE_AUTO")

# ---------------------------------------------------------- normalizar pesos
bpy.ops.object.select_all(action="DESELECT")
cuerpo.select_set(True)
bpy.context.view_layer.objects.active = cuerpo
normalizado = False
try:
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)
    normalizado = True
except Exception as e:
    log["normalizar_error"] = str(e)

# Si el operador no normalizó, hacerlo a mano
if not normalizado:
    for v in me.vertices:
        total = sum(g.weight for g in v.groups)
        if total > 1e-9:
            for g in v.groups:
                g.weight = g.weight / total
    log["normalizado_manual"] = True

bpy.context.view_layer.update()

# ---------------------------------------------------------- diagnóstico
grupos = {g.index: g.name.replace("mixamorig8:", "") for g in cuerpo.vertex_groups}
dominio = {}
cajas = {}
for v in me.vertices:
    mejor_w = -1.0
    mejor_i = -1
    for g in v.groups:
        if g.weight > mejor_w:
            mejor_w = g.weight
            mejor_i = g.group
    if mejor_i >= 0:
        nombre = grupos[mejor_i]
        dominio[nombre] = dominio.get(nombre, 0) + 1
        if nombre not in cajas:
            cajas[nombre] = [list(v.co), list(v.co)]
        else:
            for k in range(3):
                cajas[nombre][0][k] = min(cajas[nombre][0][k], v.co[k])
                cajas[nombre][1][k] = max(cajas[nombre][1][k], v.co[k])

log["dominio"] = dict(sorted(dominio.items(), key=lambda x: -x[1]))
log["cajas"] = {k: [[round(c, 2) for c in cajas[k][0]], [round(c, 2) for c in cajas[k][1]]] for k in cajas}
sumas = [sum(g.weight for g in v.groups) for v in me.vertices]
log["suma_pesos"] = {"min": round(min(sumas), 3), "max": round(max(sumas), 3),
                     "media": round(sum(sumas) / len(sumas), 3)}

bpy.ops.wm.save_as_mainfile(filepath=WORK)

# Vincular la acción Mixamo (con slot, Blender 5) para que se exporte
accion = bpy.data.actions.get("mixamo.com")
if accion is not None:
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = accion
    if hasattr(accion, "slots") and len(accion.slots) > 0:
        arm.animation_data.action_slot = accion.slots[0]
    log["accion_mixamo"] = accion.name
    log["accion_frames"] = [round(v, 1) for v in accion.frame_range]
log["acciones"] = [a.name for a in bpy.data.actions]

bpy.ops.object.select_all(action="DESELECT")
cuerpo.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.gltf(
    filepath=OUT, export_format="GLB", use_selection=True,
    export_animations=True, export_animation_mode="ACTIONS",
    export_morph=True, export_skins=True,
    export_apply=False, export_yup=True)
log["export_mb"] = round(os.path.getsize(OUT) / 1024 / 1024, 2)

print("RIG4_JSON_BEGIN")
print(json.dumps(log, indent=1, ensure_ascii=False))
print("RIG4_JSON_END")
