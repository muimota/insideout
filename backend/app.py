import asyncio
import json
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import load_settings
from .devices import VirtualDevice
from .engine import DeliberationEngine
from .llm_client import LLMClient
from .models import (
    Agent,
    InputDef,
    OutputDef,
    Simulation,
)

app = FastAPI(title="Laboratorio de Deliberación")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

state: dict[str, list] = {"agents": [], "inputs": [], "outputs": []}
running = False


class AgentCreate(BaseModel):
    name: str
    personality: str
    model: Optional[str] = None


class InputCreate(BaseModel):
    name: str
    tipo: Literal["bool", "enum", "texto"]
    enum_values: Optional[list[str]] = None
    description: str = ""
    value: Any = None


class OutputCreate(BaseModel):
    name: str
    tipo: Literal["bool", "enum", "texto"] = "enum"
    enum_values: Optional[list[Any]] = None
    description: str = ""
    safe_value: Any = None


class InputValue(BaseModel):
    value: Any


def _default_input_value(inp: InputDef) -> Any:
    if inp.tipo == "bool":
        return False
    if inp.tipo == "enum":
        return inp.enum_values[0] if inp.enum_values else None
    return ""


def _validate_input_value(inp: InputDef, value: Any) -> Any:
    if inp.tipo == "bool":
        if not isinstance(value, bool):
            raise HTTPException(400, "El valor de un input bool debe ser true/false")
        return value
    if inp.tipo == "enum":
        if str(value) not in [str(v) for v in (inp.enum_values or [])]:
            raise HTTPException(
                400, f"Valor fuera del enum: {inp.enum_values}"
            )
        return value
    return str(value)


@app.get("/experiment")
def get_experiment():
    return state


@app.delete("/experiment")
def reset_experiment():
    global running
    if running:
        raise HTTPException(409, "Hay una simulación en curso")
    state["agents"].clear()
    state["inputs"].clear()
    state["outputs"].clear()
    return {"ok": True}


@app.post("/agents", status_code=201)
def create_agent(body: AgentCreate):
    agent = Agent(name=body.name, personality=body.personality, model=body.model)
    state["agents"].append(agent)
    return agent


class AgentOrder(BaseModel):
    ids: list[str]


@app.put("/agents/order")
def reorder_agents(body: AgentOrder):
    pos = {aid: i for i, aid in enumerate(body.ids)}
    state["agents"].sort(key=lambda a: pos.get(a.id, len(body.ids)))
    return {"ok": True}


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    personality: Optional[str] = None


@app.put("/agents/{agent_id}")
def update_agent(agent_id: str, body: AgentUpdate):
    agent = next((a for a in state["agents"] if a.id == agent_id), None)
    if agent is None:
        raise HTTPException(404, "Agente no encontrado")
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(400, "El nombre no puede estar vacío")
        agent.name = body.name.strip()
    if body.personality is not None:
        if not body.personality.strip():
            raise HTTPException(400, "La personalidad no puede estar vacía")
        agent.personality = body.personality.strip()
    return agent


@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: str):
    state["agents"] = [a for a in state["agents"] if a.id != agent_id]
    return {"ok": True}


@app.post("/inputs", status_code=201)
def create_input(body: InputCreate):
    if body.tipo == "enum" and not body.enum_values:
        raise HTTPException(400, "Un input enum necesita enum_values no vacío")
    inp = InputDef(
        name=body.name,
        tipo=body.tipo,
        enum_values=body.enum_values,
        description=body.description,
        value=body.value if body.value is not None else _default_input_value(
            InputDef(name=body.name, tipo=body.tipo, enum_values=body.enum_values)
        ),
    )
    _validate_input_value(inp, inp.value)
    state["inputs"].append(inp)
    return inp


@app.delete("/inputs/{input_id}")
def delete_input(input_id: str):
    state["inputs"] = [i for i in state["inputs"] if i.id != input_id]
    return {"ok": True}


@app.post("/experiment/inputs/{input_id}/value")
def set_input_value(input_id: str, body: InputValue):
    inp = next((i for i in state["inputs"] if i.id == input_id), None)
    if inp is None:
        raise HTTPException(404, "Input no encontrado")
    inp.value = _validate_input_value(inp, body.value)
    return inp


def _default_output_payload(body: OutputCreate):
    """Devuelve (tipo, enum_values, safe_value) ya validados."""
    tipo = body.tipo
    if tipo == "enum":
        enum_values = list(body.enum_values) if body.enum_values else None
        if not enum_values:
            raise HTTPException(
                400, "Un output enum necesita enum_values no vacío"
            )
    else:
        enum_values = None

    if tipo == "bool":
        safe = False if body.safe_value is None else bool(body.safe_value)
    elif tipo == "texto":
        safe = "" if body.safe_value is None else str(body.safe_value)
    else:
        safe = body.safe_value
        if safe is None:
            safe = enum_values[0]
        if str(safe) not in [str(v) for v in enum_values]:
            raise HTTPException(400, f"safe_value fuera del enum: {enum_values}")
    return tipo, enum_values, safe


@app.post("/outputs", status_code=201)
def create_output(body: OutputCreate):
    tipo, enum_values, safe = _default_output_payload(body)
    out = OutputDef(
        name=body.name,
        tipo=tipo,
        enum_values=enum_values,
        description=body.description,
        safe_value=safe,
    )
    state["outputs"].append(out)
    return out


@app.delete("/outputs/{output_id}")
def delete_output(output_id: str):
    state["outputs"] = [o for o in state["outputs"] if o.id != output_id]
    return {"ok": True}


@app.post("/experiment/start")
async def start_simulation():
    global running
    if running:
        raise HTTPException(409, "Ya hay una simulación en curso")
    if not state["agents"] or not state["outputs"]:
        raise HTTPException(400, "Se necesita al menos 1 agente y 1 output")

    settings = load_settings()
    if not settings.api_key:
        raise HTTPException(
            500,
            "Falta configurar OPENAI_API_KEY (copia .env.example a .env)",
        )
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    simulation = Simulation(
        agents=list(state["agents"]),
        inputs=list(state["inputs"]),
        outputs=list(state["outputs"]),
        max_rondas=settings.max_rondas,
        n_mensajes=settings.n_mensajes,
        timeout_turno=settings.timeout_turno,
    )
    devices = {o.id: VirtualDevice(o, emit) for o in simulation.outputs}

    async def run_wrapper():
        global running
        try:
            llm = LLMClient(settings)
            engine = DeliberationEngine(simulation, llm, devices, emit)
            await engine.run()
        except Exception as exc:
            await queue.put(
                {"type": "simulation_error", "error": f"{type(exc).__name__}: {exc}"}
            )
        finally:
            await queue.put(None)
            running = False

    async def stream():
        task = asyncio.create_task(run_wrapper())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
