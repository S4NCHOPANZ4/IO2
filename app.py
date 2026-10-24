"""Trivia Battle: lobby, partidas 1v1 y espectadores. Flask + Flask-SocketIO, todo en memoria."""
import threading
import time

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

import config as C
from game import questions
from game.cola import Cola
from game.match import Partida
from game.sessions import Sesiones

app = Flask(__name__)
socketio = SocketIO(app, async_mode="threading")

sesiones = Sesiones()
cola = Cola()
partidas = {}                 # id de partida -> Partida
intentos = {}                 # sid -> intentos de reconexión (límite de tasa)
BANCO = questions.cargar()
_lock = threading.RLock()
LOBBY = "lobby"               # sala de Socket.IO con todos los jugadores con sesión


@app.route("/")
def index():
    return render_template("index.html")


# ---------- utilidades ----------

def unir(sid, sala):
    socketio.server.enter_room(sid, sala, namespace="/")


def salir(sid, sala):
    socketio.server.leave_room(sid, sala, namespace="/")


def sala_espectadores(p):
    return f"esp:{p.id}"


def enviar(evento, datos, sesion):
    if sesion and sesion.sid:
        socketio.emit(evento, datos, to=sesion.sid)


def datos_sesion(s):
    return {"id": s.id, "nombre": s.nombre, "codigo": s.codigo, "victorias": s.victorias}


def payload_pregunta(p, pid=None):
    """Pregunta sin la respuesta correcta. 'restante' sirve al reconectar o entrar a ver a mitad de ronda."""
    q = p.pregunta
    return {
        "ronda": p.ronda + 1, "total": len(p.preguntas),
        "categoria": q["categoria"], "dificultad": q["dificultad"],
        "pregunta": q["pregunta"], "opciones": q["opciones"],
        "duracion": p.duracion,
        "restante": max(0.0, p.duracion - p.transcurrido()),
        "respondida": pid in p.respuestas,
    }


def payload_revision(p):
    """Pregunta ya cerrada con la respuesta correcta y su corrección, para la pausa entre rondas."""
    q = p.pregunta
    return {
        "ronda": p.ronda + 1, "total": len(p.preguntas),
        "categoria": q["categoria"], "dificultad": q["dificultad"],
        "pregunta": q["pregunta"], "opciones": q["opciones"],
        "correcta": q["correcta"], "feedback": q["feedback"],
        "pausa": C.SEGUNDOS_FEEDBACK,
        "restante_pausa": max(0.0, p.fin_feedback - time.monotonic()),
        "ultima": p.terminada(),
    }


def resultado_jugador(p, pid):
    rival = p.rival(pid)
    return {**payload_revision(p), "elegida": p.respuestas.get(pid, (None,))[0],
            "yo": {**p.ultimo[pid], "hp": p.hp[pid]},
            "rival": {**p.ultimo[rival], "hp": p.hp[rival]}}


def resultado_espectador(p):
    a, b = p.jugadores
    return {**payload_revision(p), "a": {**p.ultimo[a], "hp": p.hp[a]}, "b": {**p.ultimo[b], "hp": p.hp[b]}}


def estadisticas(p, pid):
    return {"nombre": sesiones.por_id(pid).nombre, "hp": p.hp[pid],
            "dano_total": p.dano_total[pid], "aciertos": p.aciertos[pid]}


# ---------- lobby ----------

def estado_visible(s):
    if s.espectando:
        return "espectando"
    if s.partida_id:
        return "jugando"
    return "buscando" if s.estado == "en_cola" else "lobby"


def estado_lobby():
    """Lo que ve todo el lobby. Nunca incluye códigos de reconexión."""
    with _lock:
        jugadores = [{"id": s.id, "nombre": s.nombre, "victorias": s.victorias, "estado": estado_visible(s)}
                     for s in sesiones.todas() if s.conectado or s.partida_id]
        jugadores.sort(key=lambda j: (-j["victorias"], j["nombre"].lower()))
        en_curso = []
        for p in partidas.values():
            a, b = p.jugadores
            en_curso.append({"id": p.id, "a": sesiones.por_id(a).nombre, "b": sesiones.por_id(b).nombre,
                             "hp_a": p.hp[a], "hp_b": p.hp[b],
                             "ronda": max(p.ronda + 1, 1), "total": len(p.preguntas)})
    return {"jugadores": jugadores, "partidas": en_curso, "max": C.MAX_LOBBY}


def emitir_lobby():
    socketio.emit("lobby_state", estado_lobby(), to=LOBBY)


# ---------- sesiones y reconexión ----------

@socketio.on("create_session")
def on_create_session(data):
    nombre = data.get("nombre", "") if isinstance(data, dict) else ""
    with _lock:
        if sum(1 for x in sesiones.todas() if x.conectado or x.partida_id) >= C.MAX_LOBBY:
            emit("error", {"codigo": "lobby_lleno"})
            return
        s = sesiones.crear(nombre if isinstance(nombre, str) else "", request.sid)
        unir(request.sid, LOBBY)
        emit("session_created", datos_sesion(s))
        emitir_lobby()


@socketio.on("leave_session")
def on_leave_session():
    s = sesiones.por_sid(request.sid)
    if not s or s.partida_id:
        return
    with _lock:
        cola.quitar(s.id)
        sesiones.eliminar(s)
        salir(request.sid, LOBBY)
        emit("session_closed")
        emitir_lobby()


@socketio.on("reconnect_with_code")
def on_reconnect(data):
    intentos[request.sid] = intentos.get(request.sid, 0) + 1
    if intentos[request.sid] > C.MAX_INTENTOS_RECONEXION:
        emit("error", {"codigo": "demasiados_intentos"})
        return
    codigo = data.get("codigo") if isinstance(data, dict) else None
    s = sesiones.por_codigo(codigo)
    if not s:
        emit("error", {"codigo": "session_expired"})
        return
    with _lock:
        s.sid, s.conectado, s.espectando = request.sid, True, None
        s.tocar()
        unir(request.sid, LOBBY)
        emit("session_created", datos_sesion(s))
        p = partidas.get(s.partida_id)
        if p:
            unir(request.sid, p.id)
            rival = p.rival(s.id)
            enviar("opponent_status", {"conectado": True}, sesiones.por_id(rival))
            emit("restore", {"fase": "partida", "yo": s.nombre, "rival": sesiones.por_id(rival).nombre,
                             "hp_yo": p.hp[s.id], "hp_rival": p.hp[rival], "total": len(p.preguntas)})
            if p.estado == "pregunta":
                emit("question", payload_pregunta(p, s.id))
            elif p.estado == "resultado" and p.ultimo:       # volvió durante la corrección
                emit("round_result", resultado_jugador(p, s.id))
        elif s.estado == "en_cola":
            emit("queue_status", {"en_cola": True})
        else:
            emit("restore", {"fase": "lobby"})
        emitir_lobby()


@socketio.on("disconnect")
def on_disconnect(*_):
    intentos.pop(request.sid, None)
    s = sesiones.por_sid(request.sid)
    if not s:
        return                      # conexión vieja: la sesión ya usa otra
    with _lock:
        s.conectado, s.sid, s.desde, s.espectando = False, None, time.time(), None
        s.tocar()
        cola.quitar(s.id)
        if s.estado == "en_cola":
            s.estado = "inactivo"
        p = partidas.get(s.partida_id)
        if p:
            enviar("opponent_status", {"conectado": False, "gracia": C.GRACIA_DESCONEXION},
                   sesiones.por_id(p.rival(s.id)))
            socketio.start_background_task(vigilar_desconexion, s.id, s.desde, p)
        emitir_lobby()


def vigilar_desconexion(id_, marca, p):
    """Si el jugador no vuelve durante el periodo de gracia, pierde por abandono."""
    socketio.sleep(C.GRACIA_DESCONEXION)
    with _lock:
        s = sesiones.por_id(id_)
        if s and not s.conectado and s.desde == marca and p.estado != "terminada":
            p.abandono = id_


# ---------- cola y emparejamiento ----------

@socketio.on("join_queue")
def on_join_queue():
    s = sesiones.por_sid(request.sid)
    if not s:
        emit("error", {"codigo": "sin_sesion"})
        return
    with _lock:
        if s.partida_id or s.espectando:
            return
        s.estado = "en_cola"
        cola.agregar(s.id)
        emit("queue_status", {"en_cola": True})
        par = cola.sacar_par()
        if par:
            crear_partida(*par)
        emitir_lobby()


@socketio.on("leave_queue")
def on_leave_queue():
    s = sesiones.por_sid(request.sid)
    if s and not s.partida_id:
        with _lock:
            cola.quitar(s.id)
            s.estado = "inactivo"
            emit("queue_status", {"en_cola": False})
            emitir_lobby()


def crear_partida(id_a, id_b):
    a, b = sesiones.por_id(id_a), sesiones.por_id(id_b)
    p = Partida(a.id, b.id, questions.elegir(BANCO))
    partidas[p.id] = p
    for s, rival in ((a, b), (b, a)):
        s.estado, s.partida_id = "en_partida", p.id
        unir(s.sid, p.id)
        enviar("match_found", {"yo": s.nombre, "rival": rival.nombre, "hp": C.HP_INICIAL,
                               "total": len(p.preguntas), "cuenta": C.CUENTA_REGRESIVA}, s)
    socketio.start_background_task(correr_partida, p)


# ---------- espectadores ----------

@socketio.on("spectate")
def on_spectate(data):
    s = sesiones.por_sid(request.sid)
    with _lock:
        p = partidas.get(data.get("id") if isinstance(data, dict) else None)
        if not s or not p or s.partida_id or s.espectando or s.estado != "inactivo":
            emit("error", {"codigo": "no_se_puede_ver"})
            return
        s.espectando = p.id
        unir(request.sid, sala_espectadores(p))
        a, b = p.jugadores
        emit("spec_state", {"a": sesiones.por_id(a).nombre, "b": sesiones.por_id(b).nombre,
                            "hp_a": p.hp[a], "hp_b": p.hp[b], "total": len(p.preguntas)})
        if p.estado == "pregunta":
            emit("spec_question", payload_pregunta(p))
        elif p.estado == "resultado" and p.ultimo:
            emit("spec_round_result", resultado_espectador(p))
        emitir_lobby()


@socketio.on("leave_spectate")
def on_leave_spectate():
    s = sesiones.por_sid(request.sid)
    if s and s.espectando:
        with _lock:
            p = partidas.get(s.espectando)
            if p:
                salir(request.sid, sala_espectadores(p))
            s.espectando = None
            emitir_lobby()


# ---------- partida ----------

@socketio.on("answer")
def on_answer(data):
    s = sesiones.por_sid(request.sid)
    p = partidas.get(s.partida_id) if s else None
    opcion = data.get("opcion") if isinstance(data, dict) else None
    if p and isinstance(opcion, int) and 0 <= opcion <= 3:
        p.responder(s.id, opcion)


def correr_partida(p):
    """Bucle de rondas. El servidor decide cuándo termina cada ronda y cada pausa de corrección."""
    socketio.sleep(C.CUENTA_REGRESIVA)
    while not p.abandono:
        p.iniciar_ronda()
        pregunta = {**payload_pregunta(p), "respondida": False}
        socketio.emit("question", pregunta, to=p.id)
        socketio.emit("spec_question", pregunta, to=sala_espectadores(p))
        limite = p.duracion + C.TOLERANCIA
        while not p.abandono and not p.todos_respondieron() and p.transcurrido() < limite:
            socketio.sleep(0.1)
        if p.abandono:
            break
        p.resolver()
        p.fin_feedback = time.monotonic() + C.SEGUNDOS_FEEDBACK
        for pid in p.jugadores:
            enviar("round_result", resultado_jugador(p, pid), sesiones.por_id(pid))
        socketio.emit("spec_round_result", resultado_espectador(p), to=sala_espectadores(p))
        emitir_lobby()                      # actualiza HP y ronda en «Partidas en curso»
        while not p.abandono and time.monotonic() < p.fin_feedback:
            socketio.sleep(0.2)             # ambos jugadores leen la corrección
        if p.abandono or p.terminada():
            break
    finalizar(p)


def finalizar(p):
    with _lock:
        if p.estado == "terminada":
            return
        p.estado = "terminada"
        ganador, motivo = p.resultado_final()
        if ganador:
            sesiones.por_id(ganador).victorias += 1
        a, b = p.jugadores
        socketio.emit("spec_over", {
            "ganador": sesiones.por_id(ganador).nombre if ganador else None, "motivo": motivo,
            "a": estadisticas(p, a), "b": estadisticas(p, b),
        }, to=sala_espectadores(p))
        for pid in p.jugadores:
            s = sesiones.por_id(pid)
            resultado = "empate" if ganador is None else ("victoria" if ganador == pid else "derrota")
            enviar("game_over", {"resultado": resultado, "motivo": motivo,
                                 "yo": estadisticas(p, pid), "rival": estadisticas(p, p.rival(pid))}, s)
            s.partida_id, s.estado = None, "inactivo"
            if s.sid:
                salir(s.sid, p.id)
        for s in sesiones.todas():          # los espectadores vuelven al lobby
            if s.espectando == p.id:
                s.espectando = None
                if s.sid:
                    salir(s.sid, sala_espectadores(p))
        partidas.pop(p.id, None)
        emitir_lobby()


# ---------- mantenimiento ----------

def limpiar_periodicamente():
    while True:
        socketio.sleep(60)
        with _lock:
            sesiones.limpiar()


socketio.start_background_task(limpiar_periodicamente)

if __name__ == "__main__":
    # host 0.0.0.0 permite probar desde otro dispositivo en la misma red Wi-Fi
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
