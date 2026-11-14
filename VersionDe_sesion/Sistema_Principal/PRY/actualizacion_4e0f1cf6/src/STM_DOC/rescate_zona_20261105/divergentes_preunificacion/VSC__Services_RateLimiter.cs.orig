using System;
using System.Collections.Generic;

namespace Visor3D.Services
{
    /// <summary>
    /// Límite de peticiones por clave (IP) con ventana deslizante en memoria.
    /// Pensado para sesiones cortas: no persiste y se reinicia con el visor.
    /// </summary>
    public sealed class RateLimiter
    {
        private readonly object _candado = new();
        private readonly Dictionary<string, Queue<DateTime>> _ventanas = new(StringComparer.OrdinalIgnoreCase);

        public bool Permitir(string clave, int maximo, TimeSpan ventana)
        {
            if (string.IsNullOrWhiteSpace(clave)) clave = "desconocida";
            if (maximo <= 0) return true;

            lock (_candado)
            {
                DateTime ahora = DateTime.UtcNow;

                if (!_ventanas.TryGetValue(clave, out Queue<DateTime>? cola))
                {
                    cola = new Queue<DateTime>();
                    _ventanas[clave] = cola;
                }

                while (cola.Count > 0 && ahora - cola.Peek() > ventana)
                    cola.Dequeue();

                if (cola.Count >= maximo) return false;

                cola.Enqueue(ahora);

                // Poda perezosa: si hay muchas claves, se quitan las ventanas vacías.
                if (_ventanas.Count > 1000)
                {
                    var vacias = new List<string>();
                    foreach (var par in _ventanas)
                        if (par.Value.Count == 0) vacias.Add(par.Key);
                    foreach (string k in vacias) _ventanas.Remove(k);
                }

                return true;
            }
        }
    }
}
