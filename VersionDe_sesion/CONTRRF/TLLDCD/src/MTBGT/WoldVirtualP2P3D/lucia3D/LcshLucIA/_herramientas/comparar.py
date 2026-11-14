from PIL import Image, ImageDraw, ImageFont
import os

BASE = r"C:\Users\User\Desktop\LcshLucIA\_pruebas"
filas = [
    ("Reposo / IDLE", "Hombros inflados y axila rota (pesos por radio)",
     "Brazos y chaqueta deforman de forma natural (skin Mixamo)"),
    ("Gesto al hablar", "Manga clavada al torso: el brazo no sigue",
     "El brazo y el codo acompañan el gesto"),
    ("Cabeza girada 0,35 rad", "El cuello y el cuello de la chaqueta se estiran",
     "La cabeza gira sin arrastrar el torso"),
    ("Boca abierta (lipsync)", "Hueco blanco: la boca no tiene interior",
     "Óvalo oscuro anclado al morro real"),
]
imagenes = [
    ("antes/02_idle_reposo.png", "despues/01_reposo_t0.png"),
    ("antes/04_gesto_t11.png", "despues/03_hablando_t1.png"),
    ("antes/08_cabeza_giro.png", "despues/10_cabeza_giro.png"),
    ("rig/08_retrato_boca.png", "despues/05_boca_abierta.png"),
]

ANCHO_CELDA = 430
MARGEN = 18
ALTO_TITULO = 64
ALTO_PIE = 58

def fuente(tam):
    for ruta in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tam)
    return ImageFont.load_default()

f_titulo = fuente(26)
f_etiqueta = fuente(17)
f_pie = fuente(14)

# Cargar y escalar
celdas = []
for antes, despues in imagenes:
    par = []
    for ruta in (antes, despues):
        img = Image.open(os.path.join(BASE, ruta)).convert("RGB")
        alto = int(img.height * ANCHO_CELDA / img.width)
        par.append(img.resize((ANCHO_CELDA, alto), Image.LANCZOS))
    celdas.append(par)

alto_celda = celdas[0][0].height
ancho_total = MARGEN * 3 + ANCHO_CELDA * 2
alto_total = ALTO_TITULO + len(celdas) * (alto_celda + ALTO_PIE + MARGEN) + MARGEN

lienzo = Image.new("RGB", (ancho_total, alto_total), (18, 20, 26))
dibujo = ImageDraw.Draw(lienzo)
dibujo.text((MARGEN, 16), "LucIA 3D · antes / después del rigging con esqueleto Mixamo",
            font=f_titulo, fill=(235, 238, 245))

y = ALTO_TITULO
for (titulo, texto_antes, texto_despues), par in zip(filas, celdas):
    for col, (img, texto) in enumerate(zip(par, (texto_antes, texto_despues))):
        x = MARGEN + col * (ANCHO_CELDA + MARGEN)
        lienzo.paste(img, (x, y))
        color = (255, 130, 120) if col == 0 else (130, 235, 160)
        etiqueta = "ANTES" if col == 0 else "DESPUÉS"
        dibujo.rectangle([x, y, x + ANCHO_CELDA, y + 26], fill=(0, 0, 0))
        dibujo.text((x + 8, y + 4), f"{etiqueta} · {titulo}", font=f_etiqueta, fill=color)
        # pie de foto partido en dos líneas si hace falta
        palabras = texto.split()
        lineas = []
        actual = ""
        for p in palabras:
            prueba = (actual + " " + p).strip()
            if dibujo.textlength(prueba, font=f_pie) > ANCHO_CELDA - 12:
                lineas.append(actual)
                actual = p
            else:
                actual = prueba
        lineas.append(actual)
        for i, linea in enumerate(lineas[:2]):
            dibujo.text((x + 6, y + alto_celda + 4 + i * 18), linea, font=f_pie,
                        fill=(170, 175, 190))
    y += alto_celda + ALTO_PIE + MARGEN

salida = os.path.join(BASE, "comparacion.png")
lienzo.save(salida)
print("guardado", salida, lienzo.size)
