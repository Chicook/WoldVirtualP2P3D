using System;
using System.Diagnostics;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace Visor3D.Services
{
    /// <summary>
    /// Una sola ventana por instalación: la segunda ejecución enfoca la que ya
    /// está abierta (con su sesión y su avatar) en lugar de pedir login otra vez.
    /// </summary>
    internal static class InstanciaUnica
    {
        private const int SW_RESTORE = 9;

        private static Mutex? _mutex;

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetForegroundWindow(IntPtr hWnd);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

        [DllImport("user32.dll")]
        private static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

        [DllImport("kernel32.dll")]
        private static extern uint GetCurrentThreadId();

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool BringWindowToTop(IntPtr hWnd);

        public static bool EsPrimeraInstancia()
        {
            string nombre = NombreMutex();
            var mutex = new Mutex(initiallyOwned: false, nombre);
            try
            {
                if (mutex.WaitOne(0))
                {
                    _mutex = mutex;
                    return true;
                }
            }
            catch (AbandonedMutexException)
            {
                // El proceso anterior murió sin liberar: el mando pasa a nosotros.
                _mutex = mutex;
                return true;
            }

            mutex.Dispose();
            return false;
        }

        public static void EscucharInvitaciones(Action<string> recibir)
        {
            _ = Task.Run(async () =>
            {
                while (true)
                {
                    try
                    {
                        using var pipe = new NamedPipeServerStream(
                            NombreCanal(), PipeDirection.In, 1, PipeTransmissionMode.Byte,
                            PipeOptions.Asynchronous);
                        await pipe.WaitForConnectionAsync().ConfigureAwait(false);
                        using var reader = new StreamReader(pipe, Encoding.UTF8,
                            detectEncodingFromByteOrderMarks: false, bufferSize: 1024, leaveOpen: true);
                        string? enlace = await reader.ReadLineAsync().ConfigureAwait(false);
                        if (!string.IsNullOrWhiteSpace(enlace) && enlace.Length <= 4096)
                            recibir(enlace.Trim());
                    }
                    catch
                    {
                        await Task.Delay(250).ConfigureAwait(false);
                    }
                }
            });
        }

        public static bool EnviarInvitacionAInstanciaExistente(string enlace)
        {
            if (string.IsNullOrWhiteSpace(enlace) || enlace.Length > 4096) return false;
            for (int intento = 0; intento < 10; intento++)
            {
                try
                {
                    using var pipe = new NamedPipeClientStream(
                        ".", NombreCanal(), PipeDirection.Out, PipeOptions.Asynchronous);
                    pipe.Connect(300);
                    using var writer = new StreamWriter(pipe, Encoding.UTF8,
                        bufferSize: 1024, leaveOpen: true) { AutoFlush = true };
                    writer.WriteLine(enlace);
                    return true;
                }
                catch
                {
                    Thread.Sleep(100);
                }
            }
            return false;
        }

        /// <summary>Trae al frente la ventana del visor que ya estaba abierto.</summary>
        public static void EnfocarInstanciaExistente()
        {
            string nombre = NombreProceso();
            int propio = Environment.ProcessId;

            // La ventana del otro proceso puede tardar en publicar su handle.
            for (int intento = 0; intento < 30; intento++)
            {
                foreach (var proceso in Process.GetProcessesByName(nombre))
                {
                    using (proceso)
                    {
                        if (proceso.Id == propio || proceso.MainWindowHandle == IntPtr.Zero)
                            continue;

                        TraerAlFrente(proceso.MainWindowHandle);
                        return;
                    }
                }
                Thread.Sleep(200);
            }
        }

        /// <summary>
        /// Windows bloquea el robo de foco entre procesos; adjuntar la entrada al
        /// hilo en primer plano es lo que permite subir la ventana de forma fiable.
        /// </summary>
        private static void TraerAlFrente(IntPtr ventana)
        {
            ShowWindow(ventana, SW_RESTORE);

            uint hiloActual = GetCurrentThreadId();
            uint hiloFrente = GetWindowThreadProcessId(GetForegroundWindow(), out _);
            bool adjuntado = hiloFrente != 0 && hiloFrente != hiloActual &&
                             AttachThreadInput(hiloFrente, hiloActual, true);

            BringWindowToTop(ventana);
            SetForegroundWindow(ventana);

            if (adjuntado)
                AttachThreadInput(hiloFrente, hiloActual, false);
        }

        private static string NombreProceso()
            => Process.GetCurrentProcess().ProcessName;

        private static string NombreMutex()
        {
            string nombre = @"Local\WoldVirtualP2P3D." + NombreProceso();
            string? perfil = Environment.GetEnvironmentVariable("WVP_INSTANCE_ID")?.Trim();
            if (string.IsNullOrEmpty(perfil)) return nombre;

            // La vista previa puede abrir perfiles aislados en paralelo en el
            // mismo PC. El visor publicado no define esta variable y mantiene
            // exactamente su bloqueo de una sola instancia por proceso.
            foreach (char c in perfil)
            {
                if (!char.IsLetterOrDigit(c) && c != '.' && c != '_' && c != '-')
                    return nombre;
            }
            return nombre + "." + perfil;
        }

        private static string NombreCanal()
            => NombreMutex().Replace(@"Local\", "", StringComparison.OrdinalIgnoreCase)
                .Replace('\\', '_').Replace('.', '_');
    }
}
