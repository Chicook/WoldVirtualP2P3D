using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace Visor3D.Chat
{
    public sealed class FriendRecord
    {
        public string Uid { get; set; } = "";
        public string Name { get; set; } = "";
        public long Since { get; set; }
    }

    public sealed class FriendRequestRecord
    {
        public string Uid { get; set; } = "";
        public string Code { get; set; } = "";
        public string Name { get; set; } = "";
        public long At { get; set; }
    }

    internal sealed class FriendsData
    {
        public string Owner { get; set; } = "";
        public List<FriendRecord> Friends { get; set; } = new();
        public List<FriendRequestRecord> Incoming { get; set; } = new();
        public List<FriendRequestRecord> Outgoing { get; set; } = new();
    }

    /// <summary>
    /// Lista de amigos y solicitudes de un perfil, guardada en
    /// %LocalAppData%\WoldVirtualP2P3D\user\friends_&lt;uid&gt;.json.
    /// Es un registro local: no se sincroniza entre equipos ni sale del PC.
    /// </summary>
    public sealed class FriendsStore
    {
        private static readonly JsonSerializerOptions Opciones = new()
        {
            WriteIndented = true,
            Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
        };

        private readonly string _ruta;
        private readonly FriendsData _datos;

        public string Owner => _datos.Owner;
        public IReadOnlyList<FriendRecord> Friends => _datos.Friends;
        public IReadOnlyList<FriendRequestRecord> Incoming => _datos.Incoming;
        public IReadOnlyList<FriendRequestRecord> Outgoing => _datos.Outgoing;

        private FriendsStore(string ruta, FriendsData datos)
        {
            _ruta = ruta;
            _datos = datos;
        }

        public static FriendsStore Load(string uid, string? carpetaBase = null)
        {
            string dueno = ChatProtocol.CleanUid(uid);
            if (dueno.Length == 0) dueno = ChatProtocol.BuildFallbackUid("Invitado");

            string carpeta = carpetaBase ?? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "WoldVirtualP2P3D", "user");
            try { Directory.CreateDirectory(carpeta); } catch { }

            string ruta = Path.Combine(carpeta, "friends_" + SanearArchivo(dueno) + ".json");
            FriendsData datos = new();
            try
            {
                if (File.Exists(ruta))
                {
                    var leido = JsonSerializer.Deserialize<FriendsData>(File.ReadAllText(ruta, Encoding.UTF8));
                    if (leido != null) datos = leido;
                }
            }
            catch { }

            datos.Owner = dueno;
            datos.Friends ??= new List<FriendRecord>();
            datos.Incoming ??= new List<FriendRequestRecord>();
            datos.Outgoing ??= new List<FriendRequestRecord>();

            Normalizar(datos);
            return new FriendsStore(ruta, datos);
        }

        public bool Guardar()
        {
            try
            {
                string temporal = _ruta + ".tmp";
                File.WriteAllText(temporal, JsonSerializer.Serialize(_datos, Opciones), new UTF8Encoding(false));
                File.Move(temporal, _ruta, true);
                return true;
            }
            catch
            {
                return false;
            }
        }

        public FriendRecord? BuscarAmigo(string uid)
        {
            string buscado = ChatProtocol.CleanUid(uid);
            return _datos.Friends.FirstOrDefault(f => f.Uid == buscado);
        }

        public bool EsAmigo(string uid) => BuscarAmigo(uid) != null;

        public void AgregarAmigo(string uid, string nombre)
        {
            string id = ChatProtocol.CleanUid(uid);
            if (id.Length == 0) return;

            var amigo = BuscarAmigo(id);
            if (amigo == null)
            {
                amigo = new FriendRecord { Uid = id, Since = Now() };
                _datos.Friends.Add(amigo);
            }

            string limpio = ChatProtocol.CleanName(nombre);
            if (limpio.Length > 0) amigo.Name = limpio;
            if (amigo.Since == 0) amigo.Since = Now();
        }

        public bool ActualizarNombreAmigo(string uid, string nombre)
        {
            var amigo = BuscarAmigo(uid);
            string limpio = ChatProtocol.CleanName(nombre);
            if (amigo == null || limpio.Length == 0 || amigo.Name == limpio) return false;
            amigo.Name = limpio;
            return true;
        }

        public void QuitarAmigo(string uid)
        {
            string id = ChatProtocol.CleanUid(uid);
            _datos.Friends.RemoveAll(f => f.Uid == id);
            _datos.Incoming.RemoveAll(r => r.Uid == id);
            _datos.Outgoing.RemoveAll(r => r.Uid == id);
        }

        public bool TieneEntrante(string uid)
        {
            string id = ChatProtocol.CleanUid(uid);
            return _datos.Incoming.Any(r => r.Uid == id);
        }

        public void AgregarEntrante(string uid, string nombre)
        {
            string id = ChatProtocol.CleanUid(uid);
            if (id.Length == 0) return;

            var solicitud = _datos.Incoming.FirstOrDefault(r => r.Uid == id);
            if (solicitud == null)
            {
                solicitud = new FriendRequestRecord { Uid = id, At = Now() };
                _datos.Incoming.Add(solicitud);
            }
            solicitud.Name = ChatProtocol.CleanName(nombre);
            solicitud.At = Now();
        }

        public void QuitarEntrante(string uid)
        {
            string id = ChatProtocol.CleanUid(uid);
            _datos.Incoming.RemoveAll(r => r.Uid == id);
        }

        /// <summary>
        /// Registra una solicitud enviada. Si se conoce el uid se usa como clave;
        /// si solo se conoce el código (destino aún desconectado), se guarda el
        /// código para resolverlo cuando esa persona aparezca en la sesión.
        /// </summary>
        public void RegistrarSaliente(string uid, string codigo, string nombre)
        {
            string id = ChatProtocol.CleanUid(uid);
            string code = (codigo ?? "").Trim().ToUpperInvariant();
            if (id.Length == 0 && code.Length == 0) return;

            var solicitud = _datos.Outgoing.FirstOrDefault(r =>
                (id.Length > 0 && r.Uid == id) ||
                (code.Length > 0 && string.Equals(r.Code, code, StringComparison.OrdinalIgnoreCase)));

            if (solicitud == null)
            {
                solicitud = new FriendRequestRecord { At = Now() };
                _datos.Outgoing.Add(solicitud);
            }

            if (id.Length > 0) solicitud.Uid = id;
            if (code.Length > 0 && id.Length == 0) solicitud.Code = code;
            if (id.Length > 0) solicitud.Code = "";
            if (!string.IsNullOrWhiteSpace(nombre)) solicitud.Name = ChatProtocol.CleanName(nombre);
            solicitud.At = Now();

            if (id.Length > 0) QuitarDuplicadosSalientes(solicitud, id);
        }

        public void ResolverSaliente(string destino, string uid, string nombre)
        {
            string id = ChatProtocol.CleanUid(uid);
            if (id.Length == 0) return;

            string original = ChatProtocol.CleanUid(destino);
            var solicitud = _datos.Outgoing.FirstOrDefault(r =>
                r.Uid == id ||
                (original.Length > 0 && string.Equals(r.Code, original, StringComparison.OrdinalIgnoreCase)));

            if (solicitud == null)
            {
                RegistrarSaliente(id, "", nombre);
                return;
            }

            solicitud.Uid = id;
            solicitud.Code = "";
            if (!string.IsNullOrWhiteSpace(nombre)) solicitud.Name = ChatProtocol.CleanName(nombre);

            QuitarDuplicadosSalientes(solicitud, id);
        }

        private void QuitarDuplicadosSalientes(FriendRequestRecord conservar, string uid)
        {
            string codigo = ChatProtocol.BuildFriendCode(uid);
            foreach (var duplicada in _datos.Outgoing.Where(r =>
                         r != conservar &&
                         (r.Uid == uid ||
                          (codigo.Length > 0 &&
                           r.Code.Length > 0 &&
                           string.Equals(r.Code, codigo, StringComparison.OrdinalIgnoreCase))))
                     .ToList())
                _datos.Outgoing.Remove(duplicada);
        }

        public void QuitarSaliente(string uidOCodigo)
        {
            string id = ChatProtocol.CleanUid(uidOCodigo);
            string code = (uidOCodigo ?? "").Trim().ToUpperInvariant();
            _datos.Outgoing.RemoveAll(r =>
                (id.Length > 0 && r.Uid == id) ||
                (code.Length > 0 && string.Equals(r.Code, code, StringComparison.OrdinalIgnoreCase)));
        }

        public bool TieneSaliente(string uidOCodigo)
        {
            string id = ChatProtocol.CleanUid(uidOCodigo);
            string code = (uidOCodigo ?? "").Trim().ToUpperInvariant();
            return _datos.Outgoing.Any(r =>
                (id.Length > 0 && r.Uid == id) ||
                (code.Length > 0 && string.Equals(r.Code, code, StringComparison.OrdinalIgnoreCase)));
        }

        private static void Normalizar(FriendsData datos)
        {
            var amigos = new List<FriendRecord>();
            var uidsAmigos = new HashSet<string>();
            foreach (var amigo in datos.Friends)
            {
                amigo.Uid = ChatProtocol.CleanUid(amigo.Uid);
                if (amigo.Uid.Length == 0 || !uidsAmigos.Add(amigo.Uid)) continue;
                if (!string.IsNullOrWhiteSpace(amigo.Name))
                    amigo.Name = ChatProtocol.CleanName(amigo.Name);
                amigos.Add(amigo);
            }
            datos.Friends = amigos;

            NormalizarSolicitudes(datos.Incoming);
            NormalizarSolicitudes(datos.Outgoing);
            datos.Incoming.RemoveAll(r => uidsAmigos.Contains(r.Uid));
            datos.Outgoing.RemoveAll(r => uidsAmigos.Contains(r.Uid));
        }

        private static void NormalizarSolicitudes(List<FriendRequestRecord> lista)
        {
            var vistos = new HashSet<string>();
            lista.RemoveAll(r =>
            {
                r.Uid = ChatProtocol.CleanUid(r.Uid);
                r.Code = (r.Code ?? "").Trim().ToUpperInvariant();
                if (r.Uid.Length == 0 && r.Code.Length == 0) return true;
                string clave = r.Uid.Length > 0 ? "u:" + r.Uid : "c:" + r.Code;
                return !vistos.Add(clave);
            });
            foreach (var r in lista)
            {
                if (!string.IsNullOrWhiteSpace(r.Name))
                    r.Name = ChatProtocol.CleanName(r.Name);
                if (r.Uid.Length > 0) r.Code = "";
                else r.Code = r.Code.ToUpperInvariant();
            }
        }

        private static string SanearArchivo(string uid)
        {
            var salida = new StringBuilder(uid.Length);
            foreach (char c in uid)
            {
                if (char.IsLetterOrDigit(c) || c == '-' || c == '_') salida.Append(c);
                else salida.Append('_');
            }
            return salida.Length > 0 ? salida.ToString() : "invitado";
        }

        private static long Now() => DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
    }
}
