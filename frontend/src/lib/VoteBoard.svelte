<script>
  export let agents;
  export let outputs;
  export let votes;
  export let locked;

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
            <td class:changed={c?.from != null}>
              {#if c}
                <strong>{c.valor}</strong>
                {#if c.from != null}
                  <span class="flip">{c.from} → {c.valor}</span>
                {/if}
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
  .empty {
    color: #6b7681;
  }
  .state {
    color: #9fb3c8;
    white-space: nowrap;
    font-size: 0.8rem;
  }
</style>
