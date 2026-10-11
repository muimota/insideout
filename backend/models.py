from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Agent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    name: str
    personality: str
    model: Optional[str] = None


class InputDef(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    name: str
    tipo: Literal["bool", "enum", "texto"]
    enum_values: Optional[list[str]] = None
    description: str = ""
    value: Any = None


class OutputDef(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    name: str
    tipo: Literal["bool", "enum", "texto"] = "enum"
    enum_values: Optional[list[Any]] = None
    description: str = ""
    safe_value: Any = None


class Simulation(BaseModel):
    agents: list[Agent]
    inputs: list[InputDef]
    outputs: list[OutputDef]
    max_rondas: int = 3
    n_mensajes: int = 4
    timeout_turno: float = 30.0
