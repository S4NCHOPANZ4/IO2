"""Sesiones temporales en memoria con nombre y código de reconexión."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field

from config import ALFABETO_CODIGO, SESION_INACTIVA


@dataclass
class Sesion:
    id: str
    nombre: str
    codigo: str
    sid: str | None = None            # id de la conexión Socket.IO actual
    estado: str = "inactivo"          # inactivo | en_cola | en_partida
    conectado: bool = True
    partida_id: str | None = None
    victorias: int = 0                # puntos de victoria (solo mientras exista la sesión)
    espectando: str | None = None     # id de la partida que está viendo
    desde: float = 0.0                # marca de la última desconexión
    ultima: float = field(default_factory=time.time)

    def tocar(self):
        self.ultima = time.time()


class Sesiones:
    def __init__(self):
        self._por_id: dict[str, Sesion] = {}
        self._por_codigo: dict[str, Sesion] = {}

    def crear(self, nombre, sid):
        nombre = (nombre or "").strip()[:16] or f"Jugador-{secrets.randbelow(9000) + 1000}"
        codigo = self._codigo_nuevo()
        s = Sesion(id=secrets.token_hex(8), nombre=nombre, codigo=codigo, sid=sid)
        self._por_id[s.id] = s
        self._por_codigo[codigo] = s
        return s

    def _codigo_nuevo(self):
        while True:
            codigo = "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(6))
            if codigo not in self._por_codigo:
                return codigo

    def por_id(self, id_):
        return self._por_id.get(id_)

    def por_codigo(self, codigo):
        return self._por_codigo.get(str(codigo or "").strip().upper())

    def todas(self):
        return list(self._por_id.values())

    def eliminar(self, s):
        self._por_id.pop(s.id, None)
        self._por_codigo.pop(s.codigo, None)

    def por_sid(self, sid):
        return next((s for s in self._por_id.values() if s.sid == sid), None)

    def limpiar(self):
        """Borra sesiones desconectadas, sin partida y vencidas."""
        limite = time.time() - SESION_INACTIVA
        for s in list(self._por_id.values()):
            if not s.conectado and not s.partida_id and s.ultima < limite:
                del self._por_id[s.id]
                self._por_codigo.pop(s.codigo, None)
