<script>
  import { onMount } from "svelte";
  import VirtualDevices from "./lib/VirtualDevices.svelte";
  import Deliberation from "./lib/Deliberation.svelte";

  const API = "http://localhost:8000";

  let agents = $state([]);
  let inputs = $state([]);
  let outputs = $state([]);
  let phase = $state("build");
  let status = $state("");
  let error = $state("");
  let rounds = $state([]);
  let deviceValues = $state({});
  let verdict = $state(null);
  let busy = $state(false);

  let newAgent = $state({ name: "", personality: "" });
  let newInput = $state({ name: "", tipo: "bool", enum_values: "", description: "" });
  let newOutput = $state({ name: "", device_type: "led", description: "" });

  onMount(load);

  async function load() {
    const res = await fetch(`${API}/experiment`);
    const data = await res.json();
    agents = data.agents;
    inputs = data.inputs;
    outputs = data.outputs;
    phase = "build";
  }

  async function call(path, method = "POST", body) {
    busy = true;
    try {
      const res = await fetch(`${API}${path}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!res.ok) throw new Error((await res.text()) || res.statusText);
      await load();
    } catch (e) {
      error = String(e.message || e);
    } finally {
      busy = false;
    }
  }

  async function addAgent() {
    if (!newAgent.name.trim() || !newAgent.personality.trim()) return;
    await call("/agents", "POST", {
      name: newAgent.name.trim(),
      personality: newAgent.personality.trim(),
    });
    newAgent = { name: "", personality: "" };
  }

  async function addInput() {
    if (!newInput.name.trim()) return;
    const body = {
      name: newInput.name.trim(),
      tipo: newInput.tipo,
      description: newInput.description.trim(),
    };
    if (newInput.tipo === "enum") {
      body.enum_values = newInput.enum_values
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      if (!body.enum_values.length) return;
    }
    await call("/inputs", "POST", body);
    newInput = { name: "", tipo: "bool", enum_values: "", description: "" };
  }

  async function addOutput() {
    if (!newOutput.name.trim()) return;
    await call("/outputs", "POST", {
      name: newOutput.name.trim(),
      device_type: newOutput.device_type,
      description: newOutput.description.trim(),
    });
    newOutput = { name: "", device_type: "led", description: "" };
  }

  async function setInputValue(id, value) {
    await call(`/experiment/inputs/${id}/value`, "POST", { value });
  }

  async function resetAll() {
    rounds = [];
    deviceValues = {};
    verdict = null;
    status = "";
    error = "";
    await call("/experiment", "DELETE");
  }

  async function play() {
    error = "";
    verdict = null;
    rounds = [];
    deviceValues = {};
    phase = "running";
    status = "Iniciando simulación…";
    try {
      const res = await fetch(`${API}/experiment/start`, { method: "POST" });
      if (!res.ok) throw new Error((await res.text()) || res.statusText);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n\n")) >= 0) {
          const raw = buf.slice(0, i);
          buf = buf.slice(i + 2);
          const line = raw.split("\n").find((l) => l.startsWith("data: "));
          if (line) handleEvent(JSON.parse(line.slice(6)));
        }
      }
    } catch (e) {
      error = String(e.message || e);
    }
    if (phase === "running") phase = "done";
    status = "";
  }

  function handleEvent(ev) {
    switch (ev.type) {
      case "round_start":
        rounds.push({ round: ev.round, turns: [] });
        status = `Ronda ${ev.round} iniciada`;
        break;
      case "telemetry":
        status = `Ronda ${ev.round}: telemetría congelada`;
        break;
      case "turn_start":
        rounds[rounds.length - 1].turns.push({
          agent_id: ev.agent_id,
          agent_name: ev.agent_name,
          thought: "",
          proposals: [],
          timeout: false,
        });
        status = `Ronda ${ev.round}: turno de ${ev.agent_name}`;
        break;
      case "thought_token": {
        const r = rounds[rounds.length - 1];
        if (r && r.turns.length) {
          r.turns[r.turns.length - 1].thought += ev.text;
        }
        break;
      }
      case "proposal": {
        const r = rounds[rounds.length - 1];
        if (r && r.turns.length) {
          r.turns[r.turns.length - 1].proposals.push(ev);
        }
        break;
      }
      case "turn_timeout": {
        const r = rounds[rounds.length - 1];
        if (r && r.turns.length) {
          r.turns[r.turns.length - 1].timeout = true;
        }
        break;
      }
      case "command":
        deviceValues[ev.output_id] = ev.valor;
        break;
      case "consensus":
        deviceValues[ev.output_id] = ev.valor;
        status = `CONSENSO en ${ev.output_name} = ${ev.valor} (ronda ${ev.round})`;
        break;
      case "forced_resolution":
        deviceValues[ev.output_id] = ev.valor;
        status = `RESOLUCIÓN FORZADA: ${ev.output_name} = ${ev.valor}`;
        break;
      case "simulation_end":
        verdict = ev;
        phase = "done";
        break;
      case "simulation_error":
        error = ev.error;
        phase = "done";
        break;
    }
  }
</script>

<main>
  <header>
    <h1>Laboratorio de Deliberación</h1>
    <div class="controls">
      {#if status}<span class="status">{status}</span>{/if}
      <button
        class="primary"
        disabled={phase === "running" || busy || !agents.length || !outputs.length}
        onclick={play}>
        ▶ Play
      </button>
      <button onclick={resetAll} disabled={phase === "running" || busy}>Reiniciar</button>
    </div>
  </header>

  {#if error}
    <p class="error">{error}</p>
  {/if}

  <section class="grid">
    <div class="card">
      <h2>Agentes</h2>
      {#each agents as a (a.id)}
        <div class="item">
          <strong>{a.name}</strong>
          <button class="icon" disabled={busy} onclick={() => call(`/agents/${a.id}`, "DELETE")}>×</button>
          <p class="muted">{a.personality}</p>
        </div>
      {/each}
      <div class="form">
        <input placeholder="nombre" bind:value={newAgent.name} />
        <textarea placeholder="prompt de personalidad" rows="3" bind:value={newAgent.personality}></textarea>
        <button onclick={addAgent} disabled={busy}>+ Agente</button>
      </div>
    </div>

    <div class="card">
      <h2>Inputs (sensores virtuales)</h2>
      {#each inputs as inp (inp.id)}
        <div class="item">
          <strong>{inp.name}</strong>
          <span class="muted">{inp.tipo}</span>
          <button class="icon" disabled={busy} onclick={() => call(`/inputs/${inp.id}`, "DELETE")}>×</button>
          <p class="muted">{inp.description}</p>
          {#if inp.tipo === "bool"}
            <select value={inp.value} onchange={(e) => setInputValue(inp.id, e.target.value === "true")}>
              <option value="false">false</option>
              <option value="true">true</option>
            </select>
          {:else if inp.tipo === "enum"}
            <select value={inp.value} onchange={(e) => setInputValue(inp.id, e.target.value)}>
              {#each inp.enum_values as v (v)}
                <option value={v}>{v}</option>
              {/each}
            </select>
          {:else}
            <input
              value={inp.value ?? ""}
              onchange={(e) => setInputValue(inp.id, e.target.value)} />
          {/if}
        </div>
      {/each}
      <div class="form">
        <input placeholder="nombre" bind:value={newInput.name} />
        <select bind:value={newInput.tipo}>
          <option value="bool">bool</option>
          <option value="enum">enum</option>
          <option value="texto">texto</option>
        </select>
        {#if newInput.tipo === "enum"}
          <input placeholder="valores, separados por comas" bind:value={newInput.enum_values} />
        {/if}
        <input placeholder="descripción (la ve el agente)" bind:value={newInput.description} />
        <button onclick={addInput} disabled={busy}>+ Input</button>
      </div>
    </div>

    <div class="card">
      <h2>Outputs (actuadores virtuales)</h2>
      {#each outputs as o (o.id)}
        <div class="item">
          <strong>{o.name}</strong>
          <span class="muted">{o.device_type}: {o.enum_values.join(" | ")}</span>
          <button class="icon" disabled={busy} onclick={() => call(`/outputs/${o.id}`, "DELETE")}>×</button>
          <p class="muted">{o.description}</p>
        </div>
      {/each}
      <div class="form">
        <input placeholder="nombre" bind:value={newOutput.name} />
        <select bind:value={newOutput.device_type}>
          <option value="led">led</option>
          <option value="servo">servo</option>
          <option value="nivel">nivel</option>
        </select>
        <input placeholder="descripción (la ve el agente)" bind:value={newOutput.description} />
        <button onclick={addOutput} disabled={busy}>+ Output</button>
      </div>
    </div>
  </section>

  <section>
    <h2>Dispositivos virtuales</h2>
    {#if outputs.length}
      <VirtualDevices {outputs} values={deviceValues} />
    {:else}
      <p class="muted">Crea un output para ver su dispositivo virtual.</p>
    {/if}
  </section>

  {#if verdict}
    <section class="verdict {verdict.reason}">
      {#if verdict.reason === "consensus"}
        ✓ CONSENSO alcanzado en la ronda {verdict.round}
      {:else}
        ⚠ Sin consenso tras {verdict.round} rondas — resolución forzada
        (mayoría; empate → estado de seguridad)
      {/if}
    </section>
  {/if}

  {#if rounds.length}
    <section>
      <h2>Deliberación</h2>
      <Deliberation {rounds} />
    </section>
  {/if}
</main>

<style>
  main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 1.5rem 1rem 4rem;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }
  h1 {
    font-size: 1.4rem;
    margin: 0;
  }
  h2 {
    font-size: 1.05rem;
    color: #9fb3c8;
  }
  .controls {
    display: flex;
    gap: 0.6rem;
    align-items: center;
  }
  .status {
    font-family: monospace;
    color: #46b06a;
    font-size: 0.85rem;
  }
  button {
    background: #2c3237;
    color: #e8edf2;
    border: 1px solid #3a4147;
    border-radius: 6px;
    padding: 0.45rem 1rem;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  button.primary {
    background: #2f6f4f;
    border-color: #46b06a;
    font-weight: 700;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
  }
  .card {
    background: #1a1e22;
    border: 1px solid #2c3237;
    border-radius: 10px;
    padding: 1rem;
  }
  .item {
    border-bottom: 1px solid #2c3237;
    padding: 0.5rem 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: baseline;
  }
  .item p {
    width: 100%;
    margin: 0;
    font-size: 0.85rem;
  }
  .icon {
    padding: 0 0.5rem;
    margin-left: auto;
  }
  .form {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.6rem;
  }
  input,
  select,
  textarea {
    background: #12161a;
    color: #e8edf2;
    border: 1px solid #3a4147;
    border-radius: 6px;
    padding: 0.4rem 0.5rem;
    font-family: inherit;
    font-size: 0.9rem;
  }
  .form input,
  .form select {
    flex: 1 1 45%;
  }
  .form textarea {
    flex-basis: 100%;
  }
  .muted {
    color: #6b7681;
  }
  .error {
    background: #4a1f24;
    border: 1px solid #e74c3c;
    color: #f5b8bc;
    border-radius: 8px;
    padding: 0.6rem 0.9rem;
    font-size: 0.88rem;
    white-space: pre-wrap;
  }
  .verdict {
    border-radius: 8px;
    padding: 0.7rem 1rem;
    font-weight: 700;
    margin-top: 1rem;
  }
  .verdict.consensus {
    background: #1f4a33;
    color: #46b06a;
  }
  .verdict.forced_resolution {
    background: #4a3d1e;
    color: #f1c40f;
  }
</style>
