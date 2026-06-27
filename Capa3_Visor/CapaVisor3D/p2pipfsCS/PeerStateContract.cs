using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace VisorSingularity
{
    public class PeerStateContract
    {
        [JsonPropertyName("v")]
        public string Version { get; set; } = "1.1";

        [JsonPropertyName("id")]
        public string NodeId { get; set; } = string.Empty;

        [JsonPropertyName("ts")]
        public string Timestamp { get; set; } = string.Empty;

        [JsonPropertyName("u")]
        public Dictionary<string, object>? Users { get; set; }

        [JsonPropertyName("i")]
        public Dictionary<string, object>? Islands { get; set; }

        [JsonPropertyName("pk")]
        public string PublicKeyBase64 { get; set; } = string.Empty;

        [JsonPropertyName("sig")]
        public string Signature { get; set; } = string.Empty;

        public string GetSignablePayload()
        {
            var options = new JsonSerializerOptions 
            { 
                WriteIndented = false,
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
            };
            string uStr = Users != null ? JsonSerializer.Serialize(Users, options) : "";
            string iStr = Islands != null ? JsonSerializer.Serialize(Islands, options) : "";
            return $"{Version}|{NodeId}|{Timestamp}|{uStr}|{iStr}";
        }
    }
}
