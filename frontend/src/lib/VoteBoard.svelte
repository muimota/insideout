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
</script>

<div class="board">
  {#if live}
    <div class="liveonair">
      <span class="who">🗣 {live.agent_name} · ronda {live.round}</span>
      {#if live.text}
        <p class="stream">{live.text}<span class="caret"></span></p>
      {/if}
    </div>
  {/if}
  <table>
    <thead>
      <tr>
        <th>Output</th>
        {#each agents as a (a.id)}
          <th>{a.name}</th>
        {/each}
        <th>Estado</th>
      </tr>
    </thead>
    <tbody>
      {#each outputs as o (o.id)}
        {@const uni = unanimous(o.id)}
        {@const lock = locked[o.id]}
        <tr class:unanimous={uni} class:consensus={lock?.kind === "consensus"} class:forced={lock?.kind === "forced"}>
          <th>{o.name}</th>
          {#each agents as a (a.id)}
            {@const c = cell(o.id, a.id)}
            <td class:changed={c?.from != null} title={c?.justificacion || ""}>
              {#if c}
                <strong>{c.valor}</strong>
                {#if c.from != null}
                  <span class="flip">{c.from} → {c.valor}</span>
                {/if}
                {#if c.raw != null && String(c.raw) !== String(c.valor)}
                  <span class="intent raw">intención: {c.raw}</span>
                {/if}
                {#if c.justificacion}
                  <p class="intent">{c.justificacion}</p>
                {/if}
              {:else if live?.agent_id === a.id}
                <span class="thinking"><i></i><i></i><i></i></span>
              {:else}
                <span class="empty">—</span>
              {/if}
            </td>
          {/each}
          <td class="state">
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

<style>
  .board {
    overflow-x: auto;
  }
  .liveonair {
    border: 1px solid #2c3237;
    background: #14181b;
    border-radius: 8px;
    padding: 0.5rem 0.7rem;
    margin-bottom: 0.6rem;
  }
  .who {
    font-size: 0.75rem;
    color: #46b06a;
    font-weight: 600;
  }
  .stream {
    margin: 0.25rem 0 0;
    font-family: monospace;
    font-size: 0.85rem;
    color: #cdd6df;
    white-space: pre-wrap;
  }
  .caret {
    display: inline-block;
    width: 0.55em;
    height: 1em;
    background: #46b06a;
    vertical-align: text-bottom;
    animation: blink 1s steps(2) infinite;
  }
  @keyframes blink {
    to {
      opacity: 0;
    }
  }
  .thinking i {
    display: inline-block;
    width: 0.35rem;
    height: 0.35rem;
    margin-right: 0.25rem;
    border-radius: 50%;
    background: #46b06a;
    animation: pulse 1.2s infinite;
  }
  .thinking i:nth-child(2) {
    animation-delay: 0.2s;
  }
  .thinking i:nth-child(3) {
    animation-delay: 0.4s;
  }
  @keyframes pulse {
    0%,
    100% {
      opacity: 0.2;
    }
    50% {
      opacity: 1;
    }
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  th,
  td {
    border: 1px solid #2c3237;
    padding: 0.45rem 0.6rem;
    text-align: left;
    vertical-align: top;
  }
  thead th {
    color: #9fb3c8;
    font-weight: 600;
    background: #1a1e22;
  }
  tbody th {
    color: #cdd6df;
    font-weight: 600;
    background: #1a1e22;
  }
  td {
    background: #161a1d;
  }
  tr.unanimous td {
    background: #1a2a22;
  }
  tr.consensus td,
  tr.consensus th {
    box-shadow: inset 0 0 0 1px #2ecc71;
  }
  tr.forced td {
    background: #2a2418;
  }
  .changed strong {
    color: #f1c40f;
  }
  .flip {
    display: block;
    margin-top: 0.15rem;
    font-size: 0.75rem;
    color: #f1c40f;
  }
  .intent {
    margin: 0.25rem 0 0;
    font-size: 0.75rem;
    color: #8b98a5;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .intent.raw {
    display: block;
    color: #d08770;
    font-style: italic;
  }
  .empty {
    color: #6b7681;
  }
  .state {
    color: #9fb3c8;
    white-space: nowrap;
    font-size: 0.8rem;
  }
</style>
