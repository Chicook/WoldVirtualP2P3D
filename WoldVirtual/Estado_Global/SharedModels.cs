using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace WoldVirtual.EstadoGlobal.Models
{
    /// <summary>
    /// Datos maestros del estado de una isla/mundo.
    /// </summary>
    public class IslandStateData
    {
        [JsonPropertyName("users")]
        public Dictionary<string, object> Users { get; set; } = [];

        [JsonPropertyName("islands")]
        public Dictionary<string, IslandInfo> Islands { get; set; } = [];

        [JsonPropertyName("last_updated")]
        public DateTime LastUpdated { get; set; } = DateTime.UtcNow;

        [JsonPropertyName("active_avatar")]
        public AvatarInfo? ActiveAvatar { get; set; }
    }

    /// <summary>
    /// Información básica de una isla.
    /// </summary>
    public record IslandInfo(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("last_modified")] DateTime? LastModifiedAt = null
    );

    /// <summary>
    /// Información de un avatar en el metaverso.
    /// </summary>
    public record AvatarInfo(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("is_active")] bool IsActive = true
    );

    /// <summary>
    /// Estado de la sesión actual del usuario.
    /// </summary>
    public class SessionState
    {
        [JsonPropertyName("session_id")]
        public string SessionId { get; set; } = Guid.NewGuid().ToString("N")[..8].ToUpper();

        [JsonPropertyName("user_info")]
        public Dictionary<string, object> UserInfo { get; set; } = [];

        [JsonPropertyName("islands_visited")]
        public List<IslandVisit> IslandsVisited { get; set; } = [];

        [JsonPropertyName("start_time")]
        public DateTime StartTime { get; set; } = DateTime.UtcNow;

        [JsonPropertyName("end_time")]
        public DateTime? EndTime { get; set; }

        [JsonPropertyName("is_active")]
        public bool IsActive { get; set; } = true;

        [JsonPropertyName("duration_seconds")]
        public int DurationSeconds { get; set; }
    }

    /// <summary>
    /// Registro de visita a una isla.
    /// </summary>
    public record IslandVisit(
        [property: JsonPropertyName("island_id")] string IslandId,
        [property: JsonPropertyName("island_name")] string IslandName,
        [property: JsonPropertyName("visit_time")] DateTime VisitTime,
        [property: JsonPropertyName("duration_seconds")] int DurationSeconds = 0
    );
}

namespace WoldVirtual.EstadoGlobal.Helpers
{
    using WoldVirtual.EstadoGlobal.Models;

    /// <summary>
    /// Logger unificado para el estado global.
    /// </summary>
    public static class GlobalLogger
    {
        private static readonly string LogDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "logs");

        static GlobalLogger() => Directory.CreateDirectory(LogDir);

        public static void Info(string msg) => Log("INFO", msg);
        public static void Warning(string msg) => Log("WARN", msg);
        public static void Error(string msg, Exception? ex = null) => Log("ERROR", $"{msg} {(ex != null ? $"| {ex.Message}" : "")}");

        private static void Log(string level, string msg)
        {
            var line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] {msg}";
            Console.WriteLine(line);
            try { File.AppendAllLines(Path.Combine(LogDir, "estado_global.log"), [line]); } catch { }
        }
    }

    /// <summary>
    /// Validador de esquemas JSON para peers.
    /// </summary>
    public static class PeerValidator
    {
        public static bool IsValid(JsonDocument doc, out string? error)
        {
            error = null;
            if (doc.RootElement.ValueKind != JsonValueKind.Object)
            {
                error = "El root debe ser un objeto.";
                return false;
            }
            return true;
        }
    }

    /// <summary>
    /// Contexto para Source Generation de JSON (Rendimiento y AOT).
    /// </summary>
    [JsonSourceGenerationOptions(WriteIndented = true, PropertyNamingPolicy = JsonKnownNamingPolicy.Unspecified)]
    [JsonSerializable(typeof(IslandStateData))]
    [JsonSerializable(typeof(SessionState))]
    [JsonSerializable(typeof(List<IslandInfo>))]
    public partial class GlobalJsonContext : JsonSerializerContext
    {
    }
}
