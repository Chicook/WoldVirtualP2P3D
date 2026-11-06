using System;
using System.Collections.Generic;

namespace Visor3D.Services
{
    /// <summary>
    /// Límite de peticiones por clave (IP) con ventana deslizante en memoria.
    /// Pensado para sesiones cortas: no persiste y se reinicia con el visor.
    /// El número de claves rastreadas está acotado por CapacidadMaximaClaves:
    /// al insertar una clave nueva con el almacén lleno se expulsa la menos
    /// recientemente usada (LRU), así la memoria no crece sin límite aunque
    /// lleguen claves nuevas sin parar.
    /// </summary>
    public sealed class RateLimiter
    {
        // Capacidad máxima de claves (IP) rastreadas a la vez. Al superarla se
        // expulsa la clave menos recientemente usada (LRU): la memoria queda
        // acotada a CapacidadMaximaClaves ventanas, cada una con un máximo de
        // marcas igual al «maximo» que pase quien llama a Permitir.
        private const int CapacidadMaximaClaves = 4096;

        private readonly object _candado = new();
        private readonly Dictionary<string, Queue<DateTime>> _ventanas = new(StringComparer.OrdinalIgnoreCase);

        // Orden de uso de las claves: el primer nodo es la menos recientemente
        // usada y el último la más reciente. _nodos localiza el nodo de cada
        // clave en O(1) para moverlo al final en cada acceso y expulsar por
        // el principio al insertar con el almacén lleno.
        private readonly LinkedList<string> _ordenUso = new();
        private readonly Dictionary<string, LinkedListNode<string>> _nodos = new(StringComparer.OrdinalIgnoreCase);

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
                    _nodos[clave] = _ordenUso.AddLast(clave);

                    // Expulsión LRU: solo al insertar, si se supera la capacidad.
                    while (_ventanas.Count > CapacidadMaximaClaves)
                        ExpulsarMenosReciente();
                }
                else
                {
                    // Cada acceso (permitido o denegado) cuenta como uso: la
                    // clave pasa a ser la más reciente y no será la próxima
                    // expulsada mientras siga activa.
                    LinkedListNode<string> nodo = _nodos[clave];
                    _ordenUso.Remove(nodo);
                    _ordenUso.AddLast(nodo);
                }

                while (cola.Count > 0 && ahora - cola.Peek() > ventana)
                    cola.Dequeue();

                if (cola.Count >= maximo) return false;

                cola.Enqueue(ahora);

                return true;
            }
        }

        // Quita la clave menos recientemente usada de las tres estructuras.
        // Debe llamarse con _candado tomado y con al menos una clave presente.
        // La clave expulsada pierde su ventana: si vuelve a aparecer empieza
        // una ventana nueva (compromiso habitual de toda caché LRU).
        private void ExpulsarMenosReciente()
        {
            LinkedListNode<string> victima = _ordenUso.First!;
            _ordenUso.RemoveFirst();
            _nodos.Remove(victima.Value);
            _ventanas.Remove(victima.Value);
        }
    }
}
