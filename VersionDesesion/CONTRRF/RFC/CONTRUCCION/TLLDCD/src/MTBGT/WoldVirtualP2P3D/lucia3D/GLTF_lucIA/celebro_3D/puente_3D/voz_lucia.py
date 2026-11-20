"""Sintesis de voz de LucIA para el puente 3D.

Reutiliza la implementacion oficial del proyecto:
  sub_sistemas/voice_helpers.py -> gTTS es-ES + DSP 1.16x + fallback OneCore.

Devuelve PCM 16 bits listo para que Godot lo reproduzca con AudioStreamWAV.
"""
from __future__ import annotations

import base64
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

SUB_SISTEMAS = Path(__file__).resolve().parent.parent / "sub_sistemas"
if str(SUB_SISTEMAS) not in sys.path:
    sys.path.insert(0, str(SUB_SISTEMAS))

from voice_helpers import (  # noqa: E402
    LimpiadorFoneticoLucIA,
    ModuladorExpresivoJuvenil,
    sintetizar_oficial_dsp,
)

_SILENCIO_SEG = 0.15
_BLOQUE_MAX = 300
_PREFS_ONECORE = ("elvira", "laura", "helena")

_limitador = LimpiadorFoneticoLucIA()
_modulador = ModuladorExpresivoJuvenil()


def _log_voz(mensaje: str) -> None:
    try:
        ruta = Path(tempfile.gettempdir()) / "lucia_voz.log"
        with open(ruta, "a", encoding="utf-8") as archivo:
            archivo.write(f"{time.strftime('%H:%M:%S')} {mensaje}\n")
    except OSError:
        pass


def _pcm_de_wav(ruta: str) -> Optional[Tuple[bytes, int, int]]:
    try:
        import soundfile as sf

        datos, frecuencia = sf.read(ruta, dtype="int16", always_2d=True)
        if datos.size == 0:
            return None
        canales = int(datos.shape[1])
        if canales > 1:
            datos = datos[:, 0]
            canales = 1
        return datos.astype("<i2").tobytes(), int(frecuencia), canales
    except Exception:
        try:
            import wave

            with wave.open(ruta, "rb") as wav:
                if wav.getsampwidth() != 2:
                    return None
                canales = wav.getnchannels()
                frecuencia = wav.getframerate()
                pcm = wav.readframes(wav.getnframes())
            return pcm, int(frecuencia), int(canales)
        except Exception:
            return None


def _sintetizar_gtts(texto: str) -> Optional[Tuple[bytes, int, int]]:
    limpio = _limitador.sanitizar(texto)
    if not limpio:
        return None
    humanizado = _modulador.humanizar_texto(limpio, aplicar_muletillas=False)
    bloques = _limitador.segmentar_frases(humanizado, max_chars=_BLOQUE_MAX)
    partes: list[bytes] = []
    frecuencia: Optional[int] = None
    canales: Optional[int] = None

    for indice, bloque in enumerate(bloques):
        ruta: Optional[str] = None
        try:
            ruta = sintetizar_oficial_dsp(bloque, 0.65)
            if not ruta:
                return None
            resultado = _pcm_de_wav(ruta)
            if resultado is None:
                return None
            pcm, rate, ch = resultado
            if frecuencia is None:
                frecuencia, canales = rate, ch
            elif (rate, ch) != (frecuencia, canales):
                return None
            if partes and frecuencia:
                partes.append(b"\x00\x00" * int(frecuencia * _SILENCIO_SEG))
            partes.append(pcm)
        except Exception as error:
            print(f"[voz] gTTS+DSP fallo: {error}")
            return None
        finally:
            if ruta:
                try:
                    os.remove(ruta)
                except OSError:
                    pass
        if indice < len(bloques) - 1:
            time.sleep(1.0)

    if not partes or frecuencia is None or canales is None:
        return None
    return b"".join(partes), frecuencia, canales


def _token_onecore() -> Any:
    try:
        import comtypes.client  # type: ignore

        categoria = comtypes.client.CreateObject("SAPI.SpObjectTokenCategory")
        categoria.SetId(
            r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices", False
        )
        tokens = categoria.EnumerateTokens()
        mapa = []
        for i in range(tokens.Count):
            token = tokens.Item(i)
            try:
                descripcion = token.GetDescription(1033)
            except Exception:
                descripcion = ""
            mapa.append((descripcion.lower(), token))
        for preferencia in _PREFS_ONECORE:
            for descripcion, token in mapa:
                if preferencia in descripcion:
                    return token
        for descripcion, token in mapa:
            if "spanish" in descripcion or "espa" in descripcion:
                return token
    except Exception as error:
        print(f"[voz] OneCore no disponible: {error}")
    return None


def _sintetizar_onecore(texto: str) -> Optional[Tuple[bytes, int, int]]:
    ruta: Optional[str] = None
    try:
        import comtypes  # type: ignore
        import comtypes.client  # type: ignore

        try:
            comtypes.CoInitialize()
        except Exception:
            pass

        token = _token_onecore()
        if token is None:
            return None

        descriptor, ruta = tempfile.mkstemp(suffix=".wav")
        os.close(descriptor)
        sapi = comtypes.client.CreateObject("SAPI.SpVoice")
        sapi.Voice = token
        sapi.Rate = 2
        flujo = comtypes.client.CreateObject("SAPI.SpFileStream")
        flujo.Open(ruta, 3, False)
        try:
            sapi.AudioOutputStream = flujo
            sapi.Speak(texto, 0)
        finally:
            flujo.Close()
        return _pcm_de_wav(ruta)
    except Exception as error:
        _log_voz(f"onecore: {error}")
        print(f"[voz] OneCore fallo: {error}")
        return None
    finally:
        if ruta:
            try:
                os.remove(ruta)
            except OSError:
                pass


def _pcm_de_wav_stdlib(ruta: str) -> Optional[Tuple[bytes, int, int]]:
    """Lee un WAV PCM16 con la librería estándar, sin soundfile ni scipy."""
    try:
        with wave.open(ruta, "rb") as w:
            canales = w.getnchannels()
            frecuencia = w.getframerate()
            ancho = w.getsampwidth()
            datos = w.readframes(w.getnframes())
        if ancho == 2:
            return datos, int(frecuencia), int(canales)
        if ancho == 1:
            # WAV de 8 bits sin signo -> PCM16 con signo.
            pcm = bytearray()
            for muestra in datos:
                valor = (int(muestra) - 128) * 256
                pcm += int(valor).to_bytes(2, "little", signed=True)
            return bytes(pcm), int(frecuencia), int(canales)
    except Exception as error:
        print(f"[voz] WAV estándar falló: {error}")
    return None


def _sintetizar_system_speech(texto: str) -> Optional[Tuple[bytes, int, int]]:
    """Voz local de Windows vía System.Speech (Helena/Zira), sin dependencias."""
    ruta_ps1: Optional[str] = None
    ruta_wav: Optional[str] = None
    try:
        descriptor, ruta_wav = tempfile.mkstemp(suffix=".wav")
        os.close(descriptor)
        guion = (
            "param([string]$Salida, [string]$Texto)\n"
            "Add-Type -AssemblyName System.Speech\n"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
            "try { $s.SelectVoice('Microsoft Helena Desktop') } catch {}\n"
            "$s.Rate = 1\n"
            "$s.SetOutputToWaveFile($Salida)\n"
            "$s.Speak($Texto)\n"
            "$s.Dispose()\n"
        )
        descriptor, ruta_ps1 = tempfile.mkstemp(suffix=".ps1")
        os.close(descriptor)
        with open(ruta_ps1, "w", encoding="utf-8") as archivo:
            archivo.write(guion)
        proceso = subprocess.run(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", ruta_ps1, "-Salida", ruta_wav, "-Texto", texto,
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if proceso.returncode == 0 and os.path.getsize(ruta_wav) > 1000:
            return _pcm_de_wav_stdlib(ruta_wav)
        error = proceso.stderr.decode("utf-8", errors="ignore").strip()
        print(f"[voz] System.Speech falló: {error[:200]}")
    except Exception as error:
        _log_voz(f"system_speech: {error}")
        print(f"[voz] System.Speech excepción: {error}")
    finally:
        for ruta in (ruta_ps1, ruta_wav):
            if ruta:
                try:
                    os.remove(ruta)
                except OSError:
                    pass
    return None


_COLA_VOZ: "queue.Queue" = queue.Queue()
_HILO_VOZ: Optional[threading.Thread] = None


def _trabajador_voz() -> None:
    """Hilo único de síntesis: conserva COM/OneCore caliente entre turnos."""
    while True:
        texto, evento, caja = _COLA_VOZ.get()
        try:
            resultado = _sintetizar_onecore(texto)
            if resultado is None:
                resultado = _sintetizar_system_speech(texto)
            caja.append(resultado)
        except Exception as error:
            _log_voz(f"trabajador: {error}")
            print(f"[voz] Trabajador: {error}")
            caja.append(None)
        finally:
            evento.set()


def _sintetizar_en_hilo(texto: str) -> Optional[Tuple[bytes, int, int]]:
    global _HILO_VOZ
    if _HILO_VOZ is None or not _HILO_VOZ.is_alive():
        _HILO_VOZ = threading.Thread(target=_trabajador_voz, daemon=True, name="lucia-voz")
        _HILO_VOZ.start()
    evento = threading.Event()
    caja: list = []
    _COLA_VOZ.put((texto, evento, caja))
    if not evento.wait(90):
        return None
    return caja[0] if caja else None


def sintetizar_voz(texto: str) -> Optional[Dict[str, Any]]:
    """Devuelve el audio PCM16 de la respuesta o None si ningun backend funciona."""
    if not texto or not texto.strip():
        return None
    inicio = time.perf_counter()
    resultado = _sintetizar_gtts(texto)
    backend = "gTTS+DSP"
    if resultado is None:
        resultado = _sintetizar_en_hilo(texto)
        backend = "OneCore/System.Speech"
    if resultado is None:
        return None

    pcm, frecuencia, canales = resultado
    if not pcm or frecuencia <= 0 or canales <= 0:
        return None
    bytes_por_segundo = frecuencia * 2 * canales
    duracion = len(pcm) / bytes_por_segundo
    return {
        "pcm": base64.b64encode(pcm).decode("ascii"),
        "rate": frecuencia,
        "canales": canales,
        "duracion": round(duracion, 3),
        "backend": backend,
        "ms": int((time.perf_counter() - inicio) * 1000),
    }


def precargar_voz() -> None:
    try:
        import gtts  # noqa: F401
        import numpy  # noqa: F401
        import pedalboard  # noqa: F401
        import scipy.signal  # noqa: F401
        import soundfile  # noqa: F401

        print("[voz] Motor gTTS+DSP precargado")
    except Exception as error:
        print(f"[voz] Precarga parcial: {error}")
    # Calentar el hilo de voz una sola vez: conserva COM/OneCore caliente y
    # evita el arranque lento de PowerShell en cada frase.
    try:
        calentamiento = _sintetizar_en_hilo("Hola, soy LucIA.")
        if calentamiento:
            print("[voz] Hilo de voz precargado")
    except Exception as error:
        print(f"[voz] No se pudo precargar el hilo de voz: {error}")
