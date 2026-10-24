"""Comprueba el cupo del lobby (11). Requiere el servidor en marcha: python tests/simulacion_cupo.py [url]"""
import sys
import time

import socketio

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
clientes = []
for i in range(12):
    c = socketio.Client(); c.sesion, c.error = None, None
    c.on("session_created", lambda d, c=c: setattr(c, "sesion", d))
    c.on("error", lambda d, c=c: setattr(c, "error", d))
    c.connect(URL); c.emit("create_session", {"nombre": f"J{i + 1}"}); clientes.append(c)
    time.sleep(0.15)
time.sleep(0.5)
dentro = [c for c in clientes if c.sesion]
assert len(dentro) == 11 and clientes[11].error == {"codigo": "lobby_lleno"}, (len(dentro), clientes[11].error)
print("11 entran, el jugador 12 recibe lobby_lleno: OK")
dentro[0].emit("leave_session"); time.sleep(0.4)
clientes[11].error = None; clientes[11].emit("create_session", {"nombre": "J12"}); time.sleep(0.4)
assert clientes[11].sesion and not clientes[11].error
print("al salir uno, el jugador 12 puede entrar: OK")
for c in clientes: c.disconnect()
