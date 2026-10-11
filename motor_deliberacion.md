# Motor de Deliberación

Capa de orquestación (backend) que gestiona el loop de interacción entre agentes para decidir el estado de un actuador físico compartido. Los agentes debaten y votan; solo el orquestador puede enviar comandos al hardware.

## El loop (ronda k)

```
[Inicio de Ronda k]
        │
        ▼
1. Captura de telemetría: snapshot de sensores → caché de la pizarra
   (misma instantánea para ambos agentes durante la ronda)
        │
        ▼
2. Turno Agente A:
   - Recibe: telemetría actual + últimos n mensajes de la pizarra
   - Emite: argumentación en texto + propose_output(v_A, justificacion)
        │
        ▼
   ¿v_A == v_B? ──(SÍ)──► [CONSENSO] ──► Enviar comando a hardware ──► FIN (early exit)
        │ (NO)
        ▼
3. Turno Agente B:
   - Recibe: telemetría actual + últimos n mensajes (incluida propuesta de A)
   - Emite: argumentación en texto + propose_output(v_B, justificacion)
        │
        ▼
   ¿v_A == v_B? ──(SÍ)──► [CONSENSO] ──► Enviar comando a hardware ──► FIN
        │ (NO)
        ▼
4. Evaluación de salida:
   ¿k == max_rondas?
   ├── (NO) ──► Pasar a Ronda k+1
   └── (SÍ) ──► [RESOLUCIÓN FORZADA] ──► Enviar comando a hardware ──► FIN
```

### Reglas de resolución forzada (sin consenso tras max_rondas)

- **Opción A — Punto medio aritmético:** para valores escalares (ej. 0, 45, 90), se elige la opción discreta más cercana al promedio de ambas posturas.
- **Opción B — Estado de fallo / conflicto:** el actuador adopta un estado de seguridad o alerta (LED ámbar/rojo, servo en reposo), evidenciando que las personalidades diseñadas fueron incapaces de acordar.

## Herramienta única: `propose_output`

- `valor`: opción obligatoria dentro de un enum discreto preconfigurado.
  - Servo: `[0, 45, 90]`
  - LED: `["OFF", "VERDE", "AMBAR", "ROJO"]`
  - Nivel: `[1, 2, 3, 4, 5]`
- `justificacion`: texto breve coherente con la personalidad del agente.

Los agentes **no** tienen acceso directo al hardware (`set_output` se descarta porque rompería la deliberación): la herramienta solo registra el voto en la pizarra.

## Modo agente único

Con exactamente un agente no hay deliberación posible y no se aplica la
maquinaria de consenso:

- En cuanto vota todos los outputs, la simulación termina de inmediato con
  eventos `decision` (uno por output, con `via: "voto"`) y
  `simulation_end {reason: "decision"}`.
- Si omite votos (omisión o timeout), las rondas actúan como reintento
  (se conserva el voto anterior); al agotarse, lo no votado cae en su estado
  de seguridad (`via: "safe_value"`).
- El prompt del sistema no menciona otros agentes, CONSENSO ni mayoría: el
  agente sabe que decide en solitario.

## Votos inválidos (inputs o ids desconocidos)

`propose_output` con un `output_id` que no es un output **no** se descarta en
silencio: se emite `invalid_proposal` con el motivo y se anota el rechazo en la
pizarra para que los turnos siguientes (ventana de `n_mensajes`) lo vean y
corrijan. Motivos:

- es un **input** (la telemetría es de solo lectura),
- es el **nombre** de un output (se pide votar usando su id exacto),
- es un **id desconocido**.

## Cambios acordados respecto a la propuesta inicial

| Aspecto | Propuesta inicial | Decisión acordada |
| :-- | :-- | :-- |
| Memoria | Historial inyectado en el prompt (in-context) | Pizarra compartida (*blackboard*) con ventana deslizante configurable `n_mensajes_visibles` (default n=4) |
| Sensores | Sondeo continuo (pull) | Caché de telemetría actualizada solo al inicio de cada ronda (modelo de ticks); evento push despierta la deliberación |
| Turnos | Asíncrono / con riesgo de condiciones de carrera | Round-robin estricto y síncrono con límite `max_rondas = 3` |
| Actuadores | Valores continuos (ángulo 0–180, RGB) | Enums discretos; el chequeo de consenso es una comparación trivial de literales |
| Evaluación de salida | `set_output()` invocado por los agentes | Herramienta única `propose_output` (solo vota); únicamente el orquestador envía el comando final al microcontrolador |
| Desenlace | "Vale el último valor tras n intervenciones" | Corregido: early exit por coincidencia, silencio = mantiene voto anterior, resolución forzada acotada si no hay acuerdo (evita la "tiranía del último turno") |
| Latencia / UX | Animación de "respiración" del LED mientras delibera | Descartado: el hardware ejecuta solo la acción final; el proceso se supervisa en la interfaz web |
| Prompt del alumno | Definir personalidad y herramientas | Define EXCLUSIVAMENTE la personalidad; reglas operativas y tool schema los inyecta la plataforma |

## Capa de tolerancia a fallos

1. **Omisión de llamada:** si el agente genera texto sin invocar `propose_output`, se conserva su valor de la ronda anterior.
2. **Sanitización:** un valor fuera del enum se mapea a la opción válida más cercana.
3. **Timeout:** límite de 5 s por turno; al superarlo, se mantiene el voto previo y el flujo avanza.
4. **Firmware simple:** el microcontrolador recibe un comando JSON final (ej. `{"led": "VERDE", "servo": 45}`) y lo aplica al instante, sin tareas asíncronas ni animaciones.
