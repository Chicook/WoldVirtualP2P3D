using System;
using System.Buffers;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace VisorSingularity
{
    internal static class CanonicalJson
    {
        public static byte[] ToCanonicalUtf8(JsonElement element)
        {
            using var ms = new MemoryStream();
            using (var writer = new Utf8JsonWriter(ms, new JsonWriterOptions { Indented = false }))
            {
                WriteCanonical(writer, element);
            }
            return ms.ToArray();
        }

        public static byte[] ToCanonicalUtf8(string json)
        {
            using var doc = JsonDocument.Parse(json);
            return ToCanonicalUtf8(doc.RootElement);
        }

        public static bool TryRemovePropertyAndCanonicalize(string json, string propertyNameToRemove, out byte[] canonicalUtf8)
        {
            canonicalUtf8 = Array.Empty<byte>();
            try
            {
                using var doc = JsonDocument.Parse(json);
                using var ms = new MemoryStream();
                using (var writer = new Utf8JsonWriter(ms, new JsonWriterOptions { Indented = false }))
                {
                    if (doc.RootElement.ValueKind != JsonValueKind.Object)
                        return false;

                    writer.WriteStartObject();
                    foreach (var prop in doc.RootElement.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal))
                    {
                        if (string.Equals(prop.Name, propertyNameToRemove, StringComparison.Ordinal))
                            continue;

                        writer.WritePropertyName(prop.Name);
                        WriteCanonical(writer, prop.Value);
                    }
                    writer.WriteEndObject();
                }
                canonicalUtf8 = ms.ToArray();
                return true;
            }
            catch (JsonException)
            {
                return false;
            }
        }

        private static void WriteCanonical(Utf8JsonWriter writer, JsonElement el)
        {
            switch (el.ValueKind)
            {
                case JsonValueKind.Object:
                    writer.WriteStartObject();
                    foreach (var prop in el.EnumerateObject().OrderBy(p => p.Name, StringComparer.Ordinal))
                    {
                        writer.WritePropertyName(prop.Name);
                        WriteCanonical(writer, prop.Value);
                    }
                    writer.WriteEndObject();
                    break;

                case JsonValueKind.Array:
                    writer.WriteStartArray();
                    foreach (var item in el.EnumerateArray())
                        WriteCanonical(writer, item);
                    writer.WriteEndArray();
                    break;

                default:
                    WriteRaw(writer, el);
                    break;
            }
        }

        private static void WriteRaw(Utf8JsonWriter writer, JsonElement el)
        {
            string raw = el.GetRawText();
            writer.WriteRawValue(raw, skipInputValidation: true);
        }
    }
}
