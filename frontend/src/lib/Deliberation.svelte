<script>
  export let round;
</script>

<div>
  {#each round.turns as t (t.agent_id)}
    <article class="mb-[0.8rem] border-l-[3px] border-accent pl-[0.8rem] last:mb-0">
      <header class="flex items-center gap-2">
        <strong>{t.agent_name}</strong>
        {#if t.timeout}
          <span class="rounded-full bg-timeout px-2 py-[0.1rem] text-[0.75rem] text-warn">timeout: mantiene voto anterior</span>
        {/if}
      </header>
      {#if t.thought}
        <p class="my-[0.35rem] font-mono text-[0.88rem] whitespace-pre-wrap text-body">{t.thought}</p>
      {:else}
        <p class="my-[0.35rem] font-mono text-[0.88rem] whitespace-pre-wrap text-dim">(sin argumentación)</p>
      {/if}
      {#if t.proposals.length}
        <div class="flex flex-col gap-1">
          {#each t.proposals as p (p.output_id)}
            <span class="rounded-md bg-proposal px-2 py-[0.3rem] text-[0.88rem]">
              {p.output_name} =
              <strong>{p.valor}</strong>
              {#if String(p.raw_valor) !== String(p.valor)}
                <em class="text-dim">(sanitizado de "{p.raw_valor}")</em>
              {/if}
              — {p.justificacion}
            </span>
          {/each}
        </div>
      {/if}
    </article>
  {/each}
</div>
