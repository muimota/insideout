<script>
  import { onMount } from "svelte";
  import VirtualDevices from "./lib/VirtualDevices.svelte";
  import Deliberation from "./lib/Deliberation.svelte";
  import VoteBoard from "./lib/VoteBoard.svelte";

  const API = "http://localhost:8000";

  let agents = $state([]);
  let inputs = $state([]);
  let outputs = $state([]);
  let phase = $state("build");
  let status = $state("");
  let error = $state("");
  let rounds = $state([]);
  let deviceValues = $state({});
  let votes = $state({});
  let roundVotes = $state({});
  let locked = $state({});
  let roundLocked = $state({});
  let live = $state(null);
  let verdict = $state(null);
  let busy = $state(false);

  let newAgent = $state({ name: "", personality: "" });
  let newInput = $state({ name: "", tipo: "bool", enum_values: "", description: "" });
  let newOutput = $state({
    name: "",
    tipo: "enum",
    enum_values: "",
    description: "",
  });

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

  let dragIndex = $state(null);
  let overIndex = $state(null);
  let editingId = $state(null);
  let editBuf = $state("");
  let editNameId = $state(null);
  let nameBuf = $state("");

  function onAgentDragStart(i, e) {
    dragIndex = i;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(i));
  }

  function onAgentDragOver(i, e) {
    if (dragIndex === null) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    overIndex = i;
  }

  function onAgentDrop(i, e) {
    e.preventDefault();
    if (dragIndex === null || dragIndex === i) {
      dragIndex = overIndex = null;
      return;
    }
    const next = [...agents];
    const [moved] = next.splice(dragIndex, 1);
    next.splice(i, 0, moved);
    agents = next;
    dragIndex = overIndex = null;
    call("/agents/order", "PUT", { ids: next.map((a) => a.id) });
  }

  function onAgentDragEnd() {
    dragIndex = overIndex = null;
  }

  function startEdit(a) {
    if (busy) return;
    editingId = a.id;
    editBuf = a.personality;
  }

  function cancelEdit() {
    editingId = null;
  }

  function saveEdit(a) {
    const buf = editBuf.trim();
    editingId = null;
    if (buf && buf !== a.personality) {
      call(`/agents/${a.id}`, "PUT", { personality: buf });
    }
  }

  function editKeys(a, e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.target.blur();
    } else if (e.key === "Escape") {
      editBuf = a.personality;
      e.target.blur();
    }
  }

  function startEditName(a) {
    if (busy) return;
    editNameId = a.id;
    nameBuf = a.name;
  }

  function saveEditName(a) {
    const buf = nameBuf.trim();
    editNameId = null;
    if (buf && buf !== a.name) {
      call(`/agents/${a.id}`, "PUT", { name: buf });
    }
  }

  function nameKeys(a, e) {
    if (e.key === "Enter") {
      e.preventDefault();
      e.target.blur();
    } else if (e.key === "Escape") {
      nameBuf = a.name;
      e.target.blur();
    }
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
    const body = {
      name: newOutput.name.trim(),
      tipo: newOutput.tipo,
      description: newOutput.description.trim(),
    };
    if (newOutput.tipo === "enum") {
      body.enum_values = newOutput.enum_values
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => {
          const n = Number(s);
          return s !== "" && Number.isFinite(n) ? n : s;
        });
      if (!body.enum_values.length) return;
    }
    await call("/outputs", "POST", body);
    newOutput = {
      name: "",
      tipo: "enum",
      enum_values: "",
      description: "",
    };
  }

  async function setInputValue(id, value) {
    await call(`/experiment/inputs/${id}/value`, "POST", { value });
  }

  async function resetAll() {
    rounds = [];
    deviceValues = {};
    votes = {};
    roundVotes = {};
    locked = {};
    roundLocked = {};
    live = null;
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
    votes = {};
    roundVotes = {};
    locked = {};
    roundLocked = {};
    live = null;
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

  function snapshot(obj) {
    return JSON.parse(JSON.stringify(obj ?? {}));
  }

  function handleEvent(ev) {
    switch (ev.type) {
      case "round_start":
        rounds.push({ round: ev.round, turns: [] });
        roundVotes[ev.round] = snapshot(votes);
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
          rejected: [],
          timeout: false,
        });
        live = {
          round: ev.round,
          agent_id: ev.agent_id,
          agent_name: ev.agent_name,
          text: "",
        };
        status = `Ronda ${ev.round}: turno de ${ev.agent_name}`;
        break;
      case "thought_token": {
        const r = rounds[rounds.length - 1];
        if (r && r.turns.length) {
          r.turns[r.turns.length - 1].thought += ev.text;
        }
        if (live && live.agent_id === ev.agent_id) {
          live = { ...live, text: live.text + ev.text };
        }
        break;
      }
      case "proposal": {
        const r = rounds[rounds.length - 1];
        if (r && r.turns.length) {
          r.turns[r.turns.length - 1].proposals.push(ev);
        }
        const prev = votes[ev.output_id]?.[ev.agent_id];
        const from =
          prev && String(prev.valor) !== String(ev.valor) ? prev.valor : null;
        votes[ev.output_id] = {
          ...(votes[ev.output_id] ?? {}),
          [ev.agent_id]: {
            valor: ev.valor,
            raw: ev.raw_valor,
            justificacion: ev.justificacion,
            from,
            round: ev.round,
          },
        };
        roundVotes[ev.round] = snapshot(votes);
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
        locked[ev.output_id] = { kind: "consensus", valor: ev.valor, round: ev.round };
        roundLocked[ev.round] = snapshot(locked);
        status = `CONSENSO en ${ev.output_name} = ${ev.valor} (ronda ${ev.round})`;
        break;
      case "decision":
        deviceValues[ev.output_id] = ev.valor;
        locked[ev.output_id] = {
          kind: "decision",
          valor: ev.valor,
          round: ev.round,
          via: ev.via,
        };
        roundLocked[ev.round] = snapshot(locked);
        status = `DECISIÓN (agente único): ${ev.output_name} = ${ev.valor}`;
        break;
      case "invalid_proposal": {
        const r = rounds[rounds.length - 1];
        if (r && r.turns.length) {
          r.turns[r.turns.length - 1].rejected.push(ev);
        }
        status = `Voto rechazado (${ev.agent_name}): ${ev.motivo}`;
        break;
      }
      case "forced_resolution":
        deviceValues[ev.output_id] = ev.valor;
        locked[ev.output_id] = { kind: "forced", valor: ev.valor, round: ev.round };
        roundLocked[ev.round] = snapshot(locked);
        status = `RESOLUCIÓN FORZADA: ${ev.output_name} = ${ev.valor}`;
        break;
      case "simulation_end":
        live = null;
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

<main class="mx-auto max-w-[1100px] px-4 py-6 pb-16">
  <header class="flex flex-wrap items-center justify-between gap-4">
    <h1 class="text-[1.4rem]">Laboratorio de Deliberación</h1>
    <div class="flex items-center gap-2.5">
      {#if status}<span class="font-mono text-[0.85rem] text-accent">{status}</span>{/if}
      <button
        class="btn btn-primary"
        disabled={phase === "running" || busy || !agents.length || !outputs.length}
        onclick={play}>
        ▶ Play
      </button>
      <button class="btn" onclick={resetAll} disabled={phase === "running" || busy}>
        Reiniciar
      </button>
    </div>
  </header>

  {#if error}
    <p class="my-4 rounded-lg border border-danger bg-danger-deep px-[0.9rem] py-[0.6rem] text-[0.88rem] whitespace-pre-wrap text-danger-soft">{error}</p>
  {/if}

  <section class="mt-4 grid gap-4 grid-cols-[repeat(auto-fit,minmax(280px,1fr))]">
    <div class="card">
      <h2 class="text-[1.05rem] text-soft">Agentes</h2>
      <p class="mb-1 text-[0.7rem] text-dim">
        arrastra para reordenar los turnos · doble click en el nombre o en la personalidad para editar
      </p>
      {#each agents as a, i (a.id)}
        <div
          class="flex flex-wrap items-baseline gap-2 border-b border-edge py-2 select-none {dragIndex !== null && dragIndex !== i && overIndex === i ? 'outline -outline-offset-1 outline-1 outline-accent' : ''}"
          class:cursor-grab={dragIndex === null}
          class:cursor-grabbing={dragIndex === i}
          draggable={!busy && editNameId !== a.id && editingId !== a.id}
          ondragstart={(e) => onAgentDragStart(i, e)}
          ondragover={(e) => onAgentDragOver(i, e)}
          ondrop={(e) => onAgentDrop(i, e)}
          ondragend={onAgentDragEnd}>
          {#if editNameId === a.id}
            <input
              class="field text-[0.95rem] font-semibold"
              bind:value={nameBuf}
              onblur={() => saveEditName(a)}
              onkeydown={(e) => nameKeys(a, e)} />
          {:else}
            <strong
              class="cursor-text decoration-dotted hover:underline"
              title="doble click para editar el nombre"
              ondblclick={() => startEditName(a)}>
              {a.name}
            </strong>
          {/if}
          <button class="btn ml-auto px-2" disabled={busy} onclick={() => call(`/agents/${a.id}`, "DELETE")}>×</button>
          {#if editingId === a.id}
            <textarea
              class="field mt-1 w-full text-[0.85rem] text-dim"
              rows="3"
              bind:value={editBuf}
              onblur={() => saveEdit(a)}
              onkeydown={(e) => editKeys(a, e)}></textarea>
          {:else}
            <p
              class="m-0 w-full text-[0.85rem] text-dim hover:text-body"
              title="doble click para editar la personalidad"
              ondblclick={() => startEdit(a)}>
              {a.personality}
            </p>
          {/if}
        </div>
      {/each}
      <div class="mt-[0.6rem] flex flex-wrap gap-[0.4rem]">
        <input class="field flex-[1_1_45%]" placeholder="nombre" bind:value={newAgent.name} />
        <textarea class="field basis-full" placeholder="prompt de personalidad" rows="3" bind:value={newAgent.personality}></textarea>
        <button class="btn" onclick={addAgent} disabled={busy}>+ Agente</button>
      </div>
    </div>

    <div class="card">
      <h2 class="text-[1.05rem] text-soft">Inputs (sensores virtuales)</h2>
      {#each inputs as inp (inp.id)}
        <div class="flex flex-wrap items-baseline gap-2 border-b border-edge py-2">
          <strong>{inp.name}</strong>
          <span class="text-dim">{inp.tipo}</span>
          <button class="btn ml-auto px-2" disabled={busy} onclick={() => call(`/inputs/${inp.id}`, "DELETE")}>×</button>
          <p class="m-0 w-full text-[0.85rem] text-dim">{inp.description}</p>
          {#if inp.tipo === "bool"}
            <select class="field" value={String(inp.value ?? false)} onchange={(e) => setInputValue(inp.id, e.target.value === "true")}>
              <option value="false">false</option>
              <option value="true">true</option>
            </select>
          {:else if inp.tipo === "enum"}
            <select class="field" value={inp.value} onchange={(e) => setInputValue(inp.id, e.target.value)}>
              {#each inp.enum_values as v (v)}
                <option value={v}>{v}</option>
              {/each}
            </select>
          {:else}
            <input
              class="field"
              value={inp.value ?? ""}
              onchange={(e) => setInputValue(inp.id, e.target.value)} />
          {/if}
        </div>
      {/each}
      <div class="mt-[0.6rem] flex flex-wrap gap-[0.4rem]">
        <input class="field flex-[1_1_45%]" placeholder="nombre" bind:value={newInput.name} />
        <select class="field flex-[1_1_45%]" bind:value={newInput.tipo}>
          <option value="bool">bool</option>
          <option value="enum">enum</option>
          <option value="texto">texto</option>
        </select>
        {#if newInput.tipo === "enum"}
          <input class="field flex-[1_1_45%]" placeholder="valores, separados por comas" bind:value={newInput.enum_values} />
        {/if}
        <input class="field flex-[1_1_45%]" placeholder="descripción (la ve el agente)" bind:value={newInput.description} />
        <button class="btn" onclick={addInput} disabled={busy}>+ Input</button>
      </div>
    </div>

    <div class="card">
      <h2 class="text-[1.05rem] text-soft">Outputs (actuadores virtuales)</h2>
      {#each outputs as o (o.id)}
        <div class="flex flex-wrap items-baseline gap-2 border-b border-edge py-2">
          <strong>{o.name}</strong>
          <span class="text-dim">
            {o.tipo === "enum"
              ? "enum: " + (o.enum_values ?? []).join(" | ")
              : o.tipo === "bool"
                ? "bool: true | false"
                : "texto"}
          </span>
          <button class="btn ml-auto px-2" disabled={busy} onclick={() => call(`/outputs/${o.id}`, "DELETE")}>×</button>
          <p class="m-0 w-full text-[0.85rem] text-dim">{o.description}</p>
        </div>
      {/each}
      <div class="mt-[0.6rem] flex flex-wrap gap-[0.4rem]">
        <input class="field flex-[1_1_45%]" placeholder="nombre" bind:value={newOutput.name} />
        <select class="field flex-[1_1_45%]" bind:value={newOutput.tipo}>
          <option value="bool">bool</option>
          <option value="enum">enum</option>
          <option value="texto">texto</option>
        </select>
        {#if newOutput.tipo === "enum"}
          <input class="field flex-[1_1_45%]" placeholder="valores, separados por comas" bind:value={newOutput.enum_values} />
        {/if}
        <input class="field flex-[1_1_45%]" placeholder="descripción (la ve el agente)" bind:value={newOutput.description} />
        <button class="btn" onclick={addOutput} disabled={busy}>+ Output</button>
      </div>
    </div>
  </section>

  <section>
    <h2 class="text-[1.05rem] text-soft">Dispositivos virtuales</h2>
    {#if outputs.length}
      <VirtualDevices {outputs} values={deviceValues} />
    {:else}
      <p class="text-dim">Crea un output para ver su dispositivo virtual.</p>
    {/if}
  </section>

  {#if verdict}
    <section class="mt-4 rounded-lg px-4 py-[0.7rem] font-bold {verdict.reason === 'forced_resolution' ? 'bg-warn-deep text-warn' : 'bg-consensus text-accent'}">
      {#if verdict.reason === "consensus"}
        ✓ CONSENSO alcanzado en la ronda {verdict.round}
      {:else if verdict.reason === "decision"}
        ✓ Decisión individual (agente único) — ronda {verdict.round}
      {:else}
        ⚠ Sin consenso tras {verdict.round} rondas — resolución forzada
        (mayoría; empate → estado de seguridad)
      {/if}
    </section>
  {/if}

  {#if rounds.length}
    <section>
      <h2 class="text-[1.05rem] text-soft">Pizarra de votos</h2>
      {#each rounds as r (r.round)}
        <div class="mb-4 rounded-[10px] border border-edge bg-panel px-4 py-[0.8rem]">
          <h3 class="mb-[0.6rem] text-[1rem] text-soft">Ronda {r.round}</h3>
          <VoteBoard
            {agents}
            {outputs}
            votes={roundVotes[r.round] ?? {}}
            locked={roundLocked[r.round] ?? {}}
            live={live && live.round === r.round ? live : null}
          />
          <h4 class="mb-2 mt-4 border-t border-edge pt-3 text-[0.8rem] font-semibold tracking-wider text-dim uppercase">
            Deliberación
          </h4>
          <Deliberation round={r} />
        </div>
      {/each}
    </section>
  {/if}
</main>
