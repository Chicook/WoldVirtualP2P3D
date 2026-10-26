class_name Personalizacion
extends RefCounted
## Aspecto del avatar elegido, editable sin morph targets.
##
## Los GLB no traen blend shapes, pero:
## - cada prenda es una malla aparte con su material -> se tinta por separado;
## - la malla del cuerpo se puede deformar en espacio de reposo por regiones
##   (nariz, labios, orejas, ojos) y por zonas del cuerpo (torso, brazos,
##   piernas), manteniendo UV, huesos y pesos, asi que la animacion sigue
##   intacta;
## - la altura se aplica escalando el nodo visual del modelo (nunca el
##   CharacterBody3D, para no deformar la capsula de colision).

const SECCION := "personalizacion"
const ORDEN := ["piel", "pelo", "camiseta", "pantalon", "zapatillas"]
const PROPORCIONES := ["altura_cm", "ancho", "cabeza", "hombros", "torso", "brazos", "piernas"]
const ROSTRO := ["nariz", "labios", "orejas", "ojos"]
const NOMBRES := {
	"piel": "Piel",
	"pelo": "Pelo",
	"camiseta": "Camiseta",
	"pantalon": "Pantalon",
	"zapatillas": "Zapatillas",
	"altura_cm": "Altura",
	"ancho": "Complexion",
	"cabeza": "Cabeza",
	"hombros": "Hombros",
	"torso": "Torso",
	"brazos": "Brazos",
	"piernas": "Piernas",
	"nariz": "Nariz",
	"labios": "Labios",
	"orejas": "Orejas",
	"ojos": "Ojos",
}
const POR_DEFECTO := {
	"piel": Color(1, 1, 1),
	"pelo": Color(1, 1, 1),
	"camiseta": Color(1, 1, 1),
	"pantalon": Color(1, 1, 1),
	"zapatillas": Color(1, 1, 1),
	"altura_cm": 0.0,
	"ancho": 1.0,
	"cabeza": 1.0,
	"hombros": 1.0,
	"torso": 1.0,
	"brazos": 1.0,
	"piernas": 1.0,
	"nariz": 0.0,
	"labios": 0.0,
	"orejas": 0.0,
	"ojos": 0.0,
}
const RANGOS := {
	"altura_cm": Vector2(0, 30),
	"ancho": Vector2(0.85, 1.15),
	"cabeza": Vector2(0.85, 1.15),
	"hombros": Vector2(0.8, 1.25),
	"torso": Vector2(0.8, 1.25),
	"brazos": Vector2(0.8, 1.25),
	"piernas": Vector2(0.8, 1.25),
	"nariz": Vector2(0, 1),
	"labios": Vector2(0, 1),
	"orejas": Vector2(0, 1),
	"ojos": Vector2(0, 1),
}
const ALTURA_REFERENCIA := 1.75

# Cache por malla compartida: las instancias de un GLB reutilizan el recurso.
static var _cache_arreglos := {}
static var _cache_mascaras := {}
static var _cache_geo := {}
static var _cache_cabeza := {}
static var _cache_vertices := {}


static func leer() -> Dictionary:
	var cfg := ConfigFile.new()
	if cfg.load("user://registro.cfg") != OK:
		return POR_DEFECTO.duplicate()
	var d := POR_DEFECTO.duplicate()
	for clave in ORDEN:
		if cfg.has_section_key(SECCION, clave):
			d[clave] = Color.html(str(cfg.get_value(SECCION, clave, "ffffff")))
	for clave in PROPORCIONES + ROSTRO:
		if cfg.has_section_key(SECCION, clave):
			d[clave] = float(cfg.get_value(SECCION, clave, POR_DEFECTO[clave]))
	# Configs antiguas guardaban "altura" como factor 0.9..1.1.
	if not cfg.has_section_key(SECCION, "altura_cm") and cfg.has_section_key(SECCION, "altura"):
		var viejo := float(cfg.get_value(SECCION, "altura", 1.0))
		d["altura_cm"] = clampf((viejo - 1.0) * 175.0, 0.0, 30.0)
	return normalizar(d)


static func guardar(datos: Dictionary) -> void:
	var d := normalizar(datos)
	var cfg := ConfigFile.new()
	cfg.load("user://registro.cfg")
	for clave in ORDEN:
		cfg.set_value(SECCION, clave, d[clave].to_html(false))
	for clave in PROPORCIONES + ROSTRO:
		cfg.set_value(SECCION, clave, d[clave])
	cfg.erase_section_key(SECCION, "altura")
	cfg.save("user://registro.cfg")


static func normalizar(datos: Dictionary) -> Dictionary:
	var d := POR_DEFECTO.duplicate()
	for clave in ORDEN:
		var c: Color = POR_DEFECTO[clave]
		if datos.has(clave):
			if datos[clave] is Color:
				c = datos[clave]
			elif datos[clave] is String:
				c = Color.html(str(datos[clave]))
		d[clave] = Color(clampf(c.r, 0.0, 2.0), clampf(c.g, 0.0, 2.0), clampf(c.b, 0.0, 2.0), 1.0)
	for clave in PROPORCIONES + ROSTRO:
		if datos.has(clave):
			var r: Vector2 = RANGOS[clave]
			d[clave] = clampf(float(datos[clave]), r.x, r.y)
	return d


## Texto compacto para replicar el aspecto a los demas peers.
static func codificar(datos: Dictionary) -> String:
	var d := normalizar(datos)
	var partes := PackedStringArray()
	for clave in ORDEN:
		partes.append(d[clave].to_html(false))
	for clave in PROPORCIONES + ROSTRO:
		partes.append("%.3f" % d[clave])
	return "|".join(partes)


static func decodificar(texto: String) -> Dictionary:
	var partes := texto.split("|")
	if partes.size() < ORDEN.size() + 2:
		return POR_DEFECTO.duplicate()
	var d := {}
	for i in ORDEN.size():
		d[ORDEN[i]] = Color.html(partes[i])
	var resto: Array = PROPORCIONES + ROSTRO
	for i in resto.size():
		var pos := ORDEN.size() + i
		if pos < partes.size():
			d[resto[i]] = partes[pos]
	return normalizar(d)


## Aplica tintes, proporciones y rasgos a un avatar ya instanciado.
static func aplicar(avatar: Node, datos: Dictionary) -> void:
	if avatar == null or not is_instance_valid(avatar):
		return
	var d := normalizar(datos)
	_aplicar_tintes(avatar, d)
	_aplicar_figura(avatar, d)


## Altura visible actual en metros (para colocar etiquetas sobre la cabeza).
static func altura_total(avatar: Node) -> float:
	if avatar == null or not is_instance_valid(avatar):
		return ALTURA_REFERENCIA
	var modelo := _modelo(avatar)
	var base: float = avatar.get_meta("pers_altura_base", ALTURA_REFERENCIA)
	var escala0: Vector3 = avatar.get_meta("pers_escala_base", Vector3.ONE)
	if modelo == null or escala0.y <= 0.00001:
		return base
	return base * (modelo.scale.y / escala0.y)


static func _aplicar_tintes(avatar: Node, d: Dictionary) -> void:
	var firma := ""
	for clave in ORDEN:
		firma += d[clave].to_html(false) + "|"
	if avatar.get_meta("pers_firma_tintes", "") == firma:
		return
	avatar.set_meta("pers_firma_tintes", firma)

	for nodo in avatar.find_children("*", "MeshInstance3D", true, false):
		var mi := nodo as MeshInstance3D
		if mi.mesh == null:
			continue
		for s in mi.mesh.get_surface_count():
			var parte := _parte_superficie(mi, s)
			if parte == "":
				continue
			var tinte: Color = d[parte]
			var original := mi.mesh.surface_get_material(s)
			if original == null or not (original is BaseMaterial3D) or tinte.is_equal_approx(Color.WHITE):
				mi.set_surface_override_material(s, null)
				continue
			var mat := (original as BaseMaterial3D).duplicate() as BaseMaterial3D
			mat.albedo_color = (original as BaseMaterial3D).albedo_color * tinte
			mi.set_surface_override_material(s, mat)


static func _aplicar_figura(avatar: Node, d: Dictionary) -> void:
	var modelo := _modelo(avatar)
	if modelo == null:
		return
	var sk := _esqueleto(avatar)
	var idx: Dictionary = _indices_huesos(sk) if sk != null else {}
	var cuerpo := _buscar_cuerpo(avatar, idx)
	var pestanas := _buscar_malla(avatar, "eyelas")
	var geo: Dictionary = {}
	if cuerpo != null and cuerpo.mesh != null and sk != null:
		geo = _geometria(cuerpo.mesh, pestanas.mesh if pestanas != null else null, idx)

	# La malla de algunos GLB no esta en metros, asi que la altura se mide en
	# el esqueleto (HeadTop_End en reposo) y se cachea a escala base.
	var altura_base: float = avatar.get_meta("pers_altura_base", 0.0)
	if altura_base <= 0.0:
		altura_base = _altura_base_mundo(avatar, sk)
		avatar.set_meta("pers_altura_base", altura_base)
	var escala0: Vector3 = avatar.get_meta("pers_escala_base", modelo.scale)
	avatar.set_meta("pers_escala_base", escala0)
	var f: float = (altura_base + float(d["altura_cm"]) / 100.0) / maxf(altura_base, 0.01)
	modelo.scale = Vector3(escala0.x * f * d["ancho"], escala0.y * f, escala0.z * f * d["ancho"])

	if sk != null:
		var i := _hueso(sk, "Head")
		if i >= 0:
			sk.set_bone_pose_scale(i, Vector3.ONE * float(d["cabeza"]))

	if geo.is_empty():
		return
	var hay_cara := float(d["nariz"]) > 0.001 or float(d["labios"]) > 0.001 \
		or float(d["orejas"]) > 0.001 or float(d["ojos"]) > 0.001
	var hay_cuerpo := absf(float(d["torso"]) - 1.0) > 0.001 or absf(float(d["hombros"]) - 1.0) > 0.001 \
		or absf(float(d["brazos"]) - 1.0) > 0.001 or absf(float(d["piernas"]) - 1.0) > 0.001
	var firma := ""
	for clave in ROSTRO + ["hombros", "torso", "brazos", "piernas"]:
		firma += "%.3f|" % d[clave]
	if avatar.get_meta("pers_firma_mallas", "") == firma:
		return
	avatar.set_meta("pers_firma_mallas", firma)
	_reconstruir_mallas(avatar, sk, geo, d, hay_cara, hay_cuerpo, cuerpo)


## Varios avatares agrupan cuerpo, ropa y pelo en una sola malla con varias
## superficies; cada superficie se clasifica por separado.
static func _reconstruir_mallas(avatar: Node, sk: Skeleton3D, geo: Dictionary, d: Dictionary,
		hay_cara: bool, hay_cuerpo: bool, cuerpo: MeshInstance3D) -> void:
	var idx := _indices_huesos(sk)
	var ojos := float(d["ojos"]) > 0.001
	for nodo in avatar.find_children("*", "MeshInstance3D", true, false):
		var mi := nodo as MeshInstance3D
		if mi.mesh == null:
			continue
		var base: Mesh = mi.get_meta("pers_mesh_base", mi.mesh)
		mi.set_meta("pers_mesh_base", base)

		var trabajo := false
		for s in base.get_surface_count():
			var parte := _parte_superficie(mi, s)
			if parte == "" and mi == cuerpo:
				parte = "piel"
			if (hay_cara and parte == "piel") or (hay_cara and ojos and _es_pestanas(mi, s)) \
					or (hay_cuerpo and parte in ["piel", "camiseta", "pantalon", "zapatillas"]):
				trabajo = true
				break
		if not trabajo:
			if mi.mesh != base:
				mi.mesh = base
			continue

		var nueva := ArrayMesh.new()
		for s in base.get_surface_count():
			var parte := _parte_superficie(mi, s)
			if parte == "" and mi == cuerpo:
				parte = "piel"
			var es_pestanas := hay_cara and ojos and _es_pestanas(mi, s)
			var usar_cara := hay_cara and parte == "piel"
			var usar_cuerpo := hay_cuerpo and parte in ["piel", "camiseta", "pantalon", "zapatillas"]
			var origen: Array = _arreglos_originales(base, s)
			var arreglos := origen.duplicate()
			if usar_cara or usar_cuerpo or es_pestanas:
				var verts: PackedVector3Array = (origen[Mesh.ARRAY_VERTEX] as PackedVector3Array).duplicate()
				var mascaras := _mascaras_de(base, s, idx)
				var peso_cabeza: PackedFloat32Array = mascaras["cabeza"]
				for v in verts.size():
					var p: Vector3 = verts[v]
					if es_pestanas:
						p = _deformar_pestanas(p, d, geo)
					elif usar_cara:
						p = _deformar_rostro(p, peso_cabeza[v] if v < peso_cabeza.size() else 0.0, d, geo)
					if usar_cuerpo:
						p = _deformar_cuerpo_punto(p, mascaras, v, d, geo)
					verts[v] = p
				arreglos[Mesh.ARRAY_VERTEX] = verts
			nueva.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arreglos)
			nueva.surface_set_material(s, base.surface_get_material(s))
		mi.mesh = nueva


# ---------------------------------------------------------------------------
# Deformacion del rostro (espacio de reposo, UV y skin intactos)
# ---------------------------------------------------------------------------

static func _deformar_rostro(p: Vector3, w_cabeza: float, d: Dictionary, geo: Dictionary) -> Vector3:
	if w_cabeza <= 0.01:
		return p
	var anclas: Dictionary = geo["anclas"]
	var t_nariz := float(d["nariz"])
	var t_labios := float(d["labios"])
	var t_orejas := float(d["orejas"])
	var t_ojos := float(d["ojos"])

	if t_ojos > 0.001:
		var ojo: Vector3 = anclas["ojo_l"] if p.x <= anclas["x"] else anclas["ojo_r"]
		var w := _campo(p, ojo, anclas["r_ojo"]) * w_cabeza
		if w > 0.0:
			var f := 1.0 + 0.26 * t_ojos * w
			p.x = ojo.x + (p.x - ojo.x) * f
			p.y = ojo.y + (p.y - ojo.y) * f
			p.z += 0.003 * t_ojos * w

	if t_nariz > 0.001:
		var w := _campo(p, anclas["nariz"], anclas["r_nariz"]) * w_cabeza
		if w > 0.0:
			p.x = anclas["nariz"].x + (p.x - anclas["nariz"].x) * (1.0 + 0.28 * t_nariz * w)
			p.y = anclas["nariz"].y + (p.y - anclas["nariz"].y) * (1.0 + 0.20 * t_nariz * w)
			p.z += 0.012 * t_nariz * w

	if t_labios > 0.001:
		var w := _campo(p, anclas["labios"], anclas["r_labios"]) * w_cabeza
		if w > 0.0:
			p.x = anclas["labios"].x + (p.x - anclas["labios"].x) * (1.0 + 0.50 * t_labios * w)
			p.y = anclas["labios"].y + (p.y - anclas["labios"].y) * (1.0 + 0.62 * t_labios * w)
			p.z += 0.012 * t_labios * w

	if t_orejas > 0.001:
		var oreja: Vector3 = anclas["oreja_l"] if p.x <= anclas["x"] else anclas["oreja_r"]
		var w := _campo(p, oreja, anclas["r_oreja"]) * w_cabeza
		if w > 0.0:
			var signo := -1.0 if p.x <= anclas["x"] else 1.0
			p.x += signo * 0.012 * t_orejas * w
			p.y = oreja.y + (p.y - oreja.y) * (1.0 + 0.30 * t_orejas * w)
			p.z = oreja.z + (p.z - oreja.z) * (1.0 + 0.26 * t_orejas * w)

	return p


static func _deformar_pestanas(p: Vector3, d: Dictionary, geo: Dictionary) -> Vector3:
	var t := float(d["ojos"])
	if t <= 0.001:
		return p
	var anclas: Dictionary = geo["anclas"]
	var ojo: Vector3 = anclas["ojo_l"] if p.x <= anclas["x"] else anclas["ojo_r"]
	var w := _campo(p, ojo, anclas["r_pestana"])
	if w <= 0.0:
		return p
	var f := 1.0 + 0.32 * t * w
	p.x = ojo.x + (p.x - ojo.x) * f
	p.y = ojo.y + (p.y - ojo.y) * f
	return p


# ---------------------------------------------------------------------------
# Proporciones del cuerpo por zonas de la malla (sin tocar huesos)
# ---------------------------------------------------------------------------

static func _deformar_cuerpo_punto(p: Vector3, mascaras: Dictionary, v: int, d: Dictionary, geo: Dictionary) -> Vector3:
	var x0: float = geo["x"]
	var t_hombros := float(d["hombros"])
	var t_torso := float(d["torso"])
	var t_brazos := float(d["brazos"])
	var t_piernas := float(d["piernas"])

	var w_torso: PackedFloat32Array = mascaras["torso"]
	var w_hombro: PackedFloat32Array = mascaras["hombro"]
	var w_brazo: PackedFloat32Array = mascaras["brazo"]
	var w_pierna: PackedFloat32Array = mascaras["pierna"]

	var wt: float = w_torso[v] if v < w_torso.size() else 0.0
	if wt > 0.0 and absf(t_torso - 1.0) > 0.0001:
		var fz: float = geo["torso_z"]
		var f := 1.0 + (t_torso - 1.0) * wt
		p.x = x0 + (p.x - x0) * f
		p.z = fz + (p.z - fz) * f

	var wh: float = w_hombro[v] if v < w_hombro.size() else 0.0
	if wh > 0.0 and absf(t_hombros - 1.0) > 0.0001:
		p.x = x0 + (p.x - x0) * (1.0 + (t_hombros - 1.0) * wh)

	var wa: float = w_brazo[v] if v < w_brazo.size() else 0.0
	if wa > 0.0 and absf(t_brazos - 1.0) > 0.0001:
		var c: Vector2 = geo["brazo_l"] if p.x >= x0 else geo["brazo_r"]
		var f := 1.0 + (t_brazos - 1.0) * wa
		p.x = c.x + (p.x - c.x) * f
		p.z = c.y + (p.z - c.y) * f

	var wp: float = w_pierna[v] if v < w_pierna.size() else 0.0
	if wp > 0.0 and absf(t_piernas - 1.0) > 0.0001:
		var c: Vector2 = geo["pierna_l"] if p.x >= x0 else geo["pierna_r"]
		var f := 1.0 + (t_piernas - 1.0) * wp
		p.x = c.x + (p.x - c.x) * f
		p.z = c.y + (p.z - c.y) * f

	return p


# ---------------------------------------------------------------------------
# Geometria de referencia (cacheada por recurso de malla)
# ---------------------------------------------------------------------------

static func _geometria(cuerpo: Mesh, pestanas: Mesh, idx: Dictionary) -> Dictionary:
	var clave := cuerpo.get_instance_id()
	if _cache_geo.has(clave):
		return _cache_geo[clave]

	var s_ancla := _superficie_cabeza(cuerpo, idx)
	if s_ancla < 0:
		return {}
	var arr := _arreglos_originales(cuerpo, s_ancla)
	var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var huesos: PackedInt32Array = arr[Mesh.ARRAY_BONES]
	var pesos: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
	var i_cabeza: int = idx.get("Head", -1)

	var caja := AABB()
	var n := 0
	for v in verts.size():
		if _peso_de(huesos, pesos, v, i_cabeza) < 0.5:
			continue
		if n == 0:
			caja = AABB(verts[v], Vector3.ZERO)
		else:
			caja = caja.expand(verts[v])
		n += 1
	if n == 0:
		return {}

	# La altura visible es la coronilla real de la superficie, no el borde de
	# los vertices con peso alto en Head (que puede quedarse corto).
	var altura_top := -1e9
	for p in verts:
		altura_top = maxf(altura_top, p.y)

	var x0 := caja.position.x + caja.size.x * 0.5
	var y0 := caja.position.y
	var h := maxf(caja.size.y, 0.001)
	var mitad := caja.size.x * 0.5

	var z_labios := -1e9
	var z_nariz := -1e9
	var suma_z_orejas := 0.0
	var n_orejas := 0
	for v in verts.size():
		if _peso_de(huesos, pesos, v, i_cabeza) < 0.5:
			continue
		var p := verts[v]
		var ny := (p.y - y0) / h
		var dx := absf(p.x - x0)
		if ny > 0.18 and ny < 0.34 and dx < mitad * 0.24:
			z_labios = maxf(z_labios, p.z)
		if ny > 0.30 and ny < 0.46 and dx < mitad * 0.20:
			z_nariz = maxf(z_nariz, p.z)
		if ny > 0.40 and ny < 0.62 and dx > mitad * 0.80:
			suma_z_orejas += p.z
			n_orejas += 1
	if z_labios < -1e8:
		z_labios = caja.get_center().z
	if z_nariz < -1e8:
		z_nariz = z_labios
	var z_orejas := caja.get_center().z
	if n_orejas > 0:
		z_orejas = suma_z_orejas / float(n_orejas)

	var ojo_y := y0 + h * 0.52
	var ojo_x := 0.70 * mitad
	var ojo_z := caja.get_center().z + caja.size.z * 0.35
	var r_ojo := Vector3(mitad * 0.55, h * 0.10, 0.055)
	var r_pestana := Vector3(mitad * 0.70, h * 0.10, 0.055)
	if pestanas != null:
		var pbb := pestanas.get_aabb()
		var pc := pbb.get_center()
		ojo_y = pc.y
		ojo_x = 0.70 * pbb.size.x * 0.5
		ojo_z = pc.z - 0.004
		r_ojo = Vector3(maxf(pbb.size.x * 0.30, 0.018), maxf(pbb.size.y * 1.4, 0.018), 0.055)
		r_pestana = Vector3(maxf(pbb.size.x * 0.55, 0.03), maxf(pbb.size.y * 1.4, 0.018), 0.055)

	var anclas := {
		"x": x0,
		"labios": Vector3(x0, y0 + h * 0.27, z_labios - 0.004),
		"nariz": Vector3(x0, y0 + h * 0.37, z_nariz - 0.004),
		"ojo_l": Vector3(x0 - ojo_x, ojo_y, ojo_z),
		"ojo_r": Vector3(x0 + ojo_x, ojo_y, ojo_z),
		"oreja_l": Vector3(x0 - mitad * 0.92, y0 + h * 0.50, z_orejas),
		"oreja_r": Vector3(x0 + mitad * 0.92, y0 + h * 0.50, z_orejas),
		"r_labios": Vector3(mitad * 0.34, h * 0.075, 0.055),
		"r_nariz": Vector3(mitad * 0.22, h * 0.105, 0.055),
		"r_ojo": r_ojo,
		"r_pestana": r_pestana,
		"r_oreja": Vector3(mitad * 0.26, h * 0.155, 0.09),
	}

	# Centros de brazos y piernas para escalar su grosor sin mover el resto.
	var mascaras := _mascaras_de(cuerpo, s_ancla, idx)
	var brazo_l := Vector2.ZERO
	var brazo_r := Vector2.ZERO
	var pierna_l := Vector2.ZERO
	var pierna_r := Vector2.ZERO
	var nb_l := 0
	var nb_r := 0
	var np_l := 0
	var np_r := 0
	var suma_z_torso := 0.0
	var n_torso := 0
	var m_brazo: PackedFloat32Array = mascaras["brazo"]
	var m_pierna: PackedFloat32Array = mascaras["pierna"]
	var m_torso: PackedFloat32Array = mascaras["torso"]
	for v in verts.size():
		var p := verts[v]
		if v < m_torso.size() and m_torso[v] > 0.5:
			suma_z_torso += p.z
			n_torso += 1
		if v < m_brazo.size() and m_brazo[v] > 0.5:
			if p.x >= x0:
				brazo_l += Vector2(p.x, p.z)
				nb_l += 1
			else:
				brazo_r += Vector2(p.x, p.z)
				nb_r += 1
		if v < m_pierna.size() and m_pierna[v] > 0.5:
			if p.x >= x0:
				pierna_l += Vector2(p.x, p.z)
				np_l += 1
			else:
				pierna_r += Vector2(p.x, p.z)
				np_r += 1
	if nb_l > 0:
		brazo_l /= float(nb_l)
	if nb_r > 0:
		brazo_r /= float(nb_r)
	if np_l > 0:
		pierna_l /= float(np_l)
	if np_r > 0:
		pierna_r /= float(np_r)
	if nb_l == 0:
		brazo_l = Vector2(x0 + mitad, 0.0)
	if nb_r == 0:
		brazo_r = Vector2(x0 - mitad, 0.0)
	if np_l == 0:
		pierna_l = Vector2(x0 + mitad * 0.5, 0.0)
	if np_r == 0:
		pierna_r = Vector2(x0 - mitad * 0.5, 0.0)

	var geo := {
		"x": x0,
		"altura": altura_top if altura_top > -1e8 else y0 + h,
		"torso_z": suma_z_torso / float(n_torso) if n_torso > 0 else caja.get_center().z,
		"brazo_l": brazo_l,
		"brazo_r": brazo_r,
		"pierna_l": pierna_l,
		"pierna_r": pierna_r,
		"anclas": anclas,
	}
	_cache_geo[clave] = geo
	return geo


static func _mascaras_de(mesh: Mesh, s: int, idx: Dictionary) -> Dictionary:
	var clave := mesh.get_instance_id()
	var por_malla: Array = _cache_mascaras.get(clave, [])
	if por_malla.is_empty():
		for i in mesh.get_surface_count():
			por_malla.append(null)
		_cache_mascaras[clave] = por_malla
	if por_malla[s] != null:
		return por_malla[s]

	var arr := _arreglos_originales(mesh, s)
	var huesos: PackedInt32Array = arr[Mesh.ARRAY_BONES]
	var pesos: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
	var n := (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
	var cabeza := PackedFloat32Array()
	var torso := PackedFloat32Array()
	var hombro := PackedFloat32Array()
	var brazo := PackedFloat32Array()
	var pierna := PackedFloat32Array()
	cabeza.resize(n)
	torso.resize(n)
	hombro.resize(n)
	brazo.resize(n)
	pierna.resize(n)

	var i_cabeza: int = idx.get("Head", -1)
	var i_spine: int = idx.get("Spine", -1)
	var i_spine1: int = idx.get("Spine1", -1)
	var i_spine2: int = idx.get("Spine2", -1)
	var i_sh_l: int = idx.get("LeftShoulder", -1)
	var i_sh_r: int = idx.get("RightShoulder", -1)
	var i_arm_l: int = idx.get("LeftArm", -1)
	var i_arm_r: int = idx.get("RightArm", -1)
	var i_fa_l: int = idx.get("LeftForeArm", -1)
	var i_fa_r: int = idx.get("RightForeArm", -1)
	var i_ul_l: int = idx.get("LeftUpLeg", -1)
	var i_ul_r: int = idx.get("RightUpLeg", -1)
	var i_lg_l: int = idx.get("LeftLeg", -1)
	var i_lg_r: int = idx.get("RightLeg", -1)

	for v in n:
		var wc := 0.0
		var wt := 0.0
		var wh := 0.0
		var wa := 0.0
		var wp := 0.0
		for k in 4:
			var pos := v * 4 + k
			if pos >= huesos.size():
				break
			var h := huesos[pos]
			var w := pesos[pos] if pos < pesos.size() else 0.0
			if h == i_cabeza:
				wc += w
			elif h == i_spine or h == i_spine1 or h == i_spine2:
				wt += w
			elif h == i_sh_l or h == i_sh_r:
				wh += w
			elif h == i_arm_l or h == i_arm_r or h == i_fa_l or h == i_fa_r:
				wa += w
			elif h == i_ul_l or h == i_ul_r or h == i_lg_l or h == i_lg_r:
				wp += w
		cabeza[v] = minf(wc, 1.0)
		torso[v] = minf(wt, 1.0)
		hombro[v] = minf(wh, 1.0)
		brazo[v] = minf(wa, 1.0)
		pierna[v] = minf(wp, 1.0)

	var mascaras := {
		"cabeza": cabeza,
		"torso": torso,
		"hombro": hombro,
		"brazo": brazo,
		"pierna": pierna,
	}
	por_malla[s] = mascaras
	return mascaras


static func _arreglos_originales(mesh: Mesh, s: int) -> Array:
	var clave := mesh.get_instance_id()
	var por_malla: Array = _cache_arreglos.get(clave, [])
	if por_malla.is_empty():
		for i in mesh.get_surface_count():
			por_malla.append(null)
		_cache_arreglos[clave] = por_malla
	if por_malla[s] == null:
		por_malla[s] = mesh.surface_get_arrays(s)
	return por_malla[s]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

static func _campo(p: Vector3, centro: Vector3, radio: Vector3) -> float:
	var q := Vector3(
		(p.x - centro.x) / maxf(radio.x, 0.0001),
		(p.y - centro.y) / maxf(radio.y, 0.0001),
		(p.z - centro.z) / maxf(radio.z, 0.0001))
	return 1.0 - smoothstep(0.30, 1.0, q.length())


static func _peso_de(huesos: PackedInt32Array, pesos: PackedFloat32Array, v: int, hueso: int) -> float:
	var w := 0.0
	for k in 4:
		var pos := v * 4 + k
		if pos >= huesos.size():
			break
		if huesos[pos] == hueso:
			w += pesos[pos] if pos < pesos.size() else 0.0
	return w


static func _indices_huesos(sk: Skeleton3D) -> Dictionary:
	var nombres := ["Head", "Spine", "Spine1", "Spine2", "LeftShoulder", "RightShoulder",
		"LeftArm", "RightArm", "LeftForeArm", "RightForeArm",
		"LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg"]
	var d := {}
	for base in nombres:
		d[base] = _hueso(sk, base)
	return d


## Los 24 avatares usan prefijos distintos (mixamorig_, mixamorig7_, ...) y
## algunos exportan además los huesos de control de Blender (Ctrl_Head), asi
## que se busca por sufijo y se prefiere el hueso Mixamo real.
static func _hueso(sk: Skeleton3D, base: String) -> int:
	var buscado := base.to_lower()
	var mejor := -1
	var puntos := -1
	for i in sk.get_bone_count():
		var n := sk.get_bone_name(i).to_lower()
		if n != buscado and not n.ends_with("_" + buscado):
			continue
		if n.begins_with("ctrl") or n.contains("_fk_") or n.contains("_ik_"):
			continue
		var p := 0
		if n.begins_with("mixamorig"):
			p += 4
		if n == buscado:
			p += 2
		if p > puntos:
			puntos = p
			mejor = i
	return mejor


## Malla que contiene el cuerpo y la cabeza. El peso en Head descarta pelo y
## ropa, y "piel" desempata frente a mallas fusionadas (Lola, Ch18, Ch12...)
## cuyo nombre no dice "body".
static func _buscar_cuerpo(avatar: Node, idx: Dictionary) -> MeshInstance3D:
	var mejor: MeshInstance3D = null
	var mejor_puntos := -1
	var mejor_cabeza := -1
	var mejor_vert := -1
	for nodo in avatar.find_children("*", "MeshInstance3D", true, false):
		var mi := nodo as MeshInstance3D
		if mi.mesh == null or mi.mesh.get_surface_count() == 0:
			continue
		var cabezas := _cuenta_cabeza(mi.mesh, idx)
		if cabezas == 0:
			continue
		var parte := _parte(mi.name)
		var puntos := 2 if parte == "piel" else (1 if parte == "" else 0)
		var verts := _cuenta_vertices(mi.mesh)
		if puntos > mejor_puntos or (puntos == mejor_puntos and cabezas > mejor_cabeza) \
				or (puntos == mejor_puntos and cabezas == mejor_cabeza and verts > mejor_vert):
			mejor = mi
			mejor_puntos = puntos
			mejor_cabeza = cabezas
			mejor_vert = verts
	if mejor != null:
		return mejor
	var por_nombre := _buscar_malla(avatar, "body")
	return por_nombre if por_nombre != null else _malla_mayor(avatar)


static func _malla_mayor(avatar: Node) -> MeshInstance3D:
	var mejor: MeshInstance3D = null
	var mejor_vert := -1
	for nodo in avatar.find_children("*", "MeshInstance3D", true, false):
		var mi := nodo as MeshInstance3D
		if mi.mesh == null or mi.mesh.get_surface_count() == 0:
			continue
		var verts := _cuenta_vertices(mi.mesh)
		if verts > mejor_vert:
			mejor = mi
			mejor_vert = verts
	return mejor


## Superficie de la malla del cuerpo con mas vertices de cabeza: es la que
## define altura, anclajes faciales y mascaras del resto del cuerpo.
static func _superficie_cabeza(mesh: Mesh, idx: Dictionary) -> int:
	var i_cabeza: int = idx.get("Head", -1)
	if i_cabeza < 0:
		return -1
	var mejor := -1
	var mejor_n := 0
	for s in mesh.get_surface_count():
		var n := _vertices_cabeza(mesh, s, i_cabeza)
		if n > mejor_n:
			mejor_n = n
			mejor = s
	return mejor


static func _cuenta_cabeza(mesh: Mesh, idx: Dictionary) -> int:
	var i_cabeza: int = idx.get("Head", -1)
	if i_cabeza < 0:
		return 0
	var clave := "%d:%d" % [mesh.get_instance_id(), i_cabeza]
	if _cache_cabeza.has(clave):
		return _cache_cabeza[clave]
	var n := 0
	for s in mesh.get_surface_count():
		n += _vertices_cabeza(mesh, s, i_cabeza)
	_cache_cabeza[clave] = n
	return n


static func _vertices_cabeza(mesh: Mesh, s: int, i_cabeza: int) -> int:
	var arr := _arreglos_originales(mesh, s)
	var huesos: PackedInt32Array = arr[Mesh.ARRAY_BONES]
	var pesos: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
	var n := 0
	for v in (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size():
		if _peso_de(huesos, pesos, v, i_cabeza) >= 0.5:
			n += 1
	return n


static func _cuenta_vertices(mesh: Mesh) -> int:
	var clave := mesh.get_instance_id()
	if _cache_vertices.has(clave):
		return _cache_vertices[clave]
	var n := 0
	for s in mesh.get_surface_count():
		n += (mesh.surface_get_arrays(s)[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
	_cache_vertices[clave] = n
	return n


## Clasifica una superficie: primero por nombre de malla y, si no dice nada,
## por nombre de material. Las pestanas siempre cuentan como pelo.
static func _parte_superficie(mi: MeshInstance3D, s: int) -> String:
	var mat := mi.mesh.surface_get_material(s)
	var nombre_mat := String(mat.resource_name) if mat != null else ""
	if String(mi.name).to_lower().contains("eyelas") or nombre_mat.to_lower().contains("eyelas"):
		return "pelo"
	var parte := _parte(mi.name)
	if parte != "":
		return parte
	return _parte(nombre_mat)


static func _es_pestanas(mi: MeshInstance3D, s: int) -> bool:
	if String(mi.name).to_lower().contains("eyelas"):
		return true
	var mat := mi.mesh.surface_get_material(s)
	return mat != null and String(mat.resource_name).to_lower().contains("eyelas")


## Altura real del avatar sobre su propio origen, tomada del hueso de la
## coronilla en reposo (la animacion no la altera) y sin depender de la
## posicion del avatar en la escena.
static func _altura_base_mundo(avatar: Node, sk: Skeleton3D) -> float:
	if sk == null:
		return ALTURA_REFERENCIA
	var i := _hueso(sk, "HeadTop_End")
	var extra := 0.0
	if i < 0:
		i = _hueso(sk, "Head")
		extra = 0.12
	if i < 0:
		return ALTURA_REFERENCIA
	# Se compone con transformaciones LOCALES: esto se llama antes de que el avatar
	# entre en el árbol (Boot -> set_player_avatar) y global_transform lanzaría
	# "!is_inside_tree()" dejando la altura a 0 y el avatar sin escalar.
	var xf := Transform3D.IDENTITY
	var nodo: Node = sk
	while nodo != null and nodo != avatar:
		if nodo is Node3D:
			xf = (nodo as Node3D).transform * xf
		nodo = nodo.get_parent()
	var punto: Vector3 = xf * sk.get_bone_global_rest(i).origin
	return maxf(punto.y + extra, 0.5)


static func _esqueleto(avatar: Node) -> Skeleton3D:
	for sk in avatar.find_children("*", "Skeleton3D", true, false):
		return sk as Skeleton3D
	return null


static func _buscar_malla(avatar: Node, trozo: String) -> MeshInstance3D:
	for nodo in avatar.find_children("*", "MeshInstance3D", true, false):
		var mi := nodo as MeshInstance3D
		if String(mi.name).to_lower().contains(trozo):
			return mi
	return null


static func _modelo(avatar: Node) -> Node3D:
	for sk in avatar.find_children("*", "Skeleton3D", true, false):
		var padre := sk.get_parent()
		if padre is Node3D:
			return padre as Node3D
	return null


## Clasifica la malla por nombre. Los nombres vienen del GLB (Ch01_Body,
## Ch21_Hair, Ch23_Suit...), asi que la regla es por palabra contenida.
static func _parte(nombre: String) -> String:
	var n := nombre.to_lower()
	if n.contains("hair") or n.contains("eyelas") or n.contains("helmet") or n.contains("hat") or n.contains("cap"):
		return "pelo"
	if n.contains("shoe") or n.contains("sneaker") or n.contains("boot") or n.contains("zapat"):
		return "zapatillas"
	if n.contains("pant") or n.contains("jean") or n.contains("belt") or n.contains("skirt") or n.contains("short"):
		return "pantalon"
	if n.contains("shirt") or n.contains("suit") or n.contains("jacket") or n.contains("top") or n.contains("dress") or n.contains("blouse"):
		return "camiseta"
	if n.contains("body") or n.contains("skin") or n.contains("head"):
		return "piel"
	return ""
