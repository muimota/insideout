# Laboratorio de Deliberación entre Agentes

Entorno web para experimentar con agentes LLM que deliberan sobre actuadores
virtuales. Consulta `PLAN.md` (arquitectura y decisiones) y
`motor_deliberacion.md` (referencia del motor).

## Requisitos

- Python 3.12+
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
python3 -m venv .venv
.venv/bin/pip install fastapi 'uvicorn[standard]' openai python-dotenv
.venv/bin/python -m uvicorn backend.app:app --port 8000
```

### 3. Frontend

En otra terminal:

```bash
npm install --prefix frontend
npm run dev --prefix frontend
```

Abre http://localhost:5173

### 4. Uso

1. Crea uno o más **agentes** (solo el prompt de personalidad).
2. Crea **inputs** (bool/enum/texto) y fija su valor antes de jugar.
3. Crea **outputs** (led/servo/nivel) con su descripción.
4. Pulsa **Play** y observa el razonamiento en streaming, los votos y los
   dispositivos virtuales.

## Desarrollo sin API key

Puedes probar todo el flujo con un servidor LLM simulado:

```bash
.venv/bin/python -m uvicorn --app-dir dev mock_llm_server:app --port 8001
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
.venv/bin/pip install pytest pytest-asyncio
.venv/bin/python -m pytest -q
```

Cubren el motor completo con LLM simulado: consenso, mayoría, empate →
safe_value, silencio, sanitización, timeout y ventana de pizarra.

## Estructura

```
backend/   FastAPI: motor de deliberación, cliente LLM, dispositivos virtuales
frontend/  Svelte: builder del experimento, deliberación en streaming, widgets
dev/       mock del endpoint LLM para desarrollo sin API key
tests/     tests del motor (pytest)
```
