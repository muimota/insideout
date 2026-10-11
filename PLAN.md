# PLAN — Laboratorio de Deliberación entre Agentes

Entorno web para experimentar con agentes LLM que deliberan sobre actuadores
virtuales. Referencia del motor: `motor_deliberacion.md`. Referencia general:
`proyecto.md`.

## 1. Qué es

El usuario define **agentes** (personalidad), **inputs** (sensores virtuales)
y **outputs** (actuadores virtuales). Al pulsar **play**, el motor de
deliberación ejecuta rondas round-robin hasta consenso o resolución forzada.
El usuario observa el razonamiento en streaming. Solo el orquestador envía el
comando final a los dispositivos.

## 2. Decisiones cerradas

| Tema | Decisión |
| :-- | :-- |
| LLM | Protocolo **OpenAI** en todo el código (nunca "openrouter"). `base_url`, `model`, `api_key` en `.env` (gitignored) + `.env.example` |
| Visibilidad | **Fase 1: todos los agentes ven todos los inputs y outputs** (sin grafo). Fase 2: grafo como restricción de visibilidad |
| Inputs virtuales | El **usuario fija su valor en la UI** antes de play (toggle/selector/texto). El snapshot se congela al iniciar la simulación |
| Outputs | Enums discretos definidos **explícitamente por el autor del experimento** (ej. LED `["OFF","VERDE","AMBAR","ROJO"]`, servo `[0,45,90]`). Cada output enum tiene `enum_values`, `descripción` y `safe_value` (estado ante conflicto; por defecto el primer valor del enum) |
| Dispositivos | Abstracción `Device`: fase 1 = **virtuales en el navegador**; fase 3 = ESP32 físico por WebSocket sin cambiar el resto |
| Consenso | **Unánime por output** → early exit cuando todos los outputs están acordados. Sin unanimidad tras `max_rondas`: **mayoría simple por output; empate o sin mayoría → `safe_value`** (estado de conflicto) |
| Votos inválidos | `propose_output` sobre un input o id desconocido → evento `invalid_proposal` + nota de rechazo en la pizarra; la telemetría (inputs) es de solo lectura |
| Motor | Implementación propia en Python asíncrono (~300 líneas). Sin frameworks de agentes |
| Turnos | Round-robin estricto, `max_rondas = 3`, timeout por turno **configurable** (default 30 s por fiabilidad con LLMs) |
| Memoria | Pizarra compartida (*blackboard*) con ventana deslizante `n_mensajes_visibles = 4` |
| Prompt del alumno | Define **exclusivamente** la personalidad; reglas operativas y tool schema las inyecta la plataforma |
| Tolerancia a fallos | Sin tool call → mantiene voto anterior; valor fuera de enum → sanitizar al válido más cercano; timeout de turno → mantiene voto previo y avanza |

## 3. Arquitectura

```
code/
├── backend/                  # FastAPI + asyncio
│   ├── app.py                # endpoints, ciclo de vida, CORS
│   ├── config.py             # lee .env (OPENAI_API_KEY, OPENAI_BASE_URL, MODEL, TIMEOUT_TURNO...)
│   ├── models.py             # Agent, InputDef, OutputDef, Simulation (pydantic)
│   ├── llm_client.py         # cliente OpenAI-compatible: streaming, tool propose_output,
│   │                         #   sanitización de valores fuera del enum
│   ├── engine.py             # motor: rondas, pizarra, consenso, resolución forzada
│   ├── devices.py            # Device + VirtualDevice (comando → evento al frontend)
│   └── events.py             # formato de eventos del stream SSE
├── frontend/                 # Svelte + Vite
│   ├── src/App.svelte        # builder: crear agentes/inputs/outputs, fijar valores, play
│   ├── src/Deliberation.svelte   # razonamiento por agente (streaming), votos, timeline
│   └── src/VirtualDevices.svelte # badge genérico de valor, toggle (bool), texto
│                                 # estilos: Tailwind v4 utilidades (@theme en app.css)
├── tests/                    # pytest: motor con LLM mockeado
├── .env.example
└── PLAN.md
```

## 4. Modelo de datos

- **Agent**: `{id, nombre, personalidad}` — opcionalmente `model` propio.
- **InputDef**: `{id, nombre, tipo: bool|enum|texto, enum_valores?, descripción, valor}`
  (valor fijado por el usuario antes de play).
- **OutputDef**: `{id, nombre, tipo: bool|enum|texto, enum_valores (solo enum), descripción, safe_value}`.
- **Simulation**: `{agentes[], inputs[], outputs[], max_rondas, n_mensajes_visibles, timeout_turno}`.

## 5. Motor (generalizado a N agentes × M outputs)

Por ronda k:

1. **Congelar snapshot** de inputs (misma instantánea para todos los agentes).
2. **Turnos round-robin**: cada agente recibe telemetría + últimos n mensajes
   de la pizarra → argumentación en streaming + `propose_output(valor,
   justificacion)` **por cada output**.
3. Tras cada turno, chequear unanimidad **por output**; cuando todos los
   outputs están unánimes → **early exit**.
4. k == max_rondas sin unanimidad → **resolución forzada por output**:
   mayoría simple; empate o sin mayoría → `safe_value`.
5. El **orquestador** envía el comando JSON final (ej. `{"led": "VERDE"}`) a
   los `Device` virtuales. Los agentes nunca tocan el hardware.

## 6. API (REST + SSE)

- `POST /agents`, `POST /inputs`, `POST /outputs` — crear elementos (en memoria, fase 1).
- `GET /experiment` — estado completo (agentes, inputs, outputs).
- `POST /experiment/inputs/{id}/value` — fijar valor de un input.
- `POST /experiment/start` → stream **SSE** con eventos:
  `round_start`, `telemetry`, `turn_start`, `thought_token` (streaming del
  razonamiento), `proposal`, `invalid_proposal`, `round_end`, `consensus`,
  `forced_resolution`, `command`, `simulation_end`.

## 7. Fases

1. **Este hito:** builder simple (listas, sin grafo) + motor completo +
   streaming SSE + dispositivos virtuales en navegador.
2. Grafo de nodos con svelte-flow; conexiones input→agente→output como
   visibilidad restringida.
3. ESP32 real vía WebSocket manteniendo la abstracción `Device`.

## 8. Verificación

- pytest del motor con LLM mockeado: consenso en ronda 1, mayoría tras
  max_rondas, empate → safe_value, omisión de tool, sanitización, timeout.
- E2E manual con `.env` real (2 agentes debatiendo el LED con input
  "es de noche").
