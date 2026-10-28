using System;
using System.IO;
using System.Text;
using Visor3D.Seguridad;
using Visor3D.Seguridad.SesionUnica;

namespace Visor3D.Services
{
    /// <summary>
    /// Prueba del arranque de cuenta (<c>--cuenta-selftest</c>). Trabaja sobre
    /// directorios temporales, nunca sobre el perfil real: comprueba el
    /// diagnóstico y que el reinicio archiva los restos sin tocar una cuenta
    /// completa.
    /// </summary>
    public static class CuentaSelfTest
    {
        public static int Run()
        {
            var salida = new StringBuilder();
            int fallos = 0;

            void Check(string nombre, bool ok, string detalle = "")
            {
                if (!ok) fallos++;
                string linea = $"[{(ok ? "OK" : "FALLO")}] {nombre}" +
                               (string.IsNullOrWhiteSpace(detalle) ? "" : $" — {detalle}");
                salida.AppendLine(linea);
                VisorLog.Info($"[cuenta-selftest] {linea}");
            }

            string raizBase = Path.Combine(Path.GetTempPath(), "wvp3d_cuenta_selftest_" + Guid.NewGuid().ToString("N"));

            try
            {
                checkDiagnostico(Check, raizBase, "equipo vacío", EstadoCuenta.SinIdentidad);
                checkDiagnostico(Check, raizBase, "sólo la llave", EstadoCuenta.Incompleta,
                                 d => Escribir(Path.Combine(d, "user", "llave_acceso.json"), "{}"));
                checkDiagnostico(Check, raizBase, "sólo el sello de PC", EstadoCuenta.Incompleta,
                                 d => Escribir(Path.Combine(d, "Seguridad", "pc_sello.json"), "{}"));
                checkDiagnostico(Check, raizBase, "credenciales con hash", EstadoCuenta.Completa,
                                 d => EscribirCredenciales(Path.Combine(d, "credentials.json"), "username", "lucia", true));
                checkDiagnostico(Check, raizBase, "perfil con hash", EstadoCuenta.Completa,
                                 d => EscribirCredenciales(Path.Combine(d, "user", "user_profile.json"), "nombre", "lucia", true));
                checkDiagnostico(Check, raizBase, "credenciales sin hash", EstadoCuenta.Incompleta,
                                 d => EscribirCredenciales(Path.Combine(d, "credentials.json"), "username", "lucia", false));
                checkDiagnostico(Check, raizBase, "credenciales corruptas", EstadoCuenta.Incompleta,
                                 d => Escribir(Path.Combine(d, "credentials.json"), "{ esto no es json"));

                // ── Restos a medias: se archivan y el equipo vuelve a cero ─────
                string raizRestos = NuevaRaiz(raizBase, "restos");
                string motorRestos = Path.Combine(raizRestos, "godot");
                EscribirCredenciales(Path.Combine(raizRestos, "credentials.json"), "username", "lucia", false);
                Escribir(Path.Combine(raizRestos, "Seguridad", "pc_sello.json"), "{}");
                Escribir(Path.Combine(raizRestos, "user", "llave_acceso.json"), "{}");
                Escribir(Path.Combine(motorRestos, "registro.cfg"), "[jugador]");

                ArranqueCuenta.AsegurarCicloRegistro(raizRestos, motorRestos);

                var estadoTras = PerfilUsuario.Diagnosticar(out string motivoTras, raizRestos);
                Check("los restos se archivan y el equipo queda sin identidad",
                      estadoTras == EstadoCuenta.SinIdentidad &&
                      !File.Exists(Path.Combine(raizRestos, "credentials.json")) &&
                      !File.Exists(Path.Combine(raizRestos, "Seguridad", "pc_sello.json")) &&
                      !File.Exists(Path.Combine(motorRestos, "registro.cfg")),
                      motivoTras);
                Check("el motor recibe la señal de reinicio",
                      File.Exists(Path.Combine(motorRestos, "reset_flag.txt")), motorRestos);
                Check("queda copia en respaldo_cuenta",
                      Directory.Exists(Path.Combine(raizRestos, "respaldo_cuenta")) &&
                      Directory.GetFiles(Path.Combine(raizRestos, "respaldo_cuenta"), "*", SearchOption.AllDirectories).Length >= 3,
                      Path.Combine(raizRestos, "respaldo_cuenta"));

                // ── Cuenta completa: no se toca ───────────────────────────────
                string raizBuena = NuevaRaiz(raizBase, "completa");
                string motorBuena = Path.Combine(raizBuena, "godot");
                string credencial = Path.Combine(raizBuena, "credentials.json");
                EscribirCredenciales(credencial, "username", "lucia", true);
                Escribir(Path.Combine(motorBuena, "registro.cfg"), "[jugador]");

                ArranqueCuenta.AsegurarCicloRegistro(raizBuena, motorBuena);

                Check("una cuenta completa no se archiva",
                      File.Exists(credencial) &&
                      File.Exists(Path.Combine(motorBuena, "registro.cfg")) &&
                      !Directory.Exists(Path.Combine(raizBuena, "respaldo_cuenta")),
                      credencial);

                // ── Equipo nuevo con motor viejo: sólo se limpia el motor ─────
                string raizNueva = NuevaRaiz(raizBase, "nueva");
                string motorNueva = Path.Combine(raizNueva, "godot");
                Escribir(Path.Combine(motorNueva, "registro.cfg"), "[jugador]");
                Escribir(Path.Combine(motorNueva, "avatar_hash.json"), "{}");

                ArranqueCuenta.AsegurarCicloRegistro(raizNueva, motorNueva);

                Check("sin cuenta se limpia sólo el estado del motor",
                      !File.Exists(Path.Combine(motorNueva, "registro.cfg")) &&
                      !File.Exists(Path.Combine(motorNueva, "avatar_hash.json")) &&
                      File.Exists(Path.Combine(motorNueva, "reset_flag.txt")),
                      motorNueva);
            }
            catch (Exception ex)
            {
                Check("Prueba de arranque de cuenta", false, $"{ex.GetType().Name}: {ex.Message}");
            }
            finally
            {
                try { if (Directory.Exists(raizBase)) Directory.Delete(raizBase, recursive: true); }
                catch { }
            }

            salida.AppendLine(fallos == 0
                ? "RESULTADO CUENTA: OK"
                : $"RESULTADO CUENTA: {fallos} FALLO(S)");
            try
            {
                Directory.CreateDirectory(VisorLog.Carpeta);
                File.WriteAllText(Path.Combine(VisorLog.Carpeta, "cuenta-selftest.log"), salida.ToString());
            }
            catch { }
            return fallos == 0 ? 0 : 1;
        }

        private static void checkDiagnostico(Action<string, bool, string> check, string raizBase,
                                             string nombre, EstadoCuenta esperado,
                                             Action<string>? preparar = null)
        {
            string raiz = NuevaRaiz(raizBase, nombre.Replace(' ', '_'));
            preparar?.Invoke(raiz);
            var obtenido = PerfilUsuario.Diagnosticar(out string motivo, raiz);
            check($"diagnóstico: {nombre}", obtenido == esperado,
                  $"esperado={esperado} obtenido={obtenido} ({motivo})");
        }

        private static string NuevaRaiz(string raizBase, string sufijo)
        {
            string raiz = Path.Combine(raizBase, sufijo);
            Directory.CreateDirectory(raiz);
            return raiz;
        }

        private static void EscribirCredenciales(string ruta, string campoUsuario, string usuario, bool conHash)
        {
            string hash = conHash ? "pbkdf2-sha256$1000$c2FsdA==$aGFzaA==" : "";
            Escribir(ruta, $"{{\"{campoUsuario}\":\"{usuario}\",\"passwordHash\":\"{hash}\"}}");
        }

        private static void Escribir(string ruta, string contenido)
        {
            string? dir = Path.GetDirectoryName(ruta);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            File.WriteAllText(ruta, contenido, Encoding.UTF8);
        }
    }
}
