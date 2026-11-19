# tts_models — modelos de voz neuronal (Piper ONNX)

Directorio canónico de modelos TTS del subsistema de voz, según `Rutas.json`
§subsistemas.SBSTM.secciones (`tts_models`).

## Consumidores

- `LC_STM/red_neuronal/SLRN/procesador_voz_neuronal.py:18` — `_MODELS_DIR`
  apunta aquí; si no hay modelos, el motor Piper queda OFF y la voz cae al
  respaldo gTTS + DSP (comportamiento esperado, no es un error).
- `tests/STM_test3/test_voz_lucia.py:110` — comprueba este directorio.

## Estado (2026-11-16)

Vacío: sin modelos Piper descargados. Los archivos `.onnx` (y su `.json` de
configuración) no se versionan por peso; se descargan a mano y se dejan aquí.

## Política

- Nada de código: solo modelos y este LEEME.
- No renombrar la carpeta: el mapa canónico y el código la referencian por ruta fija.
