"""Simula dos jugadores contra un servidor ya en marcha (python app.py).
Uso: python tests/simulacion.py [url]   -> juega una partida completa de punta a punta."""
import sys
import threading
import time

import socketio

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"


def jugador(nombre, acierta, log):
    sio = socketio.Client()
    estado = {"fin": threading.Event()}

    @sio.on("session_created")
    def _(d):
        log.append(f"{nombre}: sesión {d['codigo']}")
        sio.emit("join_queue")

    @sio.on("question")
    def _(d):
        # No conocemos la respuesta correcta: el bot que "acierta" prueba la opción 0..3 según ronda
        sio.emit("answer", {"opcion": 0 if acierta else 3})

    @sio.on("round_result")
    def _(d):
        log.append(f"{nombre}: ronda {d['ronda']} yo={d['yo']['dano']} rival={d['rival']['dano']} hp={d['yo']['hp']}/{d['rival']['hp']}")

    @sio.on("game_over")
    def _(d):
        log.append(f"{nombre}: FIN {d['resultado']} ({d['motivo']}) {d['yo']['hp']}-{d['rival']['hp']}")
        estado["fin"].set()

    sio.connect(URL)
    sio.emit("create_session", {"nombre": nombre})
    estado["fin"].wait(timeout=90)
    sio.disconnect()
    return estado["fin"].is_set()


if __name__ == "__main__":
    log, res = [], {}
    hilos = [threading.Thread(target=lambda n=n, a=a: res.__setitem__(n, jugador(n, a, log)))
             for n, a in (("Ana", True), ("Beto", False))]
    for h in hilos:
        h.start(); time.sleep(0.3)
    for h in hilos:
        h.join()
    print("\n".join(log))
    print("OK" if all(res.values()) else "FALLÓ: la partida no terminó", res)
