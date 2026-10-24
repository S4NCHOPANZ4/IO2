"""Cola FIFO simple para emparejar jugadores."""
import threading


class Cola:
    def __init__(self):
        self._ids = []
        self._lock = threading.Lock()

    def agregar(self, id_):
        with self._lock:
            if id_ not in self._ids:
                self._ids.append(id_)

    def quitar(self, id_):
        with self._lock:
            if id_ in self._ids:
                self._ids.remove(id_)

    def sacar_par(self):
        """Devuelve (a, b) si hay dos jugadores esperando, si no None."""
        with self._lock:
            if len(self._ids) >= 2:
                return self._ids.pop(0), self._ids.pop(0)
            return None

    def __len__(self):
        return len(self._ids)
