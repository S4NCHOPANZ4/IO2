# Trivia Battle

Duelo de trivia 1 contra 1 en tiempo real. Flask + Flask-SocketIO, Jinja2 y JavaScript puro. Sin base de datos: sesiones, cola y partidas viven en memoria.

## Ejecutar en local

```bash
python -m venv .venv && source .venv/bin/activate      # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abre <http://localhost:5000> en dos o tres ventanas (una normal y las demás de incógnito), pulsa «Entrar al lobby» en cada una y luego «Buscar partida» en dos de ellas. La tercera puede pulsar «Ver partida» para mirar el duelo.
Para jugar desde otro dispositivo en la misma red Wi-Fi, abre `http://IP-DE-TU-PC:5000`.

## Pruebas

```bash
python -m pytest                      # reglas: daño, ganador, desempate, cola
python tests/simulacion.py            # dos bots juegan una partida completa (con el servidor encendido)
python tests/simulacion_lobby.py      # lobby, victorias y espectador con tres bots
```

## Reglas rápidas

5 preguntas (fácil, fácil, media, media, difícil), 100 HP cada uno. Un acierto daña al rival: daño base 10/15/20 + bono de velocidad de hasta +10. Tiempo por pregunta: 10/15/20 s. Todo se ajusta en `config.py`; las preguntas están en `data/preguntas.json`.

## Lobby, victorias y espectador

- Todos entran primero al **lobby**: ven quién está en línea, sus **victorias** y su estado (en el lobby, buscando, jugando, viendo una partida).
- Desde el lobby se pulsa «Buscar partida» para entrar a la cola. Al terminar, se puede volver al lobby o jugar de nuevo.
- Las **partidas en curso** aparecen con su ronda y HP. «Ver partida» abre el modo espectador, que muestra HP, preguntas, tiempo y resultado de cada ronda en vivo.
- El lobby admite hasta **11 jugadores** (`MAX_LOBBY` en `config.py`). El jugador 12 ve «El lobby está lleno».
- Las victorias viven en la sesión: se pierden si el jugador sale del lobby, la sesión vence o el servidor se reinicia (no hay base de datos).

## Reconexión

Cada sesión recibe un código de 6 caracteres (visible arriba a la derecha). Al refrescar, la página se reconecta sola. Si el servidor se reinicia, el código deja de existir y se muestra «El servidor se reinició. Vuelve a entrar.». Si un jugador no vuelve en 30 s, pierde por abandono.

## Despliegue (Railway)

1. Sube el proyecto a un repositorio de GitHub (sin `.venv`).
2. En railway.com: **New Project → Deploy from GitHub repo**.
3. En el servicio: **Settings → Deploy → Custom Start Command**: `gunicorn -w 1 --threads 100 -b 0.0.0.0:$PORT app:app`
4. **Settings → Networking → Generate Domain** y abre la URL con `https://`.
5. Deja 1 réplica y **no actives Serverless** (el servidor mantiene conexiones WebSocket y estado en memoria).
6. Prueba con 3 o más dispositivos en la URL pública antes de la demo.

Notas: un solo worker (el estado vive en memoria); cada nuevo despliegue o reinicio borra lobby, sesiones y partidas, así que no despliegues durante la demo. Alternativa gratuita: Render (servicio web gratuito, mismo comando de inicio), que se duerme tras 15 minutos sin tráfico.
