"""Prueba de lobby, victorias y espectador contra un servidor ya en marcha (python app.py).
Ana (acierta siempre) juega contra Beto (falla siempre) y Cami los mira desde el lobby.
Uso: python tests/simulacion_lobby.py [url]"""
import json
import sys
import threading
import time
from pathlib import Path

import socketio

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
RUTA = Path(__file__).resolve().parent.parent / "data" / "preguntas.json"
CORRECTA = {q["pregunta"]: q["correcta"] for q in json.loads(RUTA.read_text(encoding="utf-8"))}


class Cliente:
    def __init__(self, nombre, modo):
        self.nombre, self.modo = nombre, modo
        self.sio = socketio.Client()
        self.lobby, self.eventos, self.fin = None, [], threading.Event()
        s = self.sio

        @s.on("lobby_state")
        def _(d): self.lobby = d

        @s.on("question")
        def _(d):
            c = CORRECTA[d["pregunta"]]
            s.emit("answer", {"opcion": c if self.modo == "bueno" else (c + 1) % 4})

        @s.on("game_over")
        def _(d): self.eventos.append(("game_over", d)); self.fin.set()

        for e in ("spec_state", "spec_question", "spec_round_result"):
            s.on(e, (lambda e: lambda d: self.eventos.append((e, d)))(e))

        @s.on("spec_over")
        def _(d): self.eventos.append(("spec_over", d)); self.fin.set()

    def entrar(self):
        self.sio.connect(URL)
        self.sio.emit("create_session", {"nombre": self.nombre})


def esperar(cond, t=10):
    fin = time.time() + t
    while time.time() < fin:
        if cond():
            return True
        time.sleep(0.1)
    return False


def estado_de(c, nombre):
    return next((j for j in c.lobby["jugadores"] if j["nombre"] == nombre), None)


if __name__ == "__main__":
    ana, beto, cami = Cliente("Ana", "bueno"), Cliente("Beto", "malo"), Cliente("Cami", "espectador")
    for c in (ana, beto, cami):
        c.entrar()
    assert esperar(lambda: cami.lobby and len(cami.lobby["jugadores"]) == 3), "el lobby no muestra a los 3 jugadores"
    assert {j["estado"] for j in cami.lobby["jugadores"]} == {"lobby"}
    print("lobby con 3 jugadores: OK")

    ana.sio.emit("join_queue")
    assert esperar(lambda: estado_de(cami, "Ana")["estado"] == "buscando"), "no se ve 'buscando'"
    beto.sio.emit("join_queue")
    assert esperar(lambda: cami.lobby["partidas"]), "no aparece la partida en curso"
    assert estado_de(cami, "Ana")["estado"] == "jugando"
    print("partida en curso visible en el lobby: OK")

    cami.sio.emit("spectate", {"id": cami.lobby["partidas"][0]["id"]})
    assert esperar(lambda: estado_de(cami, "Cami")["estado"] == "espectando"), "Cami no figura como espectando"
    assert all(c.fin.wait(60) for c in (ana, beto, cami)), "la partida no terminó"
    nombres = [e for e, _ in cami.eventos]
    assert "spec_state" in nombres and "spec_question" in nombres and "spec_round_result" in nombres
    over = next(d for e, d in cami.eventos if e == "spec_over")
    assert over["ganador"] == "Ana", over
    print(f"espectador recibió {nombres.count('spec_round_result')} rondas y el fin ({over['motivo']}): OK")

    assert esperar(lambda: estado_de(cami, "Ana")["victorias"] == 1 and not cami.lobby["partidas"]), "victoria no registrada"
    assert estado_de(cami, "Beto")["victorias"] == 0 and estado_de(cami, "Cami")["estado"] == "lobby"
    assert cami.lobby["jugadores"][0]["nombre"] == "Ana"            # ordenado por victorias
    print("victorias en el lobby y espectador de vuelta en el lobby: OK")

    ana.sio.emit("leave_session")
    assert esperar(lambda: estado_de(cami, "Ana") is None), "Ana sigue en el lobby tras salir"
    print("salir del lobby: OK")
    for c in (ana, beto, cami):
        c.sio.disconnect()
    print("TODO OK")
