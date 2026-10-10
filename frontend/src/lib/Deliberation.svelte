<script>
  export let rounds;
</script>

<div class="deliberation">
  {#each rounds as r (r.round)}
    <section class="round">
      <h3>Ronda {r.round}</h3>
      {#each r.turns as t (t.agent_id)}
        <article class="turn">
          <header>
            <strong>{t.agent_name}</strong>
            {#if t.timeout}
              <span class="badge timeout">timeout: mantiene voto anterior</span>
            {/if}
          </header>
          {#if t.thought}
            <p class="thought">{t.thought}</p>
          {:else}
            <p class="thought muted">(sin argumentación)</p>
          {/if}
          {#if t.proposals.length}
            <div class="proposals">
              {#each t.proposals as p (p.output_id)}
                <span class="proposal">
                  {p.output_name} =
                  <strong>{p.valor}</strong>
                  {#if String(p.raw_valor) !== String(p.valor)}
                    <em class="muted">(sanitizado de "{p.raw_valor}")</em>
                  {/if}
                  — {p.justificacion}
                </span>
              {/each}
            </div>
          {/if}
        </article>
      {/each}
    </section>
  {/each}
</div>

<style>
  .round {
    border: 1px solid #2c3237;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    margin-bottom: 1rem;
    background: #1a1e22;
  }
  .round h3 {
    margin: 0 0 0.6rem;
    font-size: 1rem;
    color: #9fb3c8;
  }
  .turn {
    border-left: 3px solid #46b06a;
    padding-left: 0.8rem;
    margin-bottom: 0.8rem;
  }
  .turn header {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  .thought {
    font-family: monospace;
    font-size: 0.88rem;
    white-space: pre-wrap;
    margin: 0.35rem 0;
    color: #cdd6df;
  }
  .muted {
    color: #6b7681;
  }
  .badge.timeout {
    background: #5a3d1e;
    color: #f1c40f;
    padding: 0.1rem 0.5rem;
    border-radius: 10px;
    font-size: 0.75rem;
  }
  .proposals {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .proposal {
    font-size: 0.88rem;
    background: #22282d;
    border-radius: 6px;
    padding: 0.3rem 0.5rem;
  }
</style>
