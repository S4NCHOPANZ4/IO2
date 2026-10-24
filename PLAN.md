# Trivia Battle MVP: Plan del proyecto

> **Estado:** plan completo, pendiente de aprobación. No se ha escrito código todavía.
> **Objetivo:** demostrar a stakeholders un juego de trivia 1v1 en tiempo real, simple, limpio y listo para demo.

---

## 1. Resumen

Dos jugadores entran a una cola, se emparejan en una sala y responden las mismas **5 preguntas** al mismo tiempo. Cada jugador empieza con **100 HP**. Una respuesta correcta daña al oponente. Gana quien deje al rival sin HP o quien tenga más HP al terminar la quinta pregunta.

El servidor es la autoridad: controla el reloj, los tiempos de respuesta, el daño y el estado de la partida. El navegador solo muestra información y envía respuestas.

### Qué incluye y qué no

| Incluido | Fuera de alcance |
|---|---|
| Cola y emparejamiento 1v1 | Cuentas de usuario y login |
| 5 preguntas por partida con cuenta regresiva por dificultad | Base de datos o persistencia |
| Barras de HP, daño y puntuación claros | Rankings y estadísticas históricas |
| Nombre temporal y código de reconexión | Varias categorías a elección, salas privadas |
| Interfaz 100 % en español | Escalado a varios procesos o servidores |
| Desarrollo y pruebas en local | Despliegue (se recomienda opción, no se despliega aún) |

---

## 2. Stack

- **Backend:** Python, Flask, Flask-SocketIO
- **Frontend:** Jinja2, HTML, CSS, JavaScript puro (sin frameworks)
- **Banco de preguntas:** archivo JSON
- **Estado:** solo en memoria (sesiones, cola, partidas)
- **Modo asíncrono:** `threading` con `simple-websocket`, para que el mismo código funcione en local y luego en la nube con un solo proceso

---

## 3. Reglas del juego

### 3.1 Estructura de la partida

- 5 preguntas por partida, elegidas por dificultad en este orden: **fácil, fácil, media, media, difícil**.
- Ambos jugadores ven la misma pregunta y responden al mismo tiempo.
- La ronda termina cuando ambos responden o cuando se acaba el tiempo.
- Se muestra la respuesta correcta y el daño durante unos 3 segundos antes de la siguiente pregunta.
- Antes de la primera pregunta hay una cuenta regresiva 3-2-1.

### 3.2 Tiempo, daño y puntuación

| Dificultad | Tiempo | Daño base | Daño máximo (con bono) |
|---|---|---|---|
| Fácil | 10 s | 10 | 20 |
| Media | 15 s | 15 | 25 |
| Difícil | 20 s | 20 | 30 |

- **Bono de velocidad:** hasta +10, proporcional al tiempo restante al responder.
  `bono = redondear(10 × tiempo_restante / tiempo_total)`
- **Ejemplo:** pregunta media respondida con 9 s de 15 s restantes → 15 + 6 = **21 de daño**.
- **Respuesta incorrecta o sin respuesta:** 0 de daño. No hay autodaño.
- **Resolución simultánea:** el daño de ambos jugadores se aplica al final de la ronda, así que los dos pueden golpearse en la misma ronda.
- **Puntos:** son el daño total infligido. Un solo número fácil de explicar.
- **HP:** nunca baja de 0.

### 3.3 Fin de la partida

1. **KO:** si un jugador llega a 0 HP, la partida termina al mostrar el resultado de esa ronda.
2. **Si ambos llegan a 0 HP en la misma ronda:** empate.
3. **Tras la pregunta 5:** gana quien tenga más HP.
4. **Si el HP es igual:** gana quien tenga menor tiempo total de respuesta en sus aciertos.
5. **Si sigue igual:** empate.

---

## 4. Banco de preguntas (`data/preguntas.json`)

| Campo | Descripción |
|---|---|
| `id` | Identificador único |
| `categoria` | Texto corto (ej. "Ciencia", "Historia") |
| `pregunta` | Enunciado en español |
| `opciones` | Lista de 4 opciones |
| `correcta` | Índice (0 a 3) de la opción correcta |
| `dificultad` | `facil`, `media` o `dificil` |

- El tiempo y el daño base **no** se guardan en cada pregunta. Salen de la dificultad, definida en una pequeña tabla de configuración.
- Se incluirán unas **20 preguntas de ejemplo** en español: 8 fáciles, 8 medias y 4 difíciles.
- El servidor **nunca** envía el índice correcto antes de revelar la ronda.
- Las preguntas de una partida no se repiten.

---

## 5. Estructura del proyecto

```
trivia-battle/
├── app.py                  # App Flask, SocketIO y manejadores de eventos
├── config.py               # Tiempos, daños, grace period, constantes
├── game/
│   ├── sessions.py         # Sesiones, nombres, códigos de reconexión
│   ├── queue.py            # Cola FIFO y emparejamiento
│   ├── match.py            # Reglas, daño, temporizadores, estado de la partida
│   └── questions.py        # Carga y selección de preguntas
├── data/
│   └── preguntas.json
├── templates/
│   ├── base.html
│   ├── index.html          # Inicio: nombre, buscar partida, reconexión
│   └── partida.html        # Cola, cuenta regresiva, partida, resultado
├── static/
│   ├── css/style.css
│   └── js/client.js        # Eventos de socket y actualización del DOM
├── tests/
│   └── test_logic.py       # Daño, ganador, desempate, cola
├── requirements.txt
└── README.md
```

Todos los textos de la interfaz viven en un solo objeto `TEXTOS` en `client.js` y en las plantillas, para mantener el español consistente y fácil de editar.

---

## 6. Estado en memoria

**Sesión:** id de jugador, nombre, código de reconexión, `sid` actual de Socket.IO, estado (`inactivo`, `en_cola`, `en_partida`, `desconectado`), id de sala, hora de última actividad.

**Partida:** dos sesiones, 5 preguntas elegidas, índice de la pregunta actual, HP de cada jugador, daño total de cada uno, tiempo total de respuesta de cada uno en aciertos, respuestas de la ronda, hora de inicio de la pregunta, estado (`cuenta_regresiva`, `pregunta`, `resultado`, `terminada`).

**Cola:** lista FIFO de ids de sesión.

Un candado (`Lock`) protege el emparejamiento para evitar que dos eventos simultáneos creen partidas duplicadas.

---

## 7. Flujo de la partida

### 7.1 Entrada y emparejamiento

1. El jugador escribe un nombre o lo deja en blanco.
2. El servidor crea la sesión y devuelve el código de reconexión.
3. El cliente envía `join_queue` y ve "Buscando oponente…" con botón de cancelar.
4. Cuando hay dos jugadores en cola, el servidor los saca, crea la partida y los une a una sala de Socket.IO.
5. Ambos reciben `match_found` y comienza la cuenta regresiva 3-2-1.

### 7.2 Bucle de rondas (5 veces)

1. El servidor envía `question` con enunciado, opciones, duración y número de ronda.
2. Cada jugador envía `answer`. Solo cuenta la primera respuesta, y el servidor mide el tiempo.
3. La ronda termina cuando ambos respondieron o expira el tiempo.
4. El servidor calcula el daño, actualiza el HP y envía `round_result` con la respuesta correcta, el daño de cada jugador y el HP nuevo.
5. Si hay KO o fue la ronda 5, envía `game_over`. Si no, pasa a la siguiente pregunta.

### 7.3 Cuenta regresiva en tiempo real

- El servidor decide la duración según la dificultad y la envía en `question`.
- El cliente cuenta hacia atrás localmente para una barra de tiempo fluida.
- El servidor cierra la ronda con su propio temporizador. El reloj del cliente no se usa para puntuar.
- Si un jugador se reconecta a mitad de pregunta, recibe el tiempo restante real.

---

## 8. Sesiones, nombres y código de reconexión

### 8.1 Nombre temporal

- Máximo 16 caracteres, escrito por el jugador.
- Si queda en blanco, se genera uno tipo `Jugador-4821`.
- No es único y desaparece con la sesión.
- Se muestra siempre con `textContent` (nunca `innerHTML`) para evitar inyección de HTML.

### 8.2 Código de reconexión

- 6 caracteres, letras mayúsculas y dígitos, sin caracteres confusos (0/O, 1/I).
- Se muestra en pantalla como "Código de reconexión" y se guarda en el navegador.
- Un refresco o una caída de red reconecta automáticamente con ese código.
- Si se pierden los datos del navegador, el jugador puede escribirlo en la pantalla de inicio.
- Sirve como "llave": quien tenga el código puede tomar la sesión. Es aceptable para una demo sin cuentas. Se limita la tasa de intentos de reconexión.

### 8.3 Desconexión durante una partida

- La sesión se marca como `desconectado` y arranca un periodo de gracia de **30 segundos**.
- El reloj de la partida **sigue corriendo**. Las rondas sin responder cuentan como 0 de daño.
- El oponente ve "Oponente desconectado".
- Si el jugador vuelve a tiempo, recibe una instantánea del estado: HP, ronda, tiempo restante y marcador.
- Si vence el periodo de gracia, pierde por abandono.

### 8.4 Reinicio del servidor

Todo está en memoria, así que un reinicio borra sesiones, cola y partidas.

1. Socket.IO intenta reconectar solo cuando el servidor vuelve.
2. El cliente envía su código y el servidor no lo reconoce, así que responde `session_expired`.
3. El cliente borra el código guardado y vuelve al inicio con el mensaje "El servidor se reinició. Vuelve a entrar."
4. Las partidas en curso se pierden para ambos jugadores y no hay recuperación.

Es un compromiso aceptable para una demo. Si algún día hiciera falta sobrevivir a reinicios, el siguiente paso mínimo sería Redis, pero queda fuera de este MVP.

### 8.5 Limpieza

Una tarea periódica elimina sesiones inactivas, códigos vencidos y partidas terminadas para que la memoria no crezca.

---

## 9. Eventos de Socket.IO

**Cliente → servidor**

| Evento | Uso |
|---|---|
| `create_session` | Crear sesión con nombre opcional |
| `join_queue` / `leave_queue` | Entrar o salir de la cola |
| `answer` | Enviar la opción elegida en la ronda actual |
| `reconnect_with_code` | Recuperar una sesión con el código |

**Servidor → cliente**

| Evento | Uso |
|---|---|
| `session_created` | Devuelve nombre y código de reconexión |
| `queue_status` | Estado de la cola |
| `match_found` | Oponente encontrado, inicia cuenta regresiva |
| `question` | Pregunta, opciones, duración, número de ronda |
| `round_result` | Respuesta correcta, daño, HP nuevo, marcador |
| `opponent_status` | Oponente desconectado o de vuelta |
| `game_over` | Resultado final y motivo (KO, HP, desempate, abandono, empate) |
| `error` | Errores como `session_expired` |

---

## 10. Pantallas (todas en español)

1. **Inicio:** campo de nombre, botón "Buscar partida", campo para código de reconexión.
2. **Buscando oponente:** indicador de espera y botón "Cancelar".
3. **Cuenta regresiva:** 3-2-1 con los nombres de ambos jugadores.
4. **Partida:** dos barras de HP (100 → 0), pregunta, 4 opciones, barra de tiempo, número de ronda, daño flotante.
5. **Resultado de ronda:** respuesta correcta, daño de cada jugador, HP actualizado.
6. **Final:** ganador o empate, daño total, aciertos y botón "Jugar de nuevo".

---

## 11. Desarrollo y pruebas en local

- Se ejecuta con un solo proceso (`python app.py`).
- Para probar dos jugadores: una ventana normal y una ventana de incógnito en `localhost`.
- Para una demo más realista: ejecutar con host `0.0.0.0` y conectar un segundo dispositivo en la misma red Wi-Fi.
- **Pruebas unitarias** (lógica pura): cálculo de daño, bono de velocidad, ganador, desempate, emparejamiento de la cola.
- **Lista de pruebas manuales:**
  1. Emparejar a dos jugadores.
  2. Jugar una partida completa.
  3. Provocar un KO.
  4. Refrescar el navegador a mitad de partida.
  5. Reconectar con el código.
  6. Dejar pasar los 30 s de gracia y verificar el abandono.
  7. Reiniciar el servidor a mitad de partida.
  8. Salir de la cola antes de emparejarse.
  9. Doble clic o doble respuesta en una ronda.

---

## 12. Recomendación de hosting gratuito (sin desplegar todavía)

**Opción recomendada: Render (servicio web gratuito).**

- Un servicio gratuito vuelve a arrancar con una petición HTTP o una nueva conexión WebSocket.
- Desde febrero de 2026, el servicio gratuito se apaga tras 15 minutos sin peticiones HTTP ni mensajes WebSocket de una conexión existente. Con dos jugadores activos hay tráfico constante, así que no se corta en plena partida.
- Se despliega desde GitHub con un comando de inicio de Gunicorn.

**Limitaciones a considerar:**

- Render puede reiniciar un servicio gratuito en cualquier momento, lo que borra el estado en memoria. Para eso están el código de reconexión y el mensaje `session_expired`.
- Un servicio dormido tarda en despertar: conviene abrir la URL unos minutos antes de la demo.
- Debe correr con **un solo worker**, porque las colas en memoria no funcionan entre varios procesos.

**Alternativa descartada: Koyeb (instancia gratuita).** Tiene 512 MB de RAM y 0,1 vCPU, se escala a cero tras 1 hora sin tráfico y eso no se puede desactivar. Además, su documentación indica que una conexión WebSocket que despierta un servicio dormido puede durar solo unos minutos, lo que encaja mal con juego en tiempo real.

Referencias: <https://render.com/docs/free> y <https://www.koyeb.com/docs/run-and-scale/scale-to-zero>

---

## 13. Riesgos y decisiones

| Tema | Decisión |
|---|---|
| Un solo proceso | Obligatorio para que la cola en memoria funcione |
| Trampas | El tiempo se mide en el servidor y la respuesta correcta no se envía antes de revelar |
| Doble pestaña | La sesión toma el `sid` de la última conexión |
| Respuestas duplicadas | Solo cuenta la primera por jugador y ronda |
| Jugador solo en cola | Espera hasta que llegue otro o cancela |
| Ambos se desconectan | La partida se cierra tras el periodo de gracia |
| XSS en nombres | Siempre `textContent`, longitud máxima de 16 |
| Código adivinable | 6 caracteres aleatorios y límite de intentos por conexión |

---

## 14. Plan de construcción

- [ ] 1. Esqueleto de la app, configuración, plantillas base y carga de preguntas
- [ ] 2. Sesiones, nombres temporales y código de reconexión
- [ ] 3. Cola y emparejamiento
- [ ] 4. Lógica de partida: rondas, temporizadores, daño, KO y desempate
- [ ] 5. Interfaz completa en español: barras de HP, cuenta regresiva, resultados
- [ ] 6. Desconexión, reconexión y `session_expired`
- [ ] 7. Pruebas unitarias y lista de pruebas manuales
- [ ] 8. README con instrucciones para ejecutar en local

## 15. Criterios de "listo para demo"

- Dos jugadores en navegadores distintos juegan una partida completa sin errores.
- Las barras de HP, el daño y los puntos son claros y coinciden con las reglas de la sección 3.
- Refrescar la página no saca al jugador de la partida.
- Un reinicio del servidor muestra un mensaje claro en español y no deja la pantalla rota.
- El código es limpio, está comentado donde hace falta y no tiene sobreingeniería.

## 16. Supuestos que confirmar antes de empezar

1. Tabla de daño y tiempos de la sección 3.2 (10/15/20 s, daño base 10/15/20, bono hasta +10).
2. Durante una desconexión el reloj sigue corriendo y hay 30 s de gracia (no se pausa la partida).
3. Orden de dificultad por partida: fácil, fácil, media, media, difícil.
4. Incluir unas 20 preguntas de ejemplo en español en el banco.

---

## 17. Ampliación: lobby, victorias y modo espectador

- **Flujo nuevo:** Inicio (nombre) → **Lobby** → Cola → Partida → Final → Lobby. Antes se buscaba partida directamente desde el inicio.
- **Lobby:** lista en tiempo real de jugadores en línea con **victorias** y estado (`lobby`, `buscando`, `jugando`, `espectando`), y lista de **partidas en curso** con ronda y HP. Botones «Buscar partida» y «Salir del lobby». El lobby nunca difunde códigos de reconexión.
- **Cupo:** máximo 11 jugadores en el lobby (`MAX_LOBBY`). Al llegar al límite, `create_session` responde `lobby_lleno`. El contador del lobby muestra `n/11`.
- **Victorias:** +1 al ganador de cada partida (incluye victoria por abandono). Se guardan en la sesión, en memoria: se pierden al salir del lobby, vencer la sesión o reiniciar el servidor.
- **Modo espectador:** desde el lobby, «Ver partida» une al jugador a una sala de solo lectura. Recibe el estado actual, la pregunta con el tiempo restante real, el resultado de cada ronda (sin revelar la respuesta antes del cierre) y el final. Al terminar la partida, vuelve al lobby con el botón.
- **Reglas del espectador:** solo puede ver quien está libre en el lobby (no en cola ni en partida). Si se desconecta, vuelve al lobby al reconectar.
- **Eventos nuevos:** cliente→servidor `leave_session`, `spectate`, `leave_spectate`; servidor→cliente `lobby_state`, `session_closed`, `spec_state`, `spec_question`, `spec_round_result`, `spec_over`.

---

## 18. Corrección (feedback) tras cada pregunta

- Cada pregunta del JSON incluye `feedback`: una explicación corta de la respuesta correcta.
- Al cerrarse una ronda, el servidor envía `round_result` (jugadores) y `spec_round_result` (espectadores) con la pregunta, la respuesta correcta y el feedback. Los dos jugadores ven exactamente lo mismo durante `SEGUNDOS_FEEDBACK` (30 s), con cuenta atrás en la barra de tiempo.
- El servidor controla la pausa: la siguiente pregunta (o el resultado final) llega al terminar esos 30 s, también tras la quinta pregunta y tras un KO.
- Si un jugador se reconecta durante la pausa, recibe de nuevo la corrección con el tiempo restante real.
- Efecto en la duración: una partida de 5 preguntas pasa de ~1 minuto a ~3 minutos.
