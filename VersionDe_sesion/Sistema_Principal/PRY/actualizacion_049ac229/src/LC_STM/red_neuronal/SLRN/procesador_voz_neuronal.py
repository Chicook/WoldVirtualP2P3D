"""Procesador de Voz Neuronal de LucIA 2026 (LC_STM/red_neuronal/SLRN/procesador_voz_neuronal.py)."""
from __future__ import annotations

import io
import json
import logging
import re
import threading
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("lucIA.RedNeuronal.Voz")

_DIR_SRC = Path(__file__).resolve().parents[3]  # .../RFC/src
_MODELS_DIR = _DIR_SRC / "SBSTM" / "tts_models"

_MODELOS_PRIORITARIOS: List[Tuple[str, str, str]] = [
    (
        "es_AR-daniela-high.onnx",
        "Daniela (alta calidad, femenina)",
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_AR/daniela/high/es_AR-daniela-high.onnx",
    ),
    (
        "es_ES-sharvard-medium.onnx",
        "Sharvard (es-ES, media)",
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx",
    ),
]


# ===========================================================================
# ModuladorCognitivo — Registro oral chica espanola 18 anos
# ===========================================================================
class ModuladorCognitivo18Anos:
    """Adapta el texto al estilo oral espontaneo de una chica espanola de 18 anos."""

    MULETILLAS_NATURALES: List[str] = [
        "Oye, ", "Pues mira, ", "A ver, te cuento: ", "Mira, ", "Fijate que ", "Bueno, a ver, ",
    ]

    PATRONES_ORALES: List[Tuple[str, str]] = [
        (r"\bpor lo tanto\b", "asi que"), (r"\bpor consiguiente\b", "con lo cual"),
        (r"\bsin embargo\b", "pero oye,"), (r"\bno obstante\b", "aunque bueno,"),
        (r"\bes decir\b", "o sea,"), (r"\ben efecto\b", "exactamente,"),
        (r"\bcabe destacar que\b", "lo que mola es que"), (r"\bciertamente\b", "de verdad,"),
        (r"\bpor tanto\b", "entonces"), (r"\basimismo\b", "y tambien"),
    ]

    def __init__(self) -> None:
        self._contador = 0
        self._lock = threading.Lock()

    def procesar_texto(self, texto: str, emocion: float = 0.65) -> str:
        """Humaniza y adapta el texto al registro oral de una joven de 18 anos."""
        if not texto:
            return ""
        t = texto.strip()
        t = re.sub(r"```.*?```", "", t, flags=re.DOTALL)
        t = re.sub(r"`[^`]*`", "", t)
        t = re.sub(r"[*_#~>|\\()\[\]{}]", "", t)
        t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
        t = re.sub(r"\s+", " ", t).strip()

        for pat, rep in self.PATRONES_ORALES:
            t = re.sub(pat, rep, t, flags=re.IGNORECASE)

        if len(t) > 35 and not t.startswith(("!", "?", "Oye", "Mira", "Pues")):
            with self._lock:
                self._contador += 1
                if self._contador % 2 == 1:
                    pfx = self.MULETILLAS_NATURALES[
                        self._contador % len(self.MULETILLAS_NATURALES)
                    ]
                    t = pfx + t[0].lower() + t[1:]

        if t and t[-1] not in ".!?":
            t += "."
        return t

    def calcular_parametros_dsp(self, emocion: float = 0.65) -> Dict[str, float]:
        """Parametros DSP para timbre de chica espanola de 18 anos."""
        return {
            "length_scale": max(0.72, 0.88 - emocion * 0.10),
            "pitch_semitones": 2.2 + emocion * 0.8,
            "high_shelf_gain": 2.5 + emocion * 1.2,
            "low_mid_cut_db": -2.5,
            "noise_scale": 0.55 + emocion * 0.15,
            "noise_w_scale": 0.70 + emocion * 0.15,
        }

    def calcular_parametros_neuronales(self, emocion: float = 0.65) -> Dict[str, float]:
        return self.calcular_parametros_dsp(emocion)


# ===========================================================================
# Motor Piper local con soporte DirectML (Intel Arc 8 GB VRAM)
# ===========================================================================
class MotorPiperLocal:
    """Motor de sintesis Piper TTS con modelos ONNX locales y DirectML opcional."""

    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self._voice = None
        self._sample_rate: int = 22050
        self._modelo_activo: str = ""
        self._lock = threading.Lock()
        self._inicializar()

    def _inicializar(self) -> None:
        try:
            from piper import PiperVoice
        except ImportError:
            logger.error("[MotorPiper] piper-tts no instalado. pip install piper-tts")
            return

        self.models_dir.mkdir(parents=True, exist_ok=True)
        for nombre_onnx, descripcion, url_onnx in _MODELOS_PRIORITARIOS:
            ruta_onnx = self.models_dir / nombre_onnx
            ruta_json = self.models_dir / (nombre_onnx + ".json")
            if not ruta_onnx.exists() or not ruta_json.exists():
                self._descargar_modelo_si_ausente(nombre_onnx, url_onnx, ruta_onnx, ruta_json)
            if not ruta_onnx.exists() or not ruta_json.exists():
                logger.debug(f"[MotorPiper] No disponible localmente: {nombre_onnx}")
                continue
            try:
                self._voice = PiperVoice.load(
                    str(ruta_onnx),
                    config_path=str(ruta_json),
                    use_cuda=False,
                )
                with open(ruta_json, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._sample_rate = cfg.get("audio", {}).get("sample_rate", 22050)
                self._modelo_activo = descripcion
                logger.info(
                    f"[MotorPiper] Cargado: {descripcion} @ {self._sample_rate} Hz"
                )
                self._intentar_directml(ruta_onnx)
                break
            except Exception as e:
                logger.warning(f"[MotorPiper] Fallo cargando {descripcion}: {e}")
                self._voice = None

        if self._voice is None:
            logger.error(
                "[MotorPiper] Ningun modelo Piper disponible en tts_models/. "
                "Verifica que los .onnx y .json esten presentes."
            )

    def _descargar_modelo_si_ausente(
        self, nombre_onnx: str, url_onnx: str, ruta_onnx: Path, ruta_json: Path
    ) -> None:
        """Descarga de forma segura el modelo ONNX y JSON desde Hugging Face si no estan."""
        import urllib.request
        url_json = url_onnx + ".json"
        try:
            logger.info(f"[MotorPiper] Descargando modelo de voz neuronal {nombre_onnx}...")
            if not ruta_json.exists():
                urllib.request.urlretrieve(url_json, str(ruta_json))
            if not ruta_onnx.exists():
                urllib.request.urlretrieve(url_onnx, str(ruta_onnx))
            logger.info(f"[MotorPiper] Descarga de {nombre_onnx} completada con exito.")
        except Exception as e_dl:
            logger.warning(f"[MotorPiper] No se pudo descargar {nombre_onnx} automaticamente: {e_dl}")
            for p in (ruta_onnx, ruta_json):
                if p.exists() and p.stat().st_size == 0:
                    try:
                        p.unlink()
                    except Exception:
                        pass

    def _intentar_directml(self, ruta_onnx: Path) -> None:
        """Inyecta sesion DirectML (Intel Arc) en PiperVoice si esta disponible."""
        try:
            import onnxruntime as ort
            if "DmlExecutionProvider" not in ort.get_available_providers():
                logger.debug("[MotorPiper] DirectML no disponible, usando CPU")
                return
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess = ort.InferenceSession(
                str(ruta_onnx),
                sess_options=opts,
                providers=["DmlExecutionProvider", "CPUExecutionProvider"],
            )
            # Piper expone la sesion ONNX como .session o .model segun version
            if hasattr(self._voice, "session"):
                self._voice.session = sess
                logger.info("[MotorPiper] DirectML (Intel Arc 8GB) inyectado en .session OK")
            elif hasattr(self._voice, "model"):
                self._voice.model = sess
                logger.info("[MotorPiper] DirectML (Intel Arc 8GB) inyectado en .model OK")
            else:
                logger.debug("[MotorPiper] No se encontro atributo session/model para inyectar DirectML")
        except Exception as e:
            logger.debug(f"[MotorPiper] DirectML no inyectado: {e} — usando CPU")

    @property
    def disponible(self) -> bool:
        return self._voice is not None

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def sintetizar_raw(
        self,
        texto: str,
        length_scale: float = 0.85,
        noise_scale: float = 0.65,
        noise_w_scale: float = 0.80,
    ) -> Optional[np.ndarray]:
        """Sintetiza texto y retorna PCM float32 normalizado. None si falla."""
        if not self.disponible:
            return None

        from piper import SynthesisConfig
        syn_cfg = SynthesisConfig(
            length_scale=length_scale,
            noise_scale=noise_scale,
            noise_w_scale=noise_w_scale,
            normalize_audio=True,
        )

        buf = io.BytesIO()
        with self._lock:
            try:
                with wave.open(buf, "wb") as wav_out:
                    self._voice.synthesize_wav(texto, wav_out, syn_config=syn_cfg)
            except Exception as e:
                logger.error(f"[MotorPiper] Error sintetizando: {e}")
                return None

        buf.seek(0)
        try:
            with wave.open(buf, "rb") as wav_in:
                n_frames    = wav_in.getnframes()
                raw_bytes   = wav_in.readframes(n_frames)
                sampwidth   = wav_in.getsampwidth()
                self._sample_rate = wav_in.getframerate()

            if sampwidth == 2:
                return np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            elif sampwidth == 4:
                return np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                return np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
        except Exception as e:
            logger.error(f"[MotorPiper] Error decodificando WAV: {e}")
            return None


# ===========================================================================
# Procesador DSP — Timbre juvenil espanol con pedalboard
# ===========================================================================
class ProcesadorDSP:
    """
    Cadena DSP profesional via pedalboard para voz de chica espanola 18 anos:
      1. PitchShift (+2-3 semitonos) -> mas aguda y juvenil
      2. HighShelfFilter (5kHz)      -> brillo y presencia femenina
      3. PeakFilter (260 Hz)         -> corte de resonancia de pecho
    """

    def __init__(self) -> None:
        self._disponible = False
        try:
            import pedalboard  # noqa
            self._disponible = True
            logger.info("[DSP] pedalboard OK — post-procesado profesional activado")
        except ImportError:
            logger.warning(
                "[DSP] pedalboard no instalado — voz sin DSP. "
                "Instala con: pip install pedalboard"
            )

    @property
    def disponible(self) -> bool:
        return self._disponible

    def procesar(
        self,
        audio: np.ndarray,
        sample_rate: int,
        pitch_semitones: float = 2.2,
        high_shelf_gain: float = 2.5,
        low_mid_cut_db: float  = -2.5,
    ) -> np.ndarray:
        """Aplica cadena DSP y retorna audio procesado (float32)."""
        if not self._disponible or audio is None or len(audio) == 0:
            return audio
        try:
            from pedalboard import Pedalboard, PitchShift, HighShelfFilter, PeakFilter
            chain = Pedalboard([
                PitchShift(semitones=pitch_semitones),
                HighShelfFilter(cutoff_frequency_hz=5000, gain_db=high_shelf_gain),
                PeakFilter(cutoff_frequency_hz=260, gain_db=low_mid_cut_db, q=1.2),
            ])
            # pedalboard espera (channels, samples)
            audio_2d = audio[np.newaxis, :] if audio.ndim == 1 else audio
            processed = chain(audio_2d, sample_rate)
            if processed.ndim == 2 and processed.shape[0] == 1:
                processed = processed[0]
            # Normalizar para evitar clipping
            max_val = np.max(np.abs(processed))
            if max_val > 0.98:
                processed = processed * (0.95 / max_val)
            return processed
        except Exception as e:
            logger.warning(f"[DSP] Error en procesamiento: {e} — devolviendo sin DSP")
            return audio


# ===========================================================================
# ProcesadorVozNeuronalLucIA — Clase principal (punto de integracion SLRN)
# ===========================================================================
class ProcesadorVozNeuronalLucIA:
    """
    Procesador neural de voz de LucIA.
    Integra la red neuronal SLRN con la sintesis de voz local.
    Pipeline: texto -> ModuladorCognitivo -> MotorPiper -> DSP -> (ndarray, sr)
    """

    def __init__(self, models_dir: Optional[str] = None) -> None:
        if models_dir is None:
            self.models_dir = _MODELS_DIR
        else:
            self.models_dir = Path(models_dir)

        self.modulador = ModuladorCognitivo18Anos()
        self._motor    = MotorPiperLocal(self.models_dir)
        self._dsp      = ProcesadorDSP()

        estado = "LISTO" if self._motor.disponible else "SIN MOTOR (voz fallback)"
        logger.info(
            f"[ProcesadorVozNeuronal] {estado} | "
            f"Modelo: {self._motor._modelo_activo or 'ninguno'} | "
            f"DSP: {'pedalboard' if self._dsp.disponible else 'desactivado'}"
        )

    @property
    def disponible(self) -> bool:
        """True si el motor de sintesis esta operativo."""
        return self._motor.disponible

    def generar_audio_frase(
        self,
        texto: str,
        emocion: float = 0.65,
    ) -> Optional[Tuple[np.ndarray, int]]:
        """
        Sintetiza una frase con timbre de chica espanola de 18 anos.
        Retorna (samples_float32, sample_rate) o None si falla.

        Args:
            texto:   Texto a sintetizar (se humanizara automaticamente).
            emocion: Valencia emocional 0.0-1.0 (afecta velocidad y brillo).
        """
        if not self._motor.disponible:
            # Fallback a voz oficial gTTS con DSP si no hay pesos ONNX descargados
            try:
                import io
                import soundfile as sf
                from gtts import gTTS
                texto_proc = self.modulador.procesar_texto(texto, emocion)
                tts = gTTS(text=texto_proc, lang="es", tld="es", slow=False)
                mp3_fp = io.BytesIO()
                tts.write_to_fp(mp3_fp)
                mp3_fp.seek(0)
                audio_raw, sr = sf.read(mp3_fp)
                if audio_raw.ndim > 1:
                    audio_raw = audio_raw[:, 0]
                # Acelerar la cadencia a 1.16x para el tono juvenil espontáneo
                from scipy import signal
                factor_vel = 1.16
                nueva_len = int(len(audio_raw) / factor_vel)
                audio_resample = signal.resample(audio_raw, nueva_len)
                params = self.modulador.calcular_parametros_dsp(emocion)
                if self._dsp.disponible:
                    audio_final = self._dsp.procesar(
                        audio_resample,
                        sr,
                        pitch_semitones=params.get("pitch_semitones", 2.2),
                        high_shelf_gain=params.get("high_shelf_gain", 2.5),
                        low_mid_cut_db=params.get("low_mid_cut_db", -2.0),
                    )
                else:
                    audio_final = audio_resample
                return audio_final, sr
            except Exception as e_fb:
                logger.warning(f"[ProcesadorVozNeuronal] Fallback gTTS fallo: {e_fb}")
                return None

        texto_proc = self.modulador.procesar_texto(texto, emocion)
        if not texto_proc:
            return None

        params = self.modulador.calcular_parametros_dsp(emocion)

        audio = self._motor.sintetizar_raw(
            texto_proc,
            length_scale  = params["length_scale"],
            noise_scale   = params["noise_scale"],
            noise_w_scale = params["noise_w_scale"],
        )
        if audio is None or len(audio) == 0:
            return None

        sr = self._motor.sample_rate

        if self._dsp.disponible:
            audio = self._dsp.procesar(
                audio,
                sr,
                pitch_semitones = params["pitch_semitones"],
                high_shelf_gain = params["high_shelf_gain"],
                low_mid_cut_db  = params["low_mid_cut_db"],
            )

        return audio, sr

    def info(self) -> Dict[str, str]:
        """Informacion de diagnostico del procesador."""
        return {
            "modelo_activo": self._motor._modelo_activo,
            "sample_rate":   str(self._motor.sample_rate),
            "dsp":           "pedalboard" if self._dsp.disponible else "desactivado",
            "models_dir":    str(self.models_dir),
        }


# ===========================================================================
# Singleton thread-safe — punto de acceso global
# ===========================================================================
_instancia_procesador: Optional[ProcesadorVozNeuronalLucIA] = None
_lock_singleton = threading.Lock()


def get_procesador_voz_neuronal() -> ProcesadorVozNeuronalLucIA:
    """
    Singleton thread-safe del procesador de voz neuronal de LucIA.
    Punto de integracion entre SLRN y voice_engine.py.
    """
    global _instancia_procesador
    with _lock_singleton:
        if _instancia_procesador is None:
            _instancia_procesador = ProcesadorVozNeuronalLucIA()
    return _instancia_procesador
