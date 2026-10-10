<script>
  export let outputs;
  export let values = {};

  const ledColors = {
    OFF: "#3a3f44",
    VERDE: "#2ecc71",
    AMBAR: "#f1c40f",
    ROJO: "#e74c3c",
  };
</script>

<div class="devices">
  {#each outputs as out (out.id)}
    <div class="device">
      {#if out.device_type === "led"}
        <div class="led" class:on={values[out.id] && values[out.id] !== "OFF"}
          style={`--led-color: ${ledColors[values[out.id]] ?? ledColors.OFF}`}>
        </div>
        <span class="device-name">{out.name}</span>
        <span class="device-value">{values[out.id] ?? "—"}</span>
      {:else if out.device_type === "servo"}
        <div class="servo">
          <div class="dial">
            <div class="needle" style={`transform: rotate(${values[out.id] ?? 0}deg)`}></div>
            <div class="hub"></div>
          </div>
        </div>
        <span class="device-name">{out.name}</span>
        <span class="device-value">{values[out.id] ?? "—"}°</span>
      {:else if out.device_type === "nivel"}
        <div class="nivel">
          {#each out.enum_values as v (v)}
            <div class="seg" class:on={values[out.id] >= v}></div>
          {/each}
        </div>
        <span class="device-name">{out.name}</span>
        <span class="device-value">{values[out.id] ?? "—"}</span>
      {/if}
    </div>
  {/each}
</div>

<style>
  .devices {
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
    align-items: flex-start;
  }
  .device {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.4rem;
  }
  .device-name {
    font-weight: 600;
    font-size: 0.95rem;
  }
  .device-value {
    font-family: monospace;
    font-size: 1rem;
    color: #46b06a;
  }
  .led {
    width: 3rem;
    height: 3rem;
    border-radius: 50%;
    background: var(--led-color);
    border: 3px solid #1c2023;
    transition: background 0.3s, box-shadow 0.3s;
  }
  .led.on {
    box-shadow: 0 0 1.6rem 0.4rem var(--led-color);
  }
  .servo .dial {
    position: relative;
    width: 4rem;
    height: 4rem;
    border-radius: 50%;
    background: #23282d;
    border: 3px solid #12161a;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .needle {
    position: absolute;
    bottom: 50%;
    width: 4px;
    height: 46%;
    background: #e74c3c;
    transform-origin: bottom center;
    transition: transform 0.5s ease;
    border-radius: 2px;
  }
  .hub {
    width: 0.9rem;
    height: 0.9rem;
    border-radius: 50%;
    background: #f0f3f5;
  }
  .nivel {
    display: flex;
    flex-direction: column-reverse;
    gap: 3px;
  }
  .nivel .seg {
    width: 2.4rem;
    height: 0.55rem;
    border-radius: 3px;
    background: #3a3f44;
    transition: background 0.3s;
  }
  .nivel .seg.on {
    background: #2ecc71;
  }
</style>
