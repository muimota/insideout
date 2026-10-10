import asyncio
import difflib
from collections import Counter
from typing import Any

from .devices import Device, Emitter
from .llm_client import LLMClient
from .models import Simulation

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "propose_output",
            "description": (
                "Registra tu voto para un output compartido. No ejecuta nada "
                "directamente: el orquestador aplicará al dispositivo el valor "
                "final consensuado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "output_id": {
                        "type": "string",
                        "description": "Identificador del output sobre el que votas",
                    },
                    "valor": {
                        "type": "string",
                        "description": "Valor propuesto (uno de los valores válidos del output)",
                    },
                    "justificacion": {
                        "type": "string",
                        "description": "Justificación breve, coherente con tu personalidad",
                    },
                },
                "required": ["output_id", "valor", "justificacion"],
                "additionalProperties": False,
            },
        },
    }
]


def sanitize_value(valor: Any, enum_values: list[Any]) -> Any:
    sval = str(valor).strip()
    for v in enum_values:
        if sval.lower() == str(v).lower():
            return v
    nums = [v for v in enum_values if isinstance(v, (int, float))]
    if nums:
        try:
            x = float(sval)
        except ValueError:
            x = None
        if x is not None:
            return min(nums, key=lambda v: abs(v - x))
    str_vals = [str(v) for v in enum_values]
    lower_vals = [s.lower() for s in str_vals]
    matches = difflib.get_close_matches(sval.lower(), lower_vals, n=1, cutoff=0.6)
    if matches:
        return enum_values[lower_vals.index(matches[0])]
    if matches:
        return enum_values[str_vals.index(matches[0])]
    return None


BOOL_TRUE = {"true", "t", "si", "sí", "yes", "y", "1", "on"}
BOOL_FALSE = {"false", "f", "no", "n", "0", "off"}


def sanitize_bool(valor: Any) -> bool | None:
    s = str(valor).strip().lower()
    if s in BOOL_TRUE:
        return True
    if s in BOOL_FALSE:
        return False
    return None


def sanitize_texto(valor: Any) -> str | None:
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def sanitize_output(valor: Any, out) -> Any | None:
    if out.tipo == "bool":
        return sanitize_bool(valor)
    if out.tipo == "texto":
        return sanitize_texto(valor)
    return sanitize_value(valor, out.enum_values or [])


def majority(values: list[Any]) -> Any | None:
    if not values:
        return None
    counts = Counter(values).most_common(2)
    if len(counts) == 1:
        return counts[0][0]
    if counts[0][1] > counts[1][1]:
        return counts[0][0]
    return None


class DeliberationEngine:
    def __init__(
        self,
        simulation: Simulation,
        llm: LLMClient,
        devices: dict[str, Device],
        emit: Emitter,
    ):
        self.sim = simulation
        self.llm = llm
        self.devices = devices
        self.emit = emit

    async def run(self) -> None:
        sim = self.sim
        votes: dict[str, dict[str, Any]] = {a.id: {} for a in sim.agents}
        blackboard: list[dict[str, Any]] = []

        for k in range(1, sim.max_rondas + 1):
            await self.emit({"type": "round_start", "round": k})
            snapshot = {i.id: i.value for i in sim.inputs}
            await self.emit(
                {
                    "type": "telemetry",
                    "round": k,
                    "inputs": [
                        {"id": i.id, "name": i.name, "value": i.value}
                        for i in sim.inputs
                    ],
                }
            )

            for agent in sim.agents:
                await self.emit(
                    {
                        "type": "turn_start",
                        "round": k,
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                    }
                )
                calls = await self._turno(agent, k, snapshot, blackboard)
                for call in calls:
                    await self._register_vote(agent, call, k, votes, blackboard)

                if self._all_unanimous(votes):
                    await self._finish(k, votes, consensus=True)
                    return

            await self.emit({"type": "round_end", "round": k})

        await self._finish(sim.max_rondas, votes, consensus=False)

    async def _turno(
        self, agent, round: int, snapshot: dict, blackboard: list
    ) -> list[dict]:
        system = self._system_prompt(agent)
        user = self._user_prompt(round, snapshot, blackboard)
        gen = self.llm.run_turn(
            agent, system, user, TOOLS_SCHEMA, self.sim.timeout_turno
        )
        calls: list[dict] = []
        timed_out = False
        try:
            async with asyncio.timeout(self.sim.timeout_turno):
                async for ev in gen:
                    if ev["type"] == "thought_token":
                        await self.emit(
                            {
                                "type": "thought_token",
                                "round": round,
                                "agent_id": agent.id,
                                "text": ev["text"],
                            }
                        )
                    elif ev["type"] == "turn_complete":
                        calls = ev["tool_calls"]
        except TimeoutError:
            timed_out = True
        finally:
            await gen.aclose()
        if timed_out:
            await self.emit(
                {
                    "type": "turn_timeout",
                    "round": round,
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                }
            )
            return []
        return calls

    async def _register_vote(
        self, agent, call: dict, round: int, votes: dict, blackboard: list
    ) -> None:
        outputs = {o.id: o for o in self.sim.outputs}
        output_id = str(call.get("output_id", "")).strip()
        out = outputs.get(output_id)
        if out is None:
            return
        raw = call.get("valor")
        valor = sanitize_output(raw, out)
        if valor is None:
            valor = out.safe_value
        justificacion = str(call.get("justificacion", ""))[:500]
        votes[agent.id][out.id] = valor
        blackboard.append(
            {
                "round": round,
                "agent_name": agent.name,
                "output_name": out.name,
                "valor": valor,
                "justificacion": justificacion,
            }
        )
        await self.emit(
            {
                "type": "proposal",
                "round": round,
                "agent_id": agent.id,
                "agent_name": agent.name,
                "output_id": out.id,
                "output_name": out.name,
                "valor": valor,
                "raw_valor": raw,
                "justificacion": justificacion,
            }
        )

    def _all_unanimous(self, votes: dict) -> bool:
        agent_ids = [a.id for a in self.sim.agents]
        for out in self.sim.outputs:
            vals = [votes[aid].get(out.id) for aid in agent_ids]
            if any(v is None for v in vals) or len(set(vals)) != 1:
                return False
        return True

    async def _finish(self, round: int, votes: dict, consensus: bool) -> None:
        if consensus:
            for out in self.sim.outputs:
                valor = next(iter(votes[a.id][out.id] for a in self.sim.agents))
                await self.emit(
                    {
                        "type": "consensus",
                        "round": round,
                        "output_id": out.id,
                        "output_name": out.name,
                        "valor": valor,
                    }
                )
                await self.devices[out.id].apply(valor)
            await self.emit(
                {"type": "simulation_end", "round": round, "reason": "consensus"}
            )
            return

        for out in self.sim.outputs:
            vals = [
                votes[a.id].get(out.id)
                for a in self.sim.agents
                if votes[a.id].get(out.id) is not None
            ]
            valor = majority(vals)
            if valor is None:
                valor = out.safe_value
            vote_counts = dict(Counter(vals))
            await self.emit(
                {
                    "type": "forced_resolution",
                    "round": round,
                    "output_id": out.id,
                    "output_name": out.name,
                    "valor": valor,
                    "votes": vote_counts,
                }
            )
            await self.devices[out.id].apply(valor)
        await self.emit(
            {"type": "simulation_end", "round": round, "reason": "forced_resolution"}
        )

    def _system_prompt(self, agent) -> str:
        sim = self.sim

        def valid_values(o) -> str:
            if o.tipo == "bool":
                return "— valores válidos: true / false"
            if o.tipo == "texto":
                return (
                    "— valor libre de texto (breve); el CONSENSO exige que todos "
                    "los agentes propongan exactamente el mismo texto"
                )
            return f"— valores válidos: {o.enum_values}"

        outputs_txt = "\n".join(
            f'- "{o.id}" ({o.name}, dispositivo {o.device_type or "abstracto"}): '
            f"{o.description} {valid_values(o)}"
            for o in sim.outputs
        )
        return (
            f'Eres "{agent.name}", un agente que participa en un sistema de '
            "deliberación multiagente.\n\n"
            "## Tu personalidad (definida por el autor del experimento)\n"
            f"{agent.personality}\n\n"
            "## Reglas del sistema (inyectadas por la plataforma)\n"
            "- Junto a otros agentes decides el valor de los outputs compartidos "
            "en rondas sucesivas de debate.\n"
            "- En cada turno debes: (1) argumentar brevemente tu postura en texto "
            "y (2) llamar a la herramienta `propose_output` una vez POR CADA "
            "output.\n"
            "- `propose_output` solo registra tu voto en la pizarra compartida; "
            "el orquestador aplica al dispositivo el valor final.\n"
            "- Si todos los agentes proponen el mismo valor para un output, hay "
            "CONSENSO y la deliberación termina inmediatamente.\n"
            f"- Si tras {sim.max_rondas} rondas no hay consenso, se aplica "
            "resolución por mayoría; el empate produce un estado de seguridad "
            "preconfigurado.\n"
            "- Tu voto se normaliza: en enums se acepta la opción válida más "
            "cercana, en bools se interpreta true/false, y en texto libre se "
            "recortan espacios.\n\n"
            "## Outputs sobre los que deliberas\n"
            f"{outputs_txt}\n"
        )

    def _user_prompt(self, round: int, snapshot: dict, blackboard: list) -> str:
        sim = self.sim
        telemetry = "\n".join(
            f'- "{inp.name}" ({inp.description or "sin descripción"}): {inp.value}'
            for inp in sim.inputs
        )
        visible = blackboard[-sim.n_mensajes :]
        if visible:
            board = "\n".join(
                f"- [R{m['round']}] {m['agent_name']} propuso {m['valor']} para "
                f"{m['output_name']}: {m['justificacion']}"
                for m in visible
            )
        else:
            board = "(la pizarra está vacía: eres el primero en hablar)"
        return (
            f"## Ronda {round} de {sim.max_rondas}\n\n"
            "## Telemetría (instantánea congelada para esta ronda)\n"
            f"{telemetry}\n\n"
            f"## Pizarra compartida (últimos {sim.n_mensajes} mensajes)\n"
            f"{board}\n\n"
            "Es tu turno: argumenta tu postura y vota con `propose_output` "
            "para cada output."
        )
