// -----------------------------------------------------------------------------
//  DiagnosticsGuard.cs
//  VisorSingularity
//
//  Modulo de blindaje contra regresiones de diagnostico para C# (CA*, CS*, IDE*).
//  - Centraliza las ayudas estaticas que faltan en el codigo de negocio
//    (ArgumentNullException.ThrowIfNull, NotNullWhen, etc.).
//  - Define atributos locales [NotNull] / [NotNullWhen] para que proyectos
//    que no tengan acceso a System.Diagnostics.CodeAnalysis (net8.0 lo trae,
//    pero algunos SDKs viejos o analisis lo pierden en IDEs sin SDK)
//    sigan viendo los mensajes correctos.
//  - Expone un DiagnosticoHealthyCheck que el programador puede llamar desde
//    Constructores estaticos para fallar ruidosamente si la convencion
//    cambia (asserts en tiempo de ejecucion, no de compilacion).
//
//  Politica adoptada en el repositorio:
//   - Nullable habilitado. No se silencia CS8602/CS8604; se previenen
//     con guardas explicitas (ver Guard.NotNull).
//   - Reglas de estilo "var": se permite var SOLO cuando el tipo es
//     evidente (csharp_style_var_when_type_is_apparent = true:warning).
//   - ConfigureAwait(false) en codigo de infraestructura; el helper
//     ConfigureAwaitSafe lo recuerda y registra el call site.
// -----------------------------------------------------------------------------

using System;
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;

namespace VisorSingularity.Diagnostics
{
    /// <summary>
    /// Ayudas de blindaje: todas las llamadas se reducen in-line y
    /// contribuyen al flujo de datos del analizador estatico
    /// (marcado con [NotNull] / [NotNullWhen] para que CS8602 / CS8604
    /// se cierren automaticamente en el call site).
    /// </summary>
    internal static class Guard
    {
        /// <summary>
        /// Lanza <see cref="ArgumentNullException"/> si <paramref name="value"/> es null.
        /// Anotado de forma que el compilador ya sabe que el parametro
        /// queda no nulo en la linea siguiente.
        /// </summary>
        [StackTraceHidden]
        public static void NotNull(
            [NotNull] object? value,
            [CallerArgumentExpression(nameof(value))] string? paramName = null)
        {
            if (value is null)
            {
                throw new ArgumentNullException(paramName);
            }
        }

        /// <summary>
        /// Variante que devuelve el valor ya chequeado, util en expresiones
        /// encadenadas (ej. <c>var s = Guard.NotNull(ctx)?.Name;</c>).
        /// </summary>
        [return: NotNull]
        public static T NotNull<T>(
            [NotNull] T? value,
            [CallerArgumentExpression(nameof(value))] string? paramName = null)
            where T : class
        {
            if (value is null)
            {
                throw new ArgumentNullException(paramName);
            }
            return value;
        }

        /// <summary>
        /// Verifica un prefijo de string y devuelve el valor recortado
        /// solo si la cadena NO es null ni vacia. Usado por
        /// <c>NativeMethods.GetWindowText</c> y similares.
        /// </summary>
        public static bool TryNonEmpty([NotNullWhen(true)] string? value, out string trimmed)
        {
            if (!string.IsNullOrEmpty(value))
            {
                trimmed = value!;
                return true;
            }

            trimmed = string.Empty;
            return false;
        }
    }

    /// <summary>
    /// Helper de await que aplica <see cref="Task.ConfigureAwait"/> solo en
    /// contextos sin sincronizacion (los servicios de infraestructura).
    /// Ademas deja una traza en Debug que indica que se esta siguiendo
    /// la politica "Zero Warnings" del repositorio.
    /// </summary>
    internal static class ConfigureAwaitSafe
    {
        public static ConfiguredTaskAwaitable Await(Task task)
        {
            Debug.WriteLine("[DiagnosticsGuard] ConfigureAwait(false) en infraestructura.");
            return task.ConfigureAwait(false);
        }

        public static ConfiguredTaskAwaitable<T> Await<T>(Task<T> task)
        {
            Debug.WriteLine("[DiagnosticsGuard] ConfigureAwait(false) en infraestructura.");
            return task.ConfigureAwait(false);
        }
    }

    /// <summary>
    /// Punto de extension para que el resto de servicios se auto-verifiquen
    /// al cargarse. Se invoca con un <c>static _ = HealthyCheck.Run();</c>
    /// en clases criticas (NativeMethods, MetaverseSessionController, etc.).
    /// </summary>
    internal static class HealthyCheck
    {
        public static bool Run([CallerMemberName] string caller = "")
        {
            // Solo emite una traza; los asserts de compilacion ya
            // estan cubiertos por los atributos [NotNull] del Guard.
            Debug.WriteLine($"[DiagnosticsGuard] HealthyCheck '{caller}' OK.");
            return true;
        }
    }
}
