<script>
  import {
    hw,
    connectBoard,
    disconnectBoard,
    bindInput,
    unbindInput,
    bindOutput,
    unbindOutput,
    inputModes,
    outputModes,
    syncHwDefs,
  } from "./hardware/hwStore.svelte.js";

  let { inputs = [], outputs = [] } = $props();

  // Mantén el store al día con las defs actuales (para mapear enums).
  $effect(() => syncHwDefs(inputs, outputs));

  // Buffers locales de edición de binding: id → { pin, mode }
  let draft = $state({});

  function draftFor(id, modes) {
    if (!draft[id]) draft[id] = { pin: "", mode: modes[0]?.[0] ?? "" };
    return draft[id];
  }

  function validPin(pin) {
    const n = Number(pin);
    return pin !== "" && Number.isInteger(n) && n >= 0 && n <= 48;
  }
</script>

<div class="card">
  <h2 class="text-[1.05rem] text-soft">Hardware físico (desde el navegador)</h2>

  {#if !hw.supported}
    <p class="m-0 text-[0.85rem] text-dim">
      Este navegador no soporta WebSerial. Usa <strong>Chrome o Edge</strong> y
      sirve la app desde <code>localhost</code> o HTTPS. Mientras tanto, los
      dispositivos virtuales siguen funcionando igual.
    </p>
  {:else}
    <div class="flex flex-wrap items-center gap-2.5">
      {#if hw.connected}
        <span class="font-mono text-[0.85rem] text-accent">
          ● {hw.board || "placa"} conectada por USB
        </span>
        <button class="btn" onclick={disconnectBoard}>Desconectar</button>
      {:else}
        <button class="btn btn-primary" onclick={connectBoard} disabled={hw.connecting}>
          {hw.connecting ? "Conectando…" : "🔌 Conectar placa (USB)"}
        </button>
        <span class="text-[0.8rem] text-dim">
          Arduino/ESP32 con el firmware <code>firmware/lab_serial.ino</code> · 115200 baudios
        </span>
      {/if}
    </div>

    {#if hw.error}
      <p class="mt-2 rounded-lg border border-danger bg-danger-deep px-[0.9rem] py-[0.6rem] text-[0.85rem] text-danger-soft">{hw.error}</p>
    {/if}

    <div class="mt-3 grid gap-4 grid-cols-[repeat(auto-fit,minmax(280px,1fr))]">
      <div>
        <h3 class="mb-1 text-[0.8rem] font-semibold tracking-wider text-dim uppercase">
          Sensores físicos → inputs
        </h3>
        {#each inputs as inp (inp.id)}
          {@const modes = inputModes(inp)}
          {@const bound = hw.inputBindings[inp.id]}
          <div class="flex flex-wrap items-center gap-2 border-b border-edge py-2 text-[0.88rem]">
            <strong>{inp.name}</strong>
            {#if !modes.length}
              <span class="text-dim">tipo «{inp.tipo}»: solo virtual</span>
            {:else if bound}
              <span class="font-mono text-accent">pin {bound.pin} · {bound.mode}</span>
              {#if hw.connected && hw.live[bound.pin] !== undefined}
                <span class="font-mono text-dim">= {hw.live[bound.pin]}</span>
              {/if}
              <button class="btn ml-auto px-2" onclick={() => unbindInput(inp)}>×</button>
            {:else}
              {@const d = draftFor(inp.id, modes)}
              <input class="field w-[4.5rem]" placeholder="pin" bind:value={d.pin} />
              <select class="field" bind:value={d.mode}>
                {#each modes as [value, label] (value)}
                  <option {value}>{label}</option>
                {/each}
              </select>
              <button
                class="btn ml-auto"
                disabled={!validPin(d.pin)}
                onclick={() => bindInput(inp, Number(d.pin), d.mode)}>
                Vincular
              </button>
            {/if}
          </div>
        {:else}
          <p class="m-0 text-[0.85rem] text-dim">No hay inputs definidos.</p>
        {/each}
        <p class="mt-1 text-[0.75rem] text-dim">
          Un input vinculado se alimenta del sensor físico (sobrescribe el valor manual).
        </p>
      </div>

      <div>
        <h3 class="mb-1 text-[0.8rem] font-semibold tracking-wider text-dim uppercase">
          Outputs → actuadores físicos
        </h3>
        {#each outputs as out (out.id)}
          {@const modes = outputModes(out)}
          {@const bound = hw.outputBindings[out.id]}
          <div class="flex flex-wrap items-center gap-2 border-b border-edge py-2 text-[0.88rem]">
            <strong>{out.name}</strong>
            {#if !modes.length}
              <span class="text-dim">tipo «{out.tipo}»: solo virtual</span>
            {:else if bound}
              <span class="font-mono text-accent">pin {bound.pin} · {bound.mode}</span>
              <button class="btn ml-auto px-2" onclick={() => unbindOutput(out)}>×</button>
            {:else}
              {@const d = draftFor(out.id, modes)}
              <input class="field w-[4.5rem]" placeholder="pin" bind:value={d.pin} />
              <select class="field" bind:value={d.mode}>
                {#each modes as [value, label] (value)}
                  <option {value}>{label}</option>
                {/each}
              </select>
              <button
                class="btn ml-auto"
                disabled={!validPin(d.pin)}
                onclick={() => bindOutput(out, Number(d.pin), d.mode)}>
                Vincular
              </button>
            {/if}
          </div>
        {:else}
          <p class="m-0 text-[0.85rem] text-dim">No hay outputs definidos.</p>
        {/each}
        <p class="mt-1 text-[0.75rem] text-dim">
          Cuando la deliberación emita un comando para un output vinculado, se aplicará también al pin físico.
        </p>
      </div>
    </div>
  {/if}
</div>
