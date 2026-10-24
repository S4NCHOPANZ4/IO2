"""Reglas de una partida 1v1. Lógica pura: sin Socket.IO, fácil de probar."""
import secrets
import threading
import time

from config import BONO_MAX, DIFICULTADES, HP_INICIAL


def calcular_dano(dificultad, tiempo_restante):
    """Daño base de la dificultad + bono de velocidad (hasta BONO_MAX)."""
    cfg = DIFICULTADES[dificultad]
    restante = min(max(tiempo_restante, 0), cfg["tiempo"])
    return cfg["dano"] + int(BONO_MAX * restante / cfg["tiempo"] + 0.5)


class Partida:
    def __init__(self, a, b, preguntas):
        self.id = secrets.token_hex(6)
        self.jugadores = (a, b)
        self.preguntas = preguntas
        self.ronda = -1
        self.estado = "cuenta"      # cuenta | pregunta | resultado | terminada
        self.hp = {a: HP_INICIAL, b: HP_INICIAL}
        self.dano_total = {a: 0, b: 0}
        self.aciertos = {a: 0, b: 0}
        self.tiempo_total = {a: 0.0, b: 0.0}   # suma de tiempos en aciertos
        self.respuestas = {}        # pid -> (opcion, segundos)
        self.inicio = 0.0
        self.abandono = None        # pid del jugador que abandonó
        self.ultimo = None          # resultado de la última ronda (por jugador)
        self.fin_feedback = 0.0     # instante en que termina la pausa de corrección
        self._lock = threading.Lock()

    def rival(self, pid):
        a, b = self.jugadores
        return b if pid == a else a

    @property
    def pregunta(self):
        return self.preguntas[self.ronda]

    @property
    def duracion(self):
        return DIFICULTADES[self.pregunta["dificultad"]]["tiempo"]

    def iniciar_ronda(self):
        with self._lock:
            self.ronda += 1
            self.respuestas = {}
            self.inicio = time.monotonic()
            self.estado = "pregunta"
        return self.pregunta

    def transcurrido(self):
        return time.monotonic() - self.inicio

    def responder(self, pid, opcion):
        """Registra solo la primera respuesta de cada jugador. El tiempo lo mide el servidor."""
        with self._lock:
            if self.estado != "pregunta" or pid not in self.hp or pid in self.respuestas:
                return False
            self.respuestas[pid] = (opcion, min(self.transcurrido(), self.duracion))
            return True

    def todos_respondieron(self):
        return len(self.respuestas) == 2

    def resolver(self):
        """Cierra la ronda y aplica el daño de ambos a la vez."""
        with self._lock:
            self.estado = "resultado"
            respuestas = dict(self.respuestas)
        res = {}
        for pid in self.jugadores:
            r = respuestas.get(pid)
            ok = r is not None and r[0] == self.pregunta["correcta"]
            dano = calcular_dano(self.pregunta["dificultad"], self.duracion - r[1]) if ok else 0
            if ok:
                self.aciertos[pid] += 1
                self.tiempo_total[pid] += r[1]
            res[pid] = {"correcto": ok, "dano": dano, "respondio": r is not None}
        for pid in self.jugadores:
            rival = self.rival(pid)
            self.hp[rival] = max(0, self.hp[rival] - res[pid]["dano"])
            self.dano_total[pid] += res[pid]["dano"]
        self.ultimo = res
        return res

    def terminada(self):
        return min(self.hp.values()) == 0 or self.ronda >= len(self.preguntas) - 1

    def resultado_final(self):
        """Devuelve (ganador_id | None, motivo)."""
        a, b = self.jugadores
        if self.abandono:
            return self.rival(self.abandono), "abandono"
        if self.hp[a] == 0 and self.hp[b] == 0:
            return None, "doble_ko"
        if self.hp[a] == 0 or self.hp[b] == 0:
            return (b if self.hp[a] == 0 else a), "ko"
        if self.hp[a] != self.hp[b]:
            return (a if self.hp[a] > self.hp[b] else b), "hp"
        if self.tiempo_total[a] != self.tiempo_total[b]:
            return (a if self.tiempo_total[a] < self.tiempo_total[b] else b), "desempate"
        return None, "empate"
