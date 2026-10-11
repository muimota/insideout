<script>
  export let agents;
  export let outputs;
  export let votes;
  export let locked;
  export let live = null;

  function cell(outputId, agentId) {
    return votes[outputId]?.[agentId] ?? null;
  }

  function unanimous(outputId) {
    if (!agents.length) return false;
    const vals = agents.map((a) => cell(outputId, a.id)?.valor);
    if (vals.some((v) => v == null)) return false;
    return new Set(vals.map(String)).size === 1;
  }

  function thClasses(lockKind) {
    const base = "border border-edge px-[0.6rem] py-[0.45rem] text-left align-top font-semibold";
    const ring = lockKind === "consensus" ? " shadow-[inset_0_0_0_1px_#2ecc71]" : "";
    return `${base} bg-panel text-body${ring}`;
  }

  function tdClasses(uni, lockKind) {
    const base = "border border-edge px-[0.6rem] py-[0.45rem] text-left align-top";
    let bg = "bg-inner";
    if (lockKind === "consensus") bg = "bg-inner shadow-[inset_0_0_0_1px_#2ecc71]";
    else if (lockKind === "forced") bg = "bg-forced";
    else if (uni) bg = "bg-unanimous";
    return `${base} ${bg}`;
  }
</script>

<div class="overflow-x-auto">
  {#if live}
    <div class="mb-[0.6rem] rounded-lg border border-edge bg-live px-[0.7rem] py-2">
      <span class="text-[0.75rem] font-semibold text-accent">🗣 {live.agent_name} · ronda {live.round}</span>
      {#if live.text}
        <p class="mt-1 font-mono text-[0.85rem] whitespace-pre-wrap text-body">{live.text}<span class="inline-block h-[1em] w-[0.55em] animate-caretblink bg-accent align-text-bottom"></span></p>
      {/if}
    </div>
  {/if}
  <table class="w-full border-collapse text-[0.9rem]">
    <thead>
      <tr>
        <th class="border border-edge bg-panel px-[0.6rem] py-[0.45rem] text-left align-top font-semibold text-soft">Output</th>
        {#each agents as a (a.id)}
          <th class="border border-edge bg-panel px-[0.6rem] py-[0.45rem] text-left align-top font-semibold text-soft">{a.name}</th>
        {/each}
        <th class="border border-edge bg-panel px-[0.6rem] py-[0.45rem] text-left align-top font-semibold text-soft">Estado</th>
      </tr>
    </thead>
    <tbody>
      {#each outputs as o (o.id)}
        {@const uni = unanimous(o.id)}
        {@const lock = locked[o.id]}
        <tr>
          <th class={thClasses(lock?.kind)}>{o.name}</th>
          {#each agents as a (a.id)}
            {@const c = cell(o.id, a.id)}
            <td class={tdClasses(uni, lock?.kind)} title={c?.justificacion || ""}>
              {#if c}
                <strong class={c.from != null ? "text-warn" : ""}>{c.valor}</strong>
                {#if c.from != null}
                  <span class="mt-[0.15rem] block text-[0.75rem] text-warn">{c.from} → {c.valor}</span>
                {/if}
                {#if c.raw != null && String(c.raw) !== String(c.valor)}
                  <span class="block text-[0.75rem] italic text-raw">intención: {c.raw}</span>
                {/if}
                {#if c.justificacion}
                  <p class="mt-1 overflow-hidden text-[0.75rem] text-dim2 line-clamp-3">{c.justificacion}</p>
                {/if}
              {:else if live?.agent_id === a.id}
                <span class="thinking flex gap-1">
                  <i class="inline-block h-[0.35rem] w-[0.35rem] animate-dot rounded-full bg-accent"></i>
                  <i class="inline-block h-[0.35rem] w-[0.35rem] animate-dot rounded-full bg-accent [animation-delay:0.2s]"></i>
                  <i class="inline-block h-[0.35rem] w-[0.35rem] animate-dot rounded-full bg-accent [animation-delay:0.4s]"></i>
                </span>
              {:else}
                <span class="text-dim">—</span>
              {/if}
            </td>
          {/each}
          <td class="border border-edge bg-inner px-[0.6rem] py-[0.45rem] text-left align-top whitespace-nowrap text-[0.8rem] text-soft">
            {#if lock?.kind === "consensus"}
              consenso · ronda {lock.round}
            {:else if lock?.kind === "forced"}
              forzado → {lock.valor}
            {:else if uni}
              unánime
            {:else}
              en debate
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
