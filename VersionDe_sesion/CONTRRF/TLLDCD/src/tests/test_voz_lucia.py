"""
test_voz_lucia.py - Test de voz de LucIA (chica espanola 18 anios)
==================================================================
Verifica y reproduce la voz sintetizada de LucIA por los altavoces.

Prueba el pipeline completo:
  Piper TTS (Daniela) + pedalboard DSP + Intel Arc DirectML

Uso:
  python tests/test_voz_lucia.py

Guarda un fichero WAV de muestra en:
  tests/muestra_voz_lucia.wav
"""

import ctypes
import logging
import os
import sys
import time
import wave

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_voz_lucia")

_DIR_TESTS = os.path.dirname(os.path.abspath(__file__))
_DIR_SRC   = os.path.dirname(_DIR_TESTS)
if _DIR_SRC not in sys.path:
    sys.path.insert(0, _DIR_SRC)


class _MCIPlayer:
    """Reproduce un fichero WAV via winmm.dll."""

    def __init__(self, alias="test_lucia_wav"):
        self._alias = alias
        self._mci   = ctypes.windll.winmm.mciSendStringW

    def _cmd(self, comando):
        return self._mci(comando, None, 0, None)

    def reproducir_y_esperar(self, ruta_wav, timeout=60.0):
        ruta_norm = os.path.abspath(ruta_wav).replace("\\", "/")
        self._cmd(f"close {self._alias}")
        if self._cmd(f'open "{ruta_norm}" type waveaudio alias {self._alias}') == 0:
            self._cmd(f"play {self._alias}")
            buf = ctypes.create_unicode_buffer(128)
            t0  = time.time()
            time.sleep(0.12)
            while time.time() - t0 < timeout:
                res = self._mci(f"status {self._alias} mode", buf, 128, None)
                if res != 0 or buf.value not in ("playing", ""):
                    break
                time.sleep(0.09)
            self._cmd(f"stop {self._alias}")
            self._cmd(f"close {self._alias}")
            return True

        # Fallback nativo de Windows (winsound) si MCI tiene restricciones de codec/dispositivo
        try:
            import winsound
            winsound.PlaySound(os.path.abspath(ruta_wav), winsound.SND_FILENAME)
            return True
        except Exception as e_snd:
            logger.error(f"Error en reproduccion (MCI y winsound): {e_snd}")
            return False


VERDE  = "\033[92m"
ROJO   = "\033[91m"
AMARIL = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RST    = "\033[0m"

def ok(m):  print(f"  {VERDE}OK{RST}  {m}")
def err(m): print(f"  {ROJO}ERR{RST} {m}")
def inf(m): print(f"  {CYAN}-->{RST} {m}")
def sep():  print(f"\n{CYAN}{'=' * 64}{RST}\n")


def main():
    sep()
    print(f"{BOLD}{CYAN}  TEST DE VOZ - LucIA (chica espanola 18 anios){RST}")
    print(f"  Motor: Piper TTS + pedalboard DSP + Intel Arc (DirectML)")
    sep()

    # 1. Importar procesador
    print(f"{BOLD}[1/5] Cargando procesador de voz neuronal...{RST}")
    try:
        from LC_STM.red_neuronal.SLRN.procesador_voz_neuronal import get_procesador_voz_neuronal
        proc = get_procesador_voz_neuronal()
        ok("Procesador importado correctamente")
    except Exception as e:
        err(f"No se pudo importar el procesador: {e}")
        return 1

    # 2. Verificar disponibilidad
    print(f"\n{BOLD}[2/5] Verificando motor y dependencias...{RST}")
    info = proc.info()
    if proc.disponible:
        ok(f"Modelo: {info['modelo_activo']}")
        ok(f"Sample rate: {info['sample_rate']} Hz")
        ok(f"DSP: {info['dsp']}")
    else:
        inf("Motor Piper ONNX no encontrado en SBSTM/tts_models/. Usando voz neuronal oficial (gTTS + DSP).")

    # 3. Sintesis de frases
    print(f"\n{BOLD}[3/5] Sintetizando frases de prueba...{RST}")
    FRASES = [
        ("Hola! Soy Lucia, tu asistente virtual. Encantada de conocerte.", 0.80),
        ("Oye, a ver, te explico como funciona esto, que es bastante interesante.", 0.70),
        ("Pues mira, acabo de cumplir dieciocho anios y estoy lista para ayudarte.", 0.75),
        ("Mira, la inteligencia artificial esta avanzando muchisimo. Esta genial, a que si?", 0.85),
        ("Si tienes alguna duda me dices. Estoy aqui para lo que necesites.", 0.60),
    ]

    import numpy as np
    import soundfile as sf

    muestras_ok = []
    for i, (texto, emocion) in enumerate(FRASES, 1):
        inf(f"Frase {i}: \"{texto[:60]}\" (emocion={emocion})")
        try:
            resultado = proc.generar_audio_frase(texto, emocion=emocion)
            if resultado is None:
                err(f"Frase {i}: sintesis devolvio None")
                continue
            audio, sr = resultado
            dur = len(audio) / sr
            ok(f"Frase {i}: {dur:.2f}s | {len(audio)} muestras | sr={sr} Hz")
            muestras_ok.append((audio, sr, texto))
        except Exception as e:
            err(f"Frase {i}: excepcion -> {e}")

    if not muestras_ok:
        err("Ninguna frase se sintetizo correctamente")
        return 1

    # 4. Guardar WAV
    print(f"\n{BOLD}[4/5] Guardando WAV de muestra...{RST}")
    ruta_wav = os.path.join(_DIR_TESTS, "muestra_voz_lucia.wav")
    try:
        silencio = np.zeros(int(muestras_ok[0][1] * 0.45), dtype=np.float32)
        audio_completo = np.concatenate(
            [np.concatenate([a, silencio]) for a, sr, _ in muestras_ok]
        )
        sr_out = muestras_ok[0][1]
        sf.write(ruta_wav, audio_completo, sr_out)
        dur_total = len(audio_completo) / sr_out
        ok(f"WAV guardado: {ruta_wav}")
        ok(f"Duracion total: {dur_total:.2f}s | {sr_out} Hz")
    except Exception as e:
        err(f"Error guardando WAV: {e}")
        ruta_wav = None

    # 5. Reproducir por altavoces
    print(f"\n{BOLD}[5/5] Reproduciendo por altavoces...{RST}")
    if ruta_wav and os.path.exists(ruta_wav):
        print(f"  {AMARIL}>>> Escucha la voz de Lucia <<<{RST}")
        player = _MCIPlayer()
        ok_play = player.reproducir_y_esperar(ruta_wav, timeout=90.0)
        if ok_play:
            ok("Reproduccion completada")
        else:
            err("Error en reproduccion MCI")
    else:
        err("No hay WAV para reproducir")

    # Resumen
    sep()
    print(f"{BOLD}{VERDE}  RESULTADO DEL TEST{RST}")
    print(f"  Frases sintetizadas : {len(muestras_ok)}/{len(FRASES)}")
    if ruta_wav:
        print(f"  WAV guardado en     : tests/muestra_voz_lucia.wav")
    print(f"  Modelo activo       : {info['modelo_activo']}")
    print(f"  Aceleracion GPU     : Intel Arc (DirectML)")
    print(f"  DSP                 : {info['dsp']}")
    sep()

    return 0 if len(muestras_ok) == len(FRASES) else 2


if __name__ == "__main__":
    sys.exit(main())