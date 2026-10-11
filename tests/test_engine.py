import asyncio
import re

from backend.devices import VirtualDevice
from backend.engine import (
    DeliberationEngine,
    majority,
    sanitize_bool,
    sanitize_texto,
    sanitize_value,
)
from backend.models import (
    Agent,
    InputDef,
    OutputDef,
    Simulation,
)


class MockLLM:
    def __init__(self, actions):
        self.actions = actions
        self.user_prompts = []
        self.system_prompts = []

    async def run_turn(self, agent, system_prompt, user_prompt, tools, timeout):
        self.system_prompts.append((agent.name, system_prompt))
        self.user_prompts.append((agent.name, user_prompt))
        round_ = int(re.search(r"Ronda (\d+) de", user_prompt).group(1))
        yield {"type": "thought_token", "text": f"[{agent.name}] pensando..."}
        action = self.actions.get((agent.name, round_), [])
        if action == "timeout":
            await asyncio.sleep(1.0)
            return
        yield {"type": "turn_complete", "tool_calls": action}


def make_sim(n_agents=2, timeout=30.0, n_mensajes=4, outputs=None):
    agents = [Agent(name=f"A{i}", personality="test") for i in range(n_agents)]
    inputs = [
        InputDef(
            name="es_de_noche",
            tipo="bool",
            description="True si es de noche",
            value=True,
        )
    ]
    outs = outputs or [
        OutputDef(
            name="LED",
            enum_values=["OFF", "VERDE", "AMBAR", "ROJO"],
            description="LED del laboratorio",
            safe_value="AMBAR",
        )
    ]
    return Simulation(
        agents=agents,
        inputs=inputs,
        outputs=outs,
        max_rondas=3,
        n_mensajes=n_mensajes,
        timeout_turno=timeout,
    )


async def run_engine(sim, llm):
    events = []

    async def emit(ev):
        events.append(ev)

    devices = {o.id: VirtualDevice(o, emit) for o in sim.outputs}
    engine = DeliberationEngine(sim, llm, devices, emit)
    await engine.run()
    return events


def propose(output_id, valor, just="porque"):
    return {"output_id": output_id, "valor": valor, "justificacion": just}


def types_of(events):
    return [e["type"] for e in events]


def find(events, etype):
    return [e for e in events if e["type"] == etype]


async def test_consenso_en_ronda_1():
    sim = make_sim()
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): [propose(led, "VERDE")],
            ("A1", 1): [propose(led, "VERDE")],
        }
    )
    events = await run_engine(sim, llm)
    cons = find(events, "consensus")
    cmds = find(events, "command")
    assert len(cons) == 1 and cons[0]["valor"] == "VERDE"
    assert len(cmds) == 1 and cmds[0]["valor"] == "VERDE"
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 1
    assert "forced_resolution" not in types_of(events)


async def test_desacuerdo_luego_consenso():
    sim = make_sim()
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): [propose(led, "VERDE")],
            ("A1", 1): [propose(led, "ROJO")],
            ("A0", 2): [propose(led, "AMBAR")],
            ("A1", 2): [propose(led, "AMBAR")],
        }
    )
    events = await run_engine(sim, llm)
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 2
    assert find(events, "consensus")[0]["valor"] == "AMBAR"


async def test_resolucion_por_mayoria():
    sim = make_sim(n_agents=3)
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", r): [propose(led, "VERDE")] for r in (1, 2, 3)
        }
    )
    for a in ("A1", "A2"):
        for r in (1, 2, 3):
            llm.actions[(a, r)] = [propose(led, "ROJO")]
    events = await run_engine(sim, llm)
    fr = find(events, "forced_resolution")
    assert len(fr) == 1
    assert fr[0]["valor"] == "ROJO" and fr[0]["votes"] == {"ROJO": 2, "VERDE": 1}
    assert find(events, "command")[0]["valor"] == "ROJO"
    assert "consensus" not in types_of(events)


async def test_empate_vuelve_a_safe_value():
    sim = make_sim(n_agents=2)
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", r): [propose(led, "VERDE")] for r in (1, 2, 3)
        }
    )
    for r in (1, 2, 3):
        llm.actions[("A1", r)] = [propose(led, "ROJO")]
    events = await run_engine(sim, llm)
    fr = find(events, "forced_resolution")[0]
    assert fr["valor"] == "AMBAR"
    assert find(events, "command")[0]["valor"] == "AMBAR"


async def test_silencio_mantiene_voto_anterior():
    sim = make_sim()
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): [propose(led, "VERDE")],
            ("A1", 2): [propose(led, "VERDE")],
        }
    )
    events = await run_engine(sim, llm)
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 2


async def test_sanitize_mayusculas_y_escalares():
    sim = make_sim()
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): [propose(led, "verde")],
            ("A1", 1): [propose(led, "VERDE")],
        }
    )
    events = await run_engine(sim, llm)
    assert find(events, "consensus")[0]["valor"] == "VERDE"


async def test_sanitize_fuera_de_enum_cae_en_safe():
    sim = make_sim()
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): [propose(led, "azul")],
            ("A1", 1): [propose(led, "AZUL")],
        }
    )
    events = await run_engine(sim, llm)
    assert find(events, "proposal")[0]["valor"] == "AMBAR"
    assert find(events, "consensus")[0]["valor"] == "AMBAR"


async def test_servo_escalares_numericos():
    servo = OutputDef(
        name="Servo",
        enum_values=[0, 45, 90],
        description="ángulo",
        safe_value=90,
    )
    sim = make_sim(outputs=[servo])
    sid = servo.id
    llm = MockLLM(
        {
            ("A0", 1): [propose(sid, "47")],
            ("A1", 1): [propose(sid, 45)],
        }
    )
    events = await run_engine(sim, llm)
    assert find(events, "proposal")[0]["valor"] == 45
    assert find(events, "consensus")[0]["valor"] == 45


async def test_timeout_mantiene_voto_previo():
    sim = make_sim(timeout=0.05)
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): "timeout",
            ("A1", 1): [propose(led, "VERDE")],
            ("A0", 2): [propose(led, "VERDE")],
        }
    )
    events = await run_engine(sim, llm)
    assert find(events, "turn_timeout")[0]["agent_name"] == "A0"
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 2


async def test_ventana_deslizante_pizarra():
    sim = make_sim(n_mensajes=1)
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): [propose(led, "VERDE")],
            ("A1", 1): [propose(led, "ROJO")],
            ("A0", 2): [propose(led, "AMBAR")],
        }
    )
    events = await run_engine(sim, llm)
    a0_r2 = next(
        p for name, p in llm.user_prompts if name == "A0" and "Ronda 2" in p
    )
    assert "A1" in a0_r2 and "A0" not in a0_r2
    assert "Ronda 2 de 3" in a0_r2
    assert "True" in a0_r2


async def test_multiples_outputs_early_exit_parcial():
    led = OutputDef(
        name="LED",
        enum_values=["OFF", "VERDE", "AMBAR", "ROJO"],
        description="LED",
        safe_value="AMBAR",
    )
    servo = OutputDef(
        name="Servo",
        enum_values=[0, 45, 90],
        description="ángulo",
        safe_value=90,
    )
    sim = make_sim(outputs=[led, servo])
    llm = MockLLM(
        {
            ("A0", 1): [
                propose(led.id, "VERDE"),
                propose(servo.id, 0),
            ],
            ("A1", 1): [
                propose(led.id, "VERDE"),
                propose(servo.id, 90),
            ],
            ("A0", 2): [
                propose(led.id, "VERDE"),
                propose(servo.id, 45),
            ],
            ("A1", 2): [
                propose(led.id, "VERDE"),
                propose(servo.id, 45),
            ],
        }
    )
    events = await run_engine(sim, llm)
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 2
    cmds = {c["output_id"]: c["valor"] for c in find(events, "command")}
    assert cmds == {led.id: "VERDE", servo.id: 45}


def test_sanitize_value_unitario():
    led_enum = ["OFF", "VERDE", "AMBAR", "ROJO"]
    assert sanitize_value("verde", led_enum) == "VERDE"
    assert sanitize_value("VERDE", led_enum) == "VERDE"
    assert sanitize_value("verdee", led_enum) == "VERDE"
    assert sanitize_value("50", [0, 45, 90]) == 45
    assert sanitize_value(2.4, [1, 2, 3, 4, 5]) == 2
    assert sanitize_value("zzz", led_enum) is None


def test_sanitize_bool_unitario():
    assert sanitize_bool("TRUE") is True
    assert sanitize_bool(True) is True
    assert sanitize_bool(" off") is False
    assert sanitize_bool(0) is False
    assert sanitize_bool("quizás") is None


def test_sanitize_texto_unitario():
    assert sanitize_texto("  hola ") == "hola"
    assert sanitize_texto("   ") is None
    assert sanitize_texto(None) is None


async def test_output_bool_consenso():
    alarma = OutputDef(name="alarma", tipo="bool", safe_value=False)
    led = OutputDef(
        name="LED",
        enum_values=["OFF", "VERDE", "AMBAR", "ROJO"],
        safe_value="AMBAR",
    )
    sim = make_sim(outputs=[alarma, led])
    llm = MockLLM(
        {
            ("A0", 1): [propose(alarma.id, "true"), propose(led.id, "VERDE")],
            ("A1", 1): [propose(alarma.id, "TRUE"), propose(led.id, "VERDE")],
        }
    )
    events = await run_engine(sim, llm)
    cons = find(events, "consensus")
    assert [c["valor"] for c in cons] == [True, "VERDE"]
    cmds = {c["output_id"]: c["valor"] for c in find(events, "command")}
    assert cmds[alarma.id] is True
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 1


async def test_output_bool_valor_invalido_vuelve_a_safe():
    alarma = OutputDef(name="alarma", tipo="bool", safe_value=False)
    sim = make_sim(outputs=[alarma])
    llm = MockLLM(
        {
            ("A0", 1): [propose(alarma.id, "suministro eléctrico máximo")],
            ("A1", 1): [propose(alarma.id, "false")],
        }
    )
    events = await run_engine(sim, llm)
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus"
    assert find(events, "consensus")[0]["valor"] is False


async def test_output_texto_consenso():
    letrero = OutputDef(name="letrero", tipo="texto", safe_value="")
    sim = make_sim(outputs=[letrero])
    llm = MockLLM(
        {
            ("A0", 1): [propose(letrero.id, "ABRIR")],
            ("A1", 1): [propose(letrero.id, "  ABRIR ")],
        }
    )
    events = await run_engine(sim, llm)
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus"
    assert find(events, "consensus")[0]["valor"] == "ABRIR"


async def test_output_texto_empate_safe_value():
    letrero = OutputDef(name="letrero", tipo="texto", safe_value="SIN_DECISION")
    sim = make_sim(outputs=[letrero])
    llm = MockLLM(
        {
            ("A0", r): [propose(letrero.id, "ABRIR")] for r in (1, 2, 3)
        }
    )
    llm.actions[("A1", 1)] = [propose(letrero.id, "CERRAR")]
    llm.actions[("A1", 2)] = [propose(letrero.id, "CERRAR")]
    llm.actions[("A1", 3)] = [propose(letrero.id, "CERRAR")]
    events = await run_engine(sim, llm)
    forced = find(events, "forced_resolution")[0]
    assert forced["valor"] == "SIN_DECISION"
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "forced_resolution"


def test_majority_unitario():
    assert majority(["a", "a", "b"]) == "a"
    assert majority(["a", "b"]) is None
    assert majority([]) is None
    assert majority(["x"]) == "x"


async def test_mono_agente_decide_en_ronda_1():
    sim = make_sim(n_agents=1)
    led = sim.outputs[0].id
    llm = MockLLM({("A0", 1): [propose(led, "VERDE")]})
    events = await run_engine(sim, llm)
    dec = find(events, "decision")
    assert len(dec) == 1
    assert dec[0]["valor"] == "VERDE" and dec[0]["via"] == "voto"
    assert find(events, "command")[0]["valor"] == "VERDE"
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "decision" and end["round"] == 1
    assert "consensus" not in types_of(events)
    assert "forced_resolution" not in types_of(events)


async def test_mono_agente_reintenta_si_omite_output():
    led = OutputDef(
        name="LED",
        enum_values=["OFF", "VERDE", "AMBAR", "ROJO"],
        description="LED",
        safe_value="AMBAR",
    )
    servo = OutputDef(
        name="Servo", enum_values=[0, 45, 90], description="ángulo", safe_value=90
    )
    sim = make_sim(n_agents=1, outputs=[led, servo])
    llm = MockLLM(
        {
            ("A0", 1): [propose(led.id, "VERDE")],
            ("A0", 2): [propose(servo.id, 45)],
        }
    )
    events = await run_engine(sim, llm)
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "decision" and end["round"] == 2
    dec = {d["output_id"]: d["valor"] for d in find(events, "decision")}
    assert dec == {led.id: "VERDE", servo.id: 45}


async def test_mono_agente_nunca_vota_cae_en_safe_value():
    sim = make_sim(n_agents=1)
    llm = MockLLM({})
    events = await run_engine(sim, llm)
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "decision" and end["round"] == 3
    dec = find(events, "decision")[0]
    assert dec["valor"] == "AMBAR" and dec["via"] == "safe_value"
    assert find(events, "command")[0]["valor"] == "AMBAR"
    assert "consensus" not in types_of(events)
    assert "forced_resolution" not in types_of(events)


async def test_mono_agente_prompt_sin_maquinaria_de_consensus():
    sim = make_sim(n_agents=1)
    led = sim.outputs[0].id
    llm = MockLLM({("A0", 1): [propose(led, "VERDE")]})
    await run_engine(sim, llm)
    system = llm.system_prompts[0][1]
    assert "en solitario" in system
    assert "CONSENSO" not in system
    assert "otros agentes" not in system
    assert "solo lectura" in system


async def test_voto_sobre_input_es_rechazado_y_avisado():
    sim = make_sim()
    led = sim.outputs[0].id
    sensor = sim.inputs[0].name
    llm = MockLLM(
        {
            ("A0", 1): [propose(sensor, "false")],
            ("A1", 1): [propose(led, "VERDE")],
            ("A0", 2): [propose(led, "VERDE")],
        }
    )
    events = await run_engine(sim, llm)
    inv = find(events, "invalid_proposal")
    assert len(inv) == 1
    assert inv[0]["agent_name"] == "A0" and inv[0]["output_id"] == sensor
    assert "solo lectura" in inv[0]["motivo"]
    assert "input" in inv[0]["motivo"]
    props_a0 = [p for p in find(events, "proposal") if p["agent_id"] == "A0"]
    assert all(p["round"] == 2 for p in props_a0)
    a1_r1 = next(
        p for name, p in llm.user_prompts if name == "A1" and "Ronda 1" in p
    )
    assert "rechazado" in a1_r1
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 2


async def test_voto_por_nombre_de_output_se_rechaza_con_ayuda():
    sim = make_sim()
    led = sim.outputs[0]
    llm = MockLLM(
        {
            ("A0", 1): [propose(led.name, "VERDE")],
            ("A1", 1): [propose(led.id, "VERDE")],
            ("A0", 2): [propose(led.id, "VERDE")],
        }
    )
    events = await run_engine(sim, llm)
    inv = find(events, "invalid_proposal")
    assert len(inv) == 1 and inv[0]["output_id"] == "LED"
    assert led.id in inv[0]["motivo"]
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 2


async def test_voto_sobre_id_desconocido_no_bloquea_consenso():
    sim = make_sim()
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): [propose("no_existe", "VERDE"), propose(led, "VERDE")],
            ("A1", 1): [propose(led, "VERDE")],
        }
    )
    events = await run_engine(sim, llm)
    inv = find(events, "invalid_proposal")
    assert len(inv) == 1 and inv[0]["output_id"] == "no_existe"
    assert "no es un output" in inv[0]["motivo"]
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 1


async def test_abstencion_permite_consenso_inmediato():
    sim = make_sim()
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): [propose(led, "VERDE")],
            ("A1", 1): [propose(led, "ABSTAIN", just="no es mi competencia")],
        }
    )
    events = await run_engine(sim, llm)
    cons = find(events, "consensus")
    assert len(cons) == 1 and cons[0]["valor"] == "VERDE"
    assert find(events, "command")[0]["valor"] == "VERDE"
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 1


async def test_todos_se_abstienen_adopta_safe_value():
    sim = make_sim()
    led = sim.outputs[0].id
    llm = MockLLM(
        {
            ("A0", 1): [propose(led, "ABSTAIN")],
            ("A1", 1): [propose(led, "ABSTAIN")],
        }
    )
    events = await run_engine(sim, llm)
    cons = find(events, "consensus")
    assert len(cons) == 1 and cons[0]["valor"] == "AMBAR"
    assert find(events, "command")[0]["valor"] == "AMBAR"
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 1


async def test_multiples_outputs_con_especializacion():
    led = OutputDef(
        name="LED",
        enum_values=["OFF", "VERDE", "AMBAR", "ROJO"],
        description="LED",
        safe_value="AMBAR",
    )
    servo = OutputDef(
        name="Servo", enum_values=[0, 45, 90], description="ángulo", safe_value=90
    )
    sim = make_sim(outputs=[led, servo])
    llm = MockLLM(
        {
            # A0 es experto en iluminación, se abstiene del servo
            ("A0", 1): [
                propose(led.id, "VERDE"),
                propose(servo.id, "ABSTAIN", just="no controlo mecánica"),
            ],
            # A1 es experto en mecánica, se abstiene de la iluminación
            ("A1", 1): [
                propose(led.id, "ABSTAIN", just="no controlo luces"),
                propose(servo.id, 45),
            ],
        }
    )
    events = await run_engine(sim, llm)
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "consensus" and end["round"] == 1
    cmds = {c["output_id"]: c["valor"] for c in find(events, "command")}
    assert cmds == {led.id: "VERDE", servo.id: 45}


async def test_mono_agente_abstencion_adopta_safe_value():
    sim = make_sim(n_agents=1)
    led = sim.outputs[0].id
    llm = MockLLM({("A0", 1): [propose(led, "ABSTAIN")]})
    events = await run_engine(sim, llm)
    dec = find(events, "decision")
    assert len(dec) == 1
    assert dec[0]["valor"] == "AMBAR" and dec[0]["via"] == "abstencion"
    assert find(events, "command")[0]["valor"] == "AMBAR"
    end = find(events, "simulation_end")[0]
    assert end["reason"] == "decision" and end["round"] == 1

