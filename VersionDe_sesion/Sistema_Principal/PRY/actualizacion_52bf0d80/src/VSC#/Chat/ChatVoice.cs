using System;
using System.Collections.Generic;
using NAudio.Wave;
using NAudio.Wave.SampleProviders;

namespace Visor3D.Chat
{
    /// <summary>
    /// Voz del chat: micro PCM16 mono 16 kHz en tramas de 20 ms y mezcla local
    /// de todas las voces remotas. Requiere auriculares para evitar eco.
    /// </summary>
    public sealed class ChatVoice : IDisposable
    {
        private readonly object _gate = new();
        private readonly Dictionary<int, (BufferedWaveProvider buffer, ISampleProvider input)> _remotos = new();
        private WaveOutEvent? _salida;
        private MixingSampleProvider? _mezcla;
        private WaveInEvent? _micro;
        private bool _disposed;

        public bool IsMicOn { get; private set; }
        public bool PlaybackReady { get; private set; }
        public string? LastError { get; private set; }
        public float Level { get; private set; }

        public event Action<byte[]>? MicFrame;

        public static int MicrophoneCount
        {
            get
            {
                try { return WaveIn.DeviceCount; }
                catch { return 0; }
            }
        }

        public bool StartPlayback()
        {
            lock (_gate)
            {
                if (PlaybackReady) return true;
                try
                {
                    var formato = WaveFormat.CreateIeeeFloatWaveFormat(ChatProtocol.SampleRate, 1);
                    _mezcla = new MixingSampleProvider(formato) { ReadFully = true };
                    _salida = new WaveOutEvent { DesiredLatency = 120, NumberOfBuffers = 3 };
                    _salida.Init(_mezcla.ToWaveProvider16());
                    _salida.Play();
                    PlaybackReady = true;
                    LastError = null;
                    return true;
                }
                catch (Exception ex)
                {
                    LastError = $"Audio de salida no disponible: {ex.Message}";
                    _salida?.Dispose();
                    _salida = null;
                    _mezcla = null;
                    PlaybackReady = false;
                    return false;
                }
            }
        }

        public bool StartMic()
        {
            lock (_gate)
            {
                if (IsMicOn) return true;
                try
                {
                    _micro = new WaveInEvent
                    {
                        WaveFormat = new WaveFormat(ChatProtocol.SampleRate, 16, 1),
                        BufferMilliseconds = 20,
                        NumberOfBuffers = 4
                    };
                    _micro.DataAvailable += OnMicData;
                    _micro.RecordingStopped += (_, e) =>
                    {
                        if (e.Exception != null) LastError = $"Micrófono: {e.Exception.Message}";
                    };
                    _micro.StartRecording();
                    IsMicOn = true;
                    LastError = null;
                    return true;
                }
                catch (Exception ex)
                {
                    LastError = $"Micrófono no disponible: {ex.Message}";
                    DetenerMicroLocked();
                    return false;
                }
            }
        }

        public void StopMic()
        {
            lock (_gate) DetenerMicroLocked();
        }

        private void DetenerMicroLocked()
        {
            var micro = _micro;
            _micro = null;
            IsMicOn = false;
            Level = 0f;
            if (micro == null) return;
            try
            {
                micro.StopRecording();
                micro.DataAvailable -= OnMicData;
                micro.Dispose();
            }
            catch { }
        }

        private void OnMicData(object? sender, WaveInEventArgs e)
        {
            if (e.BytesRecorded <= 0) return;

            float pico = 0f;
            for (int i = 0; i + 1 < e.BytesRecorded; i += 2)
            {
                short muestra = (short)(e.Buffer[i] | (e.Buffer[i + 1] << 8));
                float valor = Math.Abs(muestra) / 32768f;
                if (valor > pico) pico = valor;
            }
            Level = pico;

            byte[] copia = new byte[e.BytesRecorded];
            Buffer.BlockCopy(e.Buffer, 0, copia, 0, e.BytesRecorded);
            MicFrame?.Invoke(copia);
        }

        /// <summary>Encola PCM16 mono 16 kHz recibido de otro participante.</summary>
        public void PlayRemote(int emisor, byte[] pcm)
        {
            if (pcm == null || pcm.Length == 0) return;

            lock (_gate)
            {
                if (_disposed) return;
                if (!_remotos.TryGetValue(emisor, out var entrada))
                {
                    var buffer = new BufferedWaveProvider(new WaveFormat(ChatProtocol.SampleRate, 16, 1))
                    {
                        BufferDuration = TimeSpan.FromMilliseconds(300),
                        DiscardOnBufferOverflow = true,
                        ReadFully = true
                    };
                    var input = buffer.ToSampleProvider();
                    _remotos[emisor] = (buffer, input);
                    _mezcla?.AddMixerInput(input);
                    entrada = (buffer, input);
                }
                entrada.buffer.AddSamples(pcm, 0, pcm.Length);
            }
        }

        public void RemoveRemote(int emisor)
        {
            lock (_gate)
            {
                if (!_remotos.TryGetValue(emisor, out var entrada)) return;
                try { _mezcla?.RemoveMixerInput(entrada.input); } catch { }
                _remotos.Remove(emisor);
            }
        }

        public void Reset()
        {
            lock (_gate)
            {
                foreach (var entrada in _remotos.Values)
                {
                    try { _mezcla?.RemoveMixerInput(entrada.input); } catch { }
                }
                _remotos.Clear();
            }
        }

        public void Dispose()
        {
            lock (_gate)
            {
                if (_disposed) return;
                _disposed = true;
                DetenerMicroLocked();
                foreach (var entrada in _remotos.Values)
                {
                    try { _mezcla?.RemoveMixerInput(entrada.input); } catch { }
                }
                _remotos.Clear();
                try { _salida?.Stop(); } catch { }
                try { _salida?.Dispose(); } catch { }
                _salida = null;
                _mezcla = null;
                PlaybackReady = false;
            }
        }
    }
}
