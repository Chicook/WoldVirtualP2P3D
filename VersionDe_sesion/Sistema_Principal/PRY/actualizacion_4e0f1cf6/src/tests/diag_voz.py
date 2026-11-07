"""Diagnostico de voz: sintetiza frase de referencia y guarda WAV sin reproducir."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from SBSTM.voice_engine import get_voice_engine

FRASE = "Hola Jefe. Soy Lucia. Tu proyecto WoldVirtual esta registrado en mi memoria."

t0 = time.perf_counter()
v = get_voice_engine()
print("init_ms:", round((time.perf_counter() - t0) * 1000))
print("gtts_disponible:", v._gtts_disponible)
print("onecore:", v._onecore_token.GetDescription(1033) if v._onecore_token else None)

limpio = v.limpiador.sanitizar(FRASE)
human = v.modulador.humanizar_texto(limpio, aplicar_muletillas=False)
print("texto_hablado:", human)

# Sintesis oficial paso a paso con reporte de backend
from gtts import gTTS
import soundfile as sf
import numpy as np
from scipy import signal
from pedalboard import Pedalboard, LowShelfFilter, PeakFilter, Compressor

out = Path(__file__).resolve().parent / "test_voces" / "diag_powershell.wav"
t1 = time.perf_counter()
tts = gTTS(text=human, lang="es", tld="es", slow=False)
tts.save(str(out) + ".mp3")
print("gtts_ms:", round((time.perf_counter() - t1) * 1000))

audio, sr = sf.read(str(out) + ".mp3")
if audio.ndim > 1:
    audio = audio[:, 0]
audio = audio.astype(np.float32)
nueva_longitud = int(len(audio) / 1.16)
audio_resample = signal.resample(audio, nueva_longitud)
board = Pedalboard([
    LowShelfFilter(cutoff_frequency_hz=280.0, gain_db=1.0),
    PeakFilter(cutoff_frequency_hz=1000.0, gain_db=0.9, q=0.7),
    PeakFilter(cutoff_frequency_hz=3400.0, gain_db=-1.5, q=1.0),
    Compressor(threshold_db=-18.0, ratio=1.7),
])
final = board(audio_resample.astype(np.float32), sr)
sf.write(str(out), final, sr)
print("wav_guardado:", out, "bytes:", out.stat().st_size)
