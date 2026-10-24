/* Cliente de Trivia Battle. Solo muestra información y envía acciones:
   el servidor decide tiempos, daño, ganador y victorias. */
(() => {
  "use strict";

  // Todos los textos de la interfaz en un solo lugar.
  const TEXTOS = {
    expirada: "El servidor se reinició. Vuelve a entrar.",
    codigoInvalido: "Código no válido o sesión vencida.",
    demasiados: "Demasiados intentos. Recarga la página.",
    sinSesion: "No hay sesión activa. Vuelve a entrar.",
    siguienteEn: s => `Siguiente pregunta en ${s} s`,
    resultadoEn: s => `Resultado final en ${s} s`,
    lobbyLleno: "El lobby está lleno (11 jugadores). Inténtalo de nuevo en un momento.",
    partidaTerminada: "Esa partida ya terminó o no se puede ver.",
    estado: { lobby: "En el lobby", buscando: "Buscando partida", jugando: "Jugando", espectando: "Viendo una partida" },
    ronda: (n, t) => `Pregunta ${n} de ${t}`,
    dificultad: { facil: "Fácil", media: "Media", dificil: "Difícil" },
    rivalDesconectado: s => `Tu oponente se desconectó. Si no vuelve en ${s} s, ganas por abandono.`,
    acertaste: n => `¡Acertaste! Hiciste ${n} de daño.`,
    fallaste: "Respuesta incorrecta: 0 de daño.",
    sinResponder: "No respondiste a tiempo: 0 de daño.",
    recibiste: n => `Tu oponente te hizo ${n} de daño.`,
    sinDanoRival: "Tu oponente no te hizo daño.",
    titulo: { victoria: "¡Victoria!", derrota: "Derrota", empate: "Empate" },
    motivo: {
      ko: "Dejaste a tu rival sin vida (KO).", hp: "Terminaron las 5 preguntas: gana quien tiene más HP.",
      desempate: "Mismo HP: gana quien respondió más rápido sus aciertos.",
      abandono: "Tu oponente abandonó la partida.", doble_ko: "Los dos quedaron sin vida a la vez.",
      empate: "Mismo HP y mismo tiempo de respuesta.",
    },
    motivoDerrota: { ko: "Tu rival te dejó sin vida (KO).", abandono: "Perdiste por desconexión." },
    ir: "¡A pelear!",
    // Textos neutrales para el modo espectador
    espRonda: (a, da, b, db) => `${a} hizo ${da} de daño. ${b} hizo ${db} de daño.`,
    espGano: { ko: "por KO", hp: "por tener más HP tras 5 preguntas", desempate: "en el desempate por velocidad", abandono: "por abandono" },
    espEmpate: { doble_ko: "Empate: los dos quedaron sin vida a la vez.", empate: "Empate: mismo HP y mismo tiempo de respuesta." },
    espFin: (n, m) => `Fin de la partida. Ganó ${n} ${m}.`,
  };

  const $ = id => document.getElementById(id);
  const PANTALLAS = ["inicio", "lobby", "cola", "cuenta", "partida", "final", "espectador"];
  const socket = io();
  const st = { entrando: false, manual: false, yo: null, seleccion: null, raf: 0, fin: 0, dur: 1, cuenta: 0, pref: "", etiqueta: null, esp: { a: "", b: "" } };

  const guardado = () => { try { return sessionStorage.getItem("tb_codigo"); } catch { return null; } };
  const guardar = c => { try { c ? sessionStorage.setItem("tb_codigo", c) : sessionStorage.removeItem("tb_codigo"); } catch {} };

  function mostrar(nombre) {
    PANTALLAS.forEach(p => { $("pantalla-" + p).hidden = p !== nombre; });
  }

  function badge(codigo) {
    $("codigo-badge").hidden = !codigo;
    $("codigo-texto").textContent = codigo || "";
  }

  // «lado» es "yo", "rival" (jugadores) o "ea", "eb" (espectador)
  function setHp(lado, hp) {
    $("hp-" + lado).textContent = hp;
    const b = $("barra-" + lado);
    b.style.width = hp + "%";
    b.className = "barra-hp " + (hp > 50 ? "ok" : hp > 25 ? "medio" : "bajo");
  }

  function flotante(lado, n) {
    const el = $("dano-" + lado);
    el.textContent = "-" + n;
    el.classList.remove("sube");
    void el.offsetWidth;            // reinicia la animación
    el.classList.add("sube");
  }

  function prepararLuchadores(l1, n1, hp1, l2, n2, hp2) {
    $("nombre-" + l1).textContent = n1;        // textContent: nunca innerHTML con nombres
    $("nombre-" + l2).textContent = n2;
    setHp(l1, hp1);
    setHp(l2, hp2);
  }

  // ---------- cuenta regresiva previa ----------
  function iniciarCuenta(n) {
    clearInterval(st.cuenta);
    $("cuenta-num").textContent = n;
    st.cuenta = setInterval(() => {
      n -= 1;
      $("cuenta-num").textContent = n > 0 ? n : TEXTOS.ir;
      if (n <= 0) clearInterval(st.cuenta);
    }, 1000);
  }

  // ---------- pregunta y temporizador (jugador: pref "", espectador: pref "e-") ----------
  function tick() {
    const restante = Math.max(0, (st.fin - performance.now()) / 1000);
    $(st.pref + "barra-tiempo").style.width = (restante / st.dur * 100) + "%";
    $(st.pref + "segundos").textContent = Math.ceil(restante);
    if (st.etiqueta) $(st.pref + "siguiente").textContent = st.etiqueta(Math.ceil(restante));
    if (restante > 0) st.raf = requestAnimationFrame(tick);
  }

  function bloquear(pref) {
    $(pref + "opciones").querySelectorAll("button").forEach(b => { b.disabled = true; });
  }

  function renderPregunta(d, pref, interactivo) {
    cancelAnimationFrame(st.raf);
    $(pref + "meta-ronda").textContent = TEXTOS.ronda(d.ronda, d.total);
    $(pref + "meta-dif").textContent = TEXTOS.dificultad[d.dificultad];
    $(pref + "meta-cat").textContent = d.categoria;
    $(pref + "pregunta").textContent = d.pregunta;
    $(pref + "mensaje-ronda").textContent = "";
    $(pref + "feedback").hidden = true;
    $(pref + "siguiente").textContent = "";
    $(pref + "barra-tiempo").parentElement.classList.remove("pausa");
    st.etiqueta = null;
    const cont = $(pref + "opciones");
    cont.replaceChildren();
    d.opciones.forEach((texto, i) => {
      const b = document.createElement("button");
      b.dataset.i = i;
      b.textContent = texto;
      b.disabled = !interactivo || d.respondida;
      cont.appendChild(b);
    });
    st.pref = pref;
    st.dur = d.duracion;
    st.fin = performance.now() + d.restante * 1000;
    tick();
  }

  function marcarCorrecta(pref, correcta, elegida) {
    const botones = $(pref + "opciones").querySelectorAll("button");
    botones.forEach(b => { b.disabled = true; });
    if (botones[correcta]) botones[correcta].classList.add("correcta");
    if (elegida !== null && elegida !== correcta && botones[elegida]) botones[elegida].classList.add("incorrecta");
  }

  // Pausa de corrección: pregunta cerrada, respuesta correcta y explicación con cuenta atrás
  function revisar(d, pref, elegida) {
    cancelAnimationFrame(st.raf);
    $(pref + "meta-ronda").textContent = TEXTOS.ronda(d.ronda, d.total);
    $(pref + "meta-dif").textContent = TEXTOS.dificultad[d.dificultad];
    $(pref + "meta-cat").textContent = d.categoria;
    $(pref + "pregunta").textContent = d.pregunta;
    const cont = $(pref + "opciones");
    cont.replaceChildren();
    d.opciones.forEach(texto => {
      const b = document.createElement("button");
      b.textContent = texto;
      cont.appendChild(b);
    });
    marcarCorrecta(pref, d.correcta, elegida);
    $(pref + "feedback-texto").textContent = d.feedback;
    $(pref + "feedback").hidden = false;
    $(pref + "barra-tiempo").parentElement.classList.add("pausa");
    st.pref = pref;
    st.dur = d.pausa;
    st.fin = performance.now() + d.restante_pausa * 1000;
    st.etiqueta = d.ultima ? TEXTOS.resultadoEn : TEXTOS.siguienteEn;
    tick();
  }

  // ---------- conexión y sesión ----------
  socket.on("connect", () => {
    $("conexion").hidden = true;
    const c = guardado();
    if (c) socket.emit("reconnect_with_code", { codigo: c });
  });
  socket.on("disconnect", () => { $("conexion").hidden = false; });

  socket.on("session_created", d => {
    guardar(d.codigo);
    badge(d.codigo);
    st.yo = d.id;
    $("mis-victorias").textContent = d.victorias;
    if (st.entrando) { st.entrando = false; mostrar("lobby"); }
  });

  socket.on("session_closed", () => {
    guardar(null);
    badge(null);
    st.yo = null;
    mostrar("inicio");
  });

  socket.on("restore", d => {
    if (d.fase === "partida") {
      prepararLuchadores("yo", d.yo, d.hp_yo, "rival", d.rival, d.hp_rival);
      $("aviso-rival").hidden = true;
      mostrar("partida");
    } else {
      mostrar("lobby");
    }
  });

  // ---------- lobby ----------
  socket.on("lobby_state", d => {
    const cuerpo = $("lista-jugadores");
    cuerpo.replaceChildren();
    d.jugadores.forEach(j => {
      const tr = document.createElement("tr");
      if (j.id === st.yo) { tr.className = "yo"; $("mis-victorias").textContent = j.victorias; }
      [j.nombre + (j.id === st.yo ? " (tú)" : ""), j.victorias, TEXTOS.estado[j.estado]].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      cuerpo.appendChild(tr);
    });
    $("num-jugadores").textContent = `${d.jugadores.length}/${d.max}`;

    const lista = $("lista-partidas");
    lista.replaceChildren();
    d.partidas.forEach(p => {
      const li = document.createElement("li");
      const info = document.createElement("div");
      const titulo = document.createElement("strong");
      titulo.textContent = `${p.a} contra ${p.b}`;
      const detalle = document.createElement("small");
      detalle.textContent = `${TEXTOS.ronda(p.ronda, p.total)}: ${p.hp_a} HP contra ${p.hp_b} HP`;
      info.append(titulo, detalle);
      const btn = document.createElement("button");
      btn.dataset.id = p.id;
      btn.textContent = "Ver partida";
      li.append(info, btn);
      lista.appendChild(li);
    });
    $("sin-partidas").hidden = d.partidas.length > 0;
  });

  socket.on("queue_status", d => {
    $("aviso-lobby").textContent = "";
    mostrar(d.en_cola ? "cola" : "lobby");
  });

  // ---------- partida (jugador) ----------
  socket.on("match_found", d => {
    prepararLuchadores("yo", d.yo, d.hp, "rival", d.rival, d.hp);
    $("aviso-rival").hidden = true;
    $("cuenta-yo").textContent = d.yo;
    $("cuenta-rival").textContent = d.rival;
    mostrar("cuenta");
    iniciarCuenta(d.cuenta);
  });

  socket.on("question", d => {
    clearInterval(st.cuenta);
    st.seleccion = null;
    renderPregunta(d, "", true);
    mostrar("partida");
  });

  socket.on("round_result", d => {
    revisar(d, "", d.elegida);
    mostrar("partida");
    setHp("yo", d.yo.hp);
    setHp("rival", d.rival.hp);
    const nuevo = d.restante_pausa > d.pausa - 2;      // no repetir la animación al reconectar
    if (nuevo && d.rival.dano > 0) flotante("yo", d.rival.dano);
    if (nuevo && d.yo.dano > 0) flotante("rival", d.yo.dano);
    const propio = d.yo.correcto ? TEXTOS.acertaste(d.yo.dano) : (d.yo.respondio ? TEXTOS.fallaste : TEXTOS.sinResponder);
    const ajeno = d.rival.dano > 0 ? TEXTOS.recibiste(d.rival.dano) : TEXTOS.sinDanoRival;
    $("mensaje-ronda").textContent = propio + " " + ajeno;
  });

  socket.on("opponent_status", d => {
    $("aviso-rival").hidden = d.conectado;
    if (!d.conectado) $("aviso-rival").textContent = TEXTOS.rivalDesconectado(d.gracia);
  });

  socket.on("game_over", d => {
    cancelAnimationFrame(st.raf);
    clearInterval(st.cuenta);
    $("final-titulo").textContent = TEXTOS.titulo[d.resultado];
    const derrota = d.resultado === "derrota" && TEXTOS.motivoDerrota[d.motivo];
    $("final-motivo").textContent = derrota || TEXTOS.motivo[d.motivo];
    for (const [id, j, clase] of [["fila-yo", d.yo, "yo"], ["fila-rival", d.rival, ""]]) {
      const fila = $(id);
      fila.replaceChildren();
      [j.nombre, j.hp, j.dano_total, j.aciertos + "/5"].forEach((v, i) => {
        const td = document.createElement("td");
        td.textContent = v;
        if (i === 0 && clase) td.className = clase;
        fila.appendChild(td);
      });
    }
    mostrar("final");
  });

  // ---------- modo espectador ----------
  socket.on("spec_state", d => {
    st.esp = { a: d.a, b: d.b };
    prepararLuchadores("ea", d.a, d.hp_a, "eb", d.b, d.hp_b);
    $("e-pregunta").textContent = "Esperando la siguiente pregunta…";
    $("e-opciones").replaceChildren();
    $("e-mensaje-ronda").textContent = "";
    $("e-feedback").hidden = true;
    $("e-siguiente").textContent = "";
    mostrar("espectador");
  });

  socket.on("spec_question", d => renderPregunta(d, "e-", false));

  socket.on("spec_round_result", d => {
    revisar(d, "e-", null);
    setHp("ea", d.a.hp);
    setHp("eb", d.b.hp);
    if (d.b.dano > 0) flotante("ea", d.b.dano);
    if (d.a.dano > 0) flotante("eb", d.a.dano);
    $("e-mensaje-ronda").textContent = TEXTOS.espRonda(st.esp.a, d.a.dano, st.esp.b, d.b.dano);
  });

  socket.on("spec_over", d => {
    cancelAnimationFrame(st.raf);
    $("e-mensaje-ronda").textContent = d.ganador
      ? TEXTOS.espFin(d.ganador, TEXTOS.espGano[d.motivo] || "")
      : TEXTOS.espEmpate[d.motivo];
  });

  // ---------- errores ----------
  socket.on("error", d => {
    if (d.codigo === "session_expired") {
      guardar(null);
      badge(null);
      st.yo = null;
      mostrar("inicio");
      $("aviso-inicio").textContent = st.manual ? TEXTOS.codigoInvalido : TEXTOS.expirada;
      st.manual = false;
    } else if (d.codigo === "demasiados_intentos") {
      $("aviso-inicio").textContent = TEXTOS.demasiados;
    } else if (d.codigo === "sin_sesion") {
      guardar(null);
      mostrar("inicio");
      $("aviso-inicio").textContent = TEXTOS.sinSesion;
    } else if (d.codigo === "lobby_lleno") {
      st.entrando = false;
      mostrar("inicio");
      $("aviso-inicio").textContent = TEXTOS.lobbyLleno;
    } else if (d.codigo === "no_se_puede_ver") {
      $("aviso-lobby").textContent = TEXTOS.partidaTerminada;
    }
  });

  // ---------- acciones del jugador ----------
  $("btn-buscar").addEventListener("click", () => {           // «Entrar al lobby»
    $("aviso-inicio").textContent = "";
    st.entrando = true;
    const c = guardado();
    if (c) socket.emit("reconnect_with_code", { codigo: c });
    else socket.emit("create_session", { nombre: $("nombre").value });
  });

  $("btn-recuperar").addEventListener("click", () => {
    const codigo = $("codigo-input").value.trim();
    if (!codigo) return;
    st.manual = true;
    st.entrando = true;
    $("aviso-inicio").textContent = "";
    socket.emit("reconnect_with_code", { codigo });
  });

  $("btn-lobby-buscar").addEventListener("click", () => { $("aviso-lobby").textContent = ""; socket.emit("join_queue"); });
  $("btn-salir").addEventListener("click", () => socket.emit("leave_session"));
  $("btn-cancelar").addEventListener("click", () => socket.emit("leave_queue"));
  $("btn-otra").addEventListener("click", () => socket.emit("join_queue"));
  $("btn-volver-lobby").addEventListener("click", () => mostrar("lobby"));
  $("btn-espectador-volver").addEventListener("click", () => { cancelAnimationFrame(st.raf); socket.emit("leave_spectate"); mostrar("lobby"); });

  $("lista-partidas").addEventListener("click", e => {
    const b = e.target.closest("button[data-id]");
    if (b) socket.emit("spectate", { id: b.dataset.id });
  });

  $("opciones").addEventListener("click", e => {
    const b = e.target.closest("button[data-i]");
    if (!b || b.disabled) return;
    st.seleccion = Number(b.dataset.i);
    bloquear("");
    b.classList.add("elegida");
    socket.emit("answer", { opcion: st.seleccion });
  });
})();
