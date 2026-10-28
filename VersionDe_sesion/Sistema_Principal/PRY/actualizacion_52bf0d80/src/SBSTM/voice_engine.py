"""

voice_engine.py - Motor de Sintesis de Voz Neuronal para LucIA (WoldVirtualP2P3D 2026)
=====================================================================================
Modo de expresion: Voz juvenil, espontanea, dinamica y fresca (estilo chica 18 anos).
Voz oficial: Voz Neuronal LucIA 18 anos (es-ES / Natural / DSP 1.16x / Tono Humano).
- Sintesis primaria: gTTS es-ES (peninsular nativo) + DSP vocal (1.16x + calidez intima de estudio).
- Fallbacks integrados: SAPI OneCore (Laura/Helena) y System.Speech.
- Control en tiempo real: cancel_tts con winmm.dll (MCI) y soporte asincrono en worker.

"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import tempfile
import threading
import time
from typing import Final, List, Optional, Tuple

from SBSTM.voice_helpers import (
    LimpiadorFoneticoLucIA,
    ModuladorExpresivoJuvenil,
    ReproductorMCIWindows,
)

logger = logging.getLogger("lucIA.Voice")

VOZ_OFICIAL: Final[str] = "LucIA-18anos-esES-vocal"
VERSION_VOICE: Final[str] = "2026.4.3"


class VoiceEngine:
    """
    Sintetizador neuronal de voz para LucIA con voz oficial es-ES natural
    y modulacion prosodica adaptativa de estilo juvenil espontaneo (18 anos).
    """

    def __init__(self, voz: str = VOZ_OFICIAL) -> None:
        self.voz: str = voz
        self._cola_voz: queue.Queue[str] = queue.Queue()
        self._detener_evento = threading.Event()
        self._cancelar_actual = threading.Event()
        self._hilo_worker: Optional[threading.Thread] = None
        self.mci = ReproductorMCIWindows()
        self.modulador = ModuladorExpresivoJuvenil()
        self.limpiador = LimpiadorFoneticoLucIA()
        self._gtts_disponible: bool = False
        self._nivel_emocion: float = 0.65
        self._habilitado: bool = True
        self._ultimo_error: str = ""
        self._onecore_token: Optional[object] = self._descubrir_voz_onecore()
        self._onecore_rate: int = 2
        self._procesador_rn = None
        self._inicializar_procesador_rn()
        self._verificar_gtts()
        self._iniciar_worker()

    def _inicializar_procesador_rn(self) -> None:
        try:
            try:
                from LC_STM.red_neuronal.SLRN.procesador_voz_neuronal import get_procesador_voz_neuronal
            except ImportError:
                import sys
                src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if src_dir not in sys.path:
                    sys.path.insert(0, src_dir)
                from LC_STM.red_neuronal.SLRN.procesador_voz_neuronal import get_procesador_voz_neuronal
            self._procesador_rn = get_procesador_voz_neuronal()
            logger.info("Motor de voz conectado con la Red Neuronal de LucIA (SLRN)")
        except Exception as e:
            logger.warning(f"No se pudo enlazar ProcesadorVozNeuronal: {e}")

    def _verificar_gtts(self) -> None:
        try:
            import gtts
            self._gtts_disponible = True
            logger.info(f"Voz oficial configurada: LucIA 18 anos (es-ES / DSP 1.16x)")
        except ImportError:
            self._gtts_disponible = False
            logger.warning("gTTS no detectado, usando fallback local")

    def _iniciar_worker(self) -> None:
        self._hilo_worker = threading.Thread(
            target=self._procesar_cola, daemon=True, name="LucIA-Voice-Worker"
        )
        self._hilo_worker.start()

    def set_emocion(self, nivel: float) -> None:
        """Ajusta la valencia emocional de la prosodia (0.0 a 1.0)."""
        self._nivel_emocion = max(0.0, min(1.0, float(nivel)))

    def limpiar_texto_para_habla(self, texto: str) -> str:
        """Sanitiza markdown, listas y caracteres extraños."""
        return self.limpiador.sanitizar(texto)

    def _sintetizar_oficial_con_timeout(self, chunk: str, segundos: float = 45.0) -> bool:
        """Sintesis oficial con timeout solo en la fase de red/DSP (no en reproduccion)."""
        from SBSTM.voice_helpers import sintetizar_oficial_dsp
        caja: List[Optional[str]] = []
        def _run() -> None:
            try:
                caja.append(sintetizar_oficial_dsp(chunk, self._nivel_emocion))
            except Exception as err:
                self._ultimo_error = f"oficial: {type(err).__name__}: {err}"[:200]
                caja.append(None)
        hilo = threading.Thread(target=_run, daemon=True)
        hilo.start()
        hilo.join(timeout=segundos)
        if hilo.is_alive():
            self._ultimo_error = f"oficial: timeout>{segundos:.0f}s en red gTTS"
            return False
        wav = caja[0] if caja else None
        if not wav:
            if not self._ultimo_error:
                self._ultimo_error = "oficial: sintesis vacia"
            return False
        try:
            from pathlib import Path as _P
            import shutil as _sh
            _aud = _P(__file__).resolve().parent.parent / "tests" / "test_voces"
            _aud.mkdir(parents=True, exist_ok=True)
            _sh.copyfile(wav, str(_aud / "ultima_voz_oficial.wav"))
        except Exception:
            pass
        try:
            if self._cancelar_actual.is_set():
                return False
            ok_mci = self.mci.reproducir_wav(wav, self._cancelar_actual, self._detener_evento)
            self._auditar("oficial-DSP", "ok" if ok_mci else "mci-sin-audio")
            if not ok_mci:
                self._ultimo_error = "oficial: MCI no reprodujo (ver voz_audit.log)"
            return bool(ok_mci)
        finally:
            try:
                if os.path.exists(wav):
                    os.remove(wav)
            except Exception:
                pass

    def _auditar(self, backend: str, detalle: str = "") -> None:
        """Registro persistente del backend de voz usado (tests/test_voces/voz_audit.log)."""
        try:
            from pathlib import Path as _P
            _aud = _P(__file__).resolve().parent.parent / "tests" / "test_voces" / "voz_audit.log"
            _aud.parent.mkdir(parents=True, exist_ok=True)
            with open(_aud, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} backend={backend} {detalle[:200]}\n")
        except Exception:
            pass

    @staticmethod
    def _descubrir_voz_onecore() -> Optional[object]:
        """
        Busca la mejor voz OneCore disponible en el sistema.
        Preferencia: ElviraNeural > Laura > Helena > cualquier es-ES femenina.
        Retorna el token COM de la voz seleccionada o None si falla.
        """
        PREFERENCIAS = [
            "elvira",   # ideal: Neural (instalar via Configuracion > Voz)
            "laura",    # OneCore juvenil femenina - segunda opcion
            "helena",   # OneCore femenina - tercera opcion
        ]
        try:
            import comtypes.client  # type: ignore
            cat = comtypes.client.CreateObject("SAPI.SpObjectTokenCategory")
            cat.SetId(
                r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices", False
            )
            tokens = cat.EnumerateTokens()
            # Recopilar todas las voces primero para busqueda priorizada
            mapa_voces: List[Tuple[str, object]] = []
            for i in range(tokens.Count):
                tok = tokens.Item(i)
                desc = tok.GetDescription(1033).lower()
                mapa_voces.append((desc, tok))
            # Seleccionar por preferencia en orden estricto
            for pref in PREFERENCIAS:
                for desc, tok in mapa_voces:
                    if pref in desc:
                        logger.info(
                            f"Voz OneCore seleccionada: {tok.GetDescription(1033)}"
                        )
                        return tok
            # Ultimo recurso: cualquier voz en espanol
            for desc, tok in mapa_voces:
                if "spanish" in desc or "espa" in desc:
                    logger.info(
                        f"Voz OneCore fallback es-ES: {tok.GetDescription(1033)}"
                    )
                    return tok
            return None
        except Exception as err:
            logger.warning(f"No se pudo acceder a voces OneCore: {err}")
            return None

    def _sintetizar_fallback_windows(self, texto_limpio: str) -> None:
        """Sintetiza con SAPI OneCore (Laura/Helena) via COM y reproduce con MCI."""
        if self._cancelar_actual.is_set():
            return

        # Intentar sintesis COM OneCore
        if self._onecore_token is not None and self._sintetizar_onecore_com(texto_limpio):
            return

        # Ultimo recurso: PowerShell System.Speech (sin seleccion de voz especifica)
        logger.warning("Usando System.Speech como ultimo recurso (calidad basica)")
        t_esc = texto_limpio.replace("'", "").replace('"', "")
        cmd = [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            f"Add-Type -AssemblyName System.Speech; "
            f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female, "
            f"[System.Speech.Synthesis.VoiceAge]::Teen); "
            f"$synth.Rate = 2; "
            f"$synth.Speak([string]'{t_esc}')"
        ]
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=25,
            )
        except Exception as err:
            logger.warning(f"Error System.Speech final: {err}")

    def _sintetizar_onecore_com(self, texto: str) -> bool:
        """Genera WAV con SAPI OneCore via COM y lo reproduce con MCI."""
        if self._cancelar_actual.is_set():
            return False
        temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd)
        try:
            import comtypes.client  # type: ignore
            sapi = comtypes.client.CreateObject("SAPI.SpVoice")
            sapi.Voice = self._onecore_token
            sapi.Rate = self._onecore_rate

            stream = comtypes.client.CreateObject("SAPI.SpFileStream")
            stream.Open(temp_path, 3, False)  # SSFMCreateForWrite
            sapi.AudioOutputStream = stream
            sapi.Speak(texto, 0)  # SPF_DEFAULT (sincrono)
            stream.Close()

            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                if not self._cancelar_actual.is_set():
                    self.mci.reproducir_wav(temp_path, self._cancelar_actual, self._detener_evento)
                return True
        except Exception as err:
            logger.warning(f"Error sintesis OneCore COM: {err}")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
        return False

    def _sintetizar_red_neuronal_local(self, chunk: str) -> bool:
        """Sintetiza mediante la red neuronal de LucIA (SLRN) de forma autonoma."""
        if self._cancelar_actual.is_set() or self._procesador_rn is None:
            return False
        try:
            import soundfile as sf
            res = self._procesador_rn.generar_audio_frase(chunk, self._nivel_emocion)
            if res is None:
                return False
            audio, sr = res
            temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
            os.close(temp_fd)
            try:
                sf.write(temp_path, audio, sr)
                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                    if not self._cancelar_actual.is_set():
                        self.mci.reproducir_wav(temp_path, self._cancelar_actual, self._detener_evento)
                        return True
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
        except Exception as ex:
            logger.warning(f"Error en sintesis con red neuronal local: {ex}")
        return False

    def _procesar_mensaje(self, texto_completo: str) -> None:
        if not self._habilitado:
            return
        try:
            self._auditar("inicio", f"gtts={self._gtts_disponible} onecore={bool(self._onecore_token)} rn={bool(self._procesador_rn)} pid={os.getpid()}")
        except Exception:
            pass
        limpio = self.limpiador.sanitizar(texto_completo)
        if not limpio:
            return
        # Voz: sin muletillas; se habla el texto completo por bloques (sin tope).
        humanizado = self.modulador.humanizar_texto(limpio, aplicar_muletillas=False)
        bloques = self.limpiador.segmentar_frases(humanizado, max_chars=300)
        print(f"  [VOZ] sintetizando voz oficial-DSP ({len(bloques)} bloques)...", flush=True)
        exito, backend, motivo_fallo, hablados = False, "ninguno", "", 0
        if self._gtts_disponible and not self._cancelar_actual.is_set():
            exito = True
            for i, bl in enumerate(bloques):
                if self._cancelar_actual.is_set() or self._detener_evento.is_set():
                    exito = False
                    break
                if i > 0:
                    time.sleep(1.0)  # anti-throttle gTTS entre bloques
                ok = self._sintetizar_oficial_con_timeout(bl)
                if not ok:  # un reintento; si falla, fallback solo de ese bloque y se sigue
                    time.sleep(2.0)
                    ok = self._sintetizar_oficial_con_timeout(bl)
                if ok:
                    hablados += 1
                    print(f"  [VOZ] bloque {hablados}/{len(bloques)} hablado.", flush=True)
                else:
                    motivo_fallo = self._ultimo_error or "sintesis oficial devolvio False"
                    self._sintetizar_fallback_windows(bl)
            if exito:
                backend = "oficial-DSP" if hablados == len(bloques) else "oficial-DSP-parcial"
        if hablados == 0 and not self._cancelar_actual.is_set():
            exito = self._sintetizar_red_neuronal_local(humanizado)
            backend = "red-neuronal-SLRN" if exito else backend
        if hablados == 0 and not exito and not self._cancelar_actual.is_set():
            for fragmento in self.limpiador.segmentar_frases(humanizado, max_chars=420):
                if self._cancelar_actual.is_set() or self._detener_evento.is_set():
                    break
                self._sintetizar_fallback_windows(fragmento)
            backend = "fallback-windows-robotica"
            if not motivo_fallo:
                motivo_fallo = self._ultimo_error or "sin motivo registrado"
        print(f"  [VOZ] backend: {backend} ({hablados}/{len(bloques)} bloques)" + (f" | fallo: {motivo_fallo}" if backend != "oficial-DSP" else ""), flush=True)
        try:
            self._auditar(backend, motivo_fallo)
        except Exception:
            pass

    def _procesar_cola(self) -> None:
        while not self._detener_evento.is_set():
            try:
                mensaje = self._cola_voz.get(timeout=0.3)
            except queue.Empty:
                continue

            if mensaje:
                self._cancelar_actual.clear()
                self._procesar_mensaje(mensaje)
            self._cola_voz.task_done()

    def cancel_tts(self) -> None:
        """Detiene inmediatamente el audio en curso y purga la cola."""
        self._cancelar_actual.set()
        self.mci.detener_inmediato()
        while not self._cola_voz.empty():
            try:
                self._cola_voz.get_nowait()
            except Exception:
                pass

    def speak(self, texto: str, esperar: bool = False, emocion: Optional[float] = None) -> None:
        """Emite un enunciado en la voz natural juvenil de LucIA."""
        if not texto or not texto.strip():
            return
        if emocion is not None:
            self.set_emocion(emocion)
        if esperar:
            self._cancelar_actual.clear()
            self._procesar_mensaje(texto)
        else:
            self._cola_voz.put(texto)

    def activar(self, estado: bool = True) -> None:
        """Habilita o desactiva la sintesis de voz global."""
        self._habilitado = bool(estado)
        if not self._habilitado:
            self.cancel_tts()

    def esta_activa(self) -> bool:
        return self._habilitado

    def detener(self) -> None:
        """Cierre definitivo del motor de audio y sus hilos asociados."""
        self._detener_evento.set()
        self.cancel_tts()


_voice_instance: Optional[VoiceEngine] = None
_global_lock_voice = threading.Lock()


def get_voice_engine() -> VoiceEngine:
    global _voice_instance
    with _global_lock_voice:
        if _voice_instance is None:
            _voice_instance = VoiceEngine(voz=VOZ_OFICIAL)
    return _voice_instance


def estado_voz() -> str:
    """Linea de estado con backends reales (gtts/onecore/red) para el arranque."""
    try:
        v = get_voice_engine()
        return (f"[VOZ]  Voz Neuronal LucIA  : ACTIVA | 18 anos / es-ES / DSP 1.16x | "
                f"gtts={v._gtts_disponible} onecore={bool(v._onecore_token)} rn={bool(v._procesador_rn)}")
    except Exception as err:
        return f"[VOZ]  Voz Neuronal LucIA  : NO DISPONIBLE ({err})"


def speak(texto: str, esperar: bool = False, emocion: Optional[float] = None) -> None:
    """Conveniencia directa: emite voz con es-ES-ElviraNeural y tono fresco."""
    motor = get_voice_engine()
    motor.speak(texto, esperar=esperar, emocion=emocion)


def cancel_speech() -> None:
    """Interrumpe cualquier reproduccion sonora activa al instante."""
    motor = get_voice_engine()
    motor.cancel_tts()


def configurar_prosodia_juvenil(tono: str = "positivo") -> None:
    """Configura la expresion de la voz segun el tono neuronal detectado."""
    motor = get_voice_engine()
    mapeo_tonos = {"positivo": 0.85, "neutro": 0.60, "tecnico": 0.45, "negativo": 0.30}
    val = mapeo_tonos.get(tono.lower(), 0.60)
    motor.set_emocion(val)


if __name__ == "__main__":
    print("\033[38;5;51m" + "=" * 72 + "\033[0m")
    print("  Motor de Voz LucIA (18 Anos / es-ES / DSP 1.16x) - Autotest")
    print("\033[38;5;51m" + "=" * 72 + "\033[0m")
    v = get_voice_engine()
    demo_txt = "Hola! Soy Lucía. Estoy encantada de saludarte y mi voz suena completamente natural."
    print(f"  Texto original : {demo_txt}")
    h = v.modulador.humanizar_texto(demo_txt)
    r, p = v.modulador.calcular_prosodia(h, 0.75)
    print(f"  Humanizado     : {h}")
    print(f"  Prosodia       : Rate={r} | Pitch={p}")
    print("\033[38;5;48m  [OK] Subsistema de voz listo para integracion en mainLCSTM\033[0m")
    print("\033[38;5;51m" + "=" * 72 + "\033[0m")
