<script>
  let { outputs = [], values = {} } = $props();
</script>

<div class="flex flex-wrap items-start gap-8">
  {#each outputs as out (out.id)}
    <div class="flex flex-col items-center gap-[0.4rem]">
      {#if out.tipo === "bool"}
        <div
          class="relative h-[1.7rem] w-[3.4rem] rounded-full transition-colors duration-300 {values[out.id] === true ? 'bg-on' : 'bg-toggle'}">
          <div
            class="absolute top-[0.2rem] h-[1.3rem] w-[1.3rem] rounded-full bg-knob transition-[left] duration-300 {values[out.id] === true ? 'left-[1.9rem]' : 'left-[0.2rem]'}">
          </div>
        </div>
        <span class="font-semibold text-[0.95rem]">{out.name}</span>
        <span class="font-mono text-[1rem] text-accent">{values[out.id] === true ? "true" : values[out.id] === false ? "false" : "—"}</span>
      {:else if out.tipo === "texto"}
        <div class="min-h-[2rem] w-[8.5rem] break-words rounded-md border border-edge bg-inner px-2 py-[0.4rem] font-mono text-[0.85rem] text-accent">{values[out.id] || "(vacío)"}</div>
        <span class="font-semibold text-[0.95rem]">{out.name}</span>
      {:else}
        <div class="inline-flex min-h-[3rem] min-w-[5.5rem] items-center justify-center rounded-lg border border-edge bg-inner px-4 py-[0.35rem] font-mono text-[1.05rem] font-bold text-accent">{values[out.id] ?? "—"}</div>
        <span class="font-semibold text-[0.95rem]">{out.name}</span>
        <span class="font-mono text-[1rem] text-accent">{(out.enum_values ?? []).join(" | ")}</span>
      {/if}
    </div>
  {/each}
</div>
