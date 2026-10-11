# Laboratorio de Deliberación entre Agentes

Entorno web para experimentar con agentes LLM que deliberan sobre actuadores
virtuales. Consulta `PLAN.md` (arquitectura y decisiones) y
`motor_deliberacion.md` (referencia del motor).

## Requisitos

- Python 3.12+ con [uv](https://docs.astral.sh/uv/)
- Node.js 20+

## Puesta en marcha

### 1. Configuración

Copia `.env.example` a `.env` y rellena tu API key. El backend habla el
protocolo OpenAI: apunta `OPENAI_BASE_URL` a tu endpoint compatible y
`OPENAI_MODEL` al modelo que quieras usar.

```
OPENAI_API_KEY=tu-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
TIMEOUT_TURNO=30
MAX_RONDAS=3
N_MENSAJES=4
```

### 2. Backend

```bash
uv sync
uv run uvicorn backend.app:app --port 8000
```

### 3. Frontend

En otra terminal:

```bash
npm install --prefix frontend
npm run dev --prefix frontend
```

Abre http://localhost:5173

### 4. Uso

1. Crea uno o más **agentes** (solo el prompt de personalidad). Arrástralos
   en la lista para reordenar los turnos y haz doble click sobre su
   personalidad para editarla.
2. Crea **inputs** (bool/enum/texto) y fija su valor antes de jugar.
3. Crea **outputs** del mismo modo (bool/enum/texto); los enum muestran un
   badge con el valor del actuador virtual.
4. Pulsa **Play** y observa en la pizarra cómo convergen los votos (con
   razonamiento en streaming), y los dispositivos virtuales.

## Desarrollo sin API key

Puedes probar todo el flujo con un servidor LLM simulado:

```bash
uv run uvicorn --app-dir dev mock_llm_server:app --port 8001
```

Y en `.env`:

```
OPENAI_API_KEY=dummy
OPENAI_BASE_URL=http://localhost:8001/v1
OPENAI_MODEL=mock-model
```

El mock genera dos posturas enfrentadas ("Prudente" propone ROJO, "Ahorrador"
propone OFF), así que la deliberación termina en resolución forzada (empate →
estado de seguridad AMBAR).

## Tests

```bash
uv run pytest -q
```

Cubren el motor completo con LLM simulado: consenso, mayoría, empate →
safe_value, silencio, sanitización, timeout, ventana de pizarra, decisión
individual (agente único) y rechazo de votos sobre inputs.

## Estructura

```
backend/   FastAPI: motor de deliberación, cliente LLM, dispositivos virtuales
frontend/  Svelte: builder del experimento, deliberación en streaming, widgets
dev/       mock del endpoint LLM para desarrollo sin API key
tests/     tests del motor (pytest)
```
