// Estado reactivo del puente hardware + mapeo valor lógico ↔ valor eléctrico.
//
// Filosofía (igual que el backend): los valores que circulan por la
// deliberación son siempre LÓGICOS ("VERDE", 45, true). La traducción a lo
// eléctrico ocurre en dos fronteras:
//   - aquí: output lógico → orden serie (DW/AW/SV) según el binding
//   - en el firmware: la orden serie → nivel de pin
//
// Los bindings pin ↔ input/output se guardan en localStorage del navegador:
// el backend no necesita saber nada del hardware.

import { SerialBridge } from "./serialBridge.js";

const LS_KEY = "lab.hw.bindings.v1";

function loadBindings() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* localStorage no disponible */
  }
  return { inputs: {}, outputs: {} };
}

function saveBindings() {
  try {
    localStorage.setItem(
      LS_KEY,
      JSON.stringify({ inputs: hw.inputBindings, outputs: hw.outputBindings }),
    );
  } catch {
    /* localStorage no disponible */
  }
}

const persisted = loadBindings();

export const hw = $state({
  supported: SerialBridge.supported(),
  connected: false,
  connecting: false,
  board: "",
  error: "",
  inputBindings: persisted.inputs ?? {}, // input_id  → { pin, mode }
  outputBindings: persisted.outputs ?? {}, // output_id → { pin, mode }
  live: {}, // pin → última lectura recibida (para mostrar en la UI)
});

let bridge = null;
let inputSink = null; // (input_id, value) => void → lo registra App.svelte
let inputDefs = []; // defs actuales de inputs (para mapear valores)
let outputDefs = []; // defs actuales de outputs
const lastSent = {}; // input_id → { value, ms, timer } (anti-rebote/throttle)

// ------------------------------------------------------------------ mapeos

// ¿Qué modos físicos admite cada definición?
export function outputModes(out) {
  if (out.tipo === "bool") return [["digital", "digital (ON/OFF)"]];
  if (out.tipo === "enum" && (out.enum_values ?? []).every(isNumeric))
    return [
      ["servo", "servo (0–180°)"],
      ["pwm", "PWM (0–255)"],
    ];
  return []; // texto y enums de texto: solo virtual
}

export function inputModes(inp) {
  if (inp.tipo === "bool")
    return [
      ["digital", "digital (activo en HIGH)"],
      ["pullup", "pullup (activo en LOW, p.ej. botón a GND)"],
    ];
  if (inp.tipo === "enum" && (inp.enum_values ?? []).every(isNumeric))
    return [["analog", "analógico (0–1023)"]];
  return [];
}

function isNumeric(v) {
  return v !== "" && Number.isFinite(Number(v));
}

function clamp(n, lo, hi) {
  return Math.min(hi, Math.max(lo, Math.round(n)));
}

// Valor lógico de un input a partir de la lectura del pin.
function mapSensorValue(inp, mode, raw) {
  if (inp.tipo === "bool") {
    if (mode === "pullup") return raw === 0; // pulsado = LOW
    return raw >= 1;
  }
  if (inp.tipo === "enum") {
    // Enum numérico: valor del enum más cercano a la lectura 0..1023
    // escalada al rango del enum (misma filosofía que sanitize_output).
    const nums = (inp.enum_values ?? []).map(Number);
    if (!nums.length) return null;
    const lo = Math.min(...nums);
    const hi = Math.max(...nums);
    const scaled = lo + (raw / 1023) * (hi - lo);
    const idx = nums.reduce(
      (best, n, i) => (Math.abs(n - scaled) < Math.abs(nums[best] - scaled) ? i : best),
      0,
    );
    return inp.enum_values[idx]; // se devuelve el valor original del enum
  }
  return null;
}

// ------------------------------------------------------------------ conexión

export async function connectBoard() {
  hw.error = "";
  hw.connecting = true;
  try {
    bridge = new SerialBridge();
    bridge.onInput = handleSensor;
    bridge.onClose = () => {
      bridge = null;
      hw.connected = false;
      hw.board = "";
      hw.live = {};
    };
    await bridge.connect();
    hw.board = bridge.boardName;
    hw.connected = true;
    await applyAllBindings();
  } catch (e) {
    bridge = null;
    // Cancelar el selector de puerto no es un error digno de mostrar.
    if (String(e?.name) !== "NotFoundError") hw.error = String(e?.message || e);
  } finally {
    hw.connecting = false;
  }
}

export async function disconnectBoard() {
  await bridge?.disconnect();
  bridge = null;
  hw.connected = false;
  hw.board = "";
  hw.live = {};
}

// Configura en la placa todos los bindings activos (tras conectar).
async function applyAllBindings() {
  if (!bridge) return;
  for (const [id, b] of Object.entries(hw.outputBindings)) {
    const out = outputDefs.find((o) => o.id === id);
    if (!out) continue;
    if (b.mode === "digital") await bridge.pinMode(b.pin, "O");
    if (b.mode === "servo") await bridge.pinMode(b.pin, "O");
    if (b.mode === "pwm") await bridge.pinMode(b.pin, "O");
  }
  for (const [id, b] of Object.entries(hw.inputBindings)) {
    const inp = inputDefs.find((i) => i.id === id);
    if (!inp) continue;
    await armInputWatcher(inp, b);
  }
}

async function armInputWatcher(inp, b) {
  if (b.mode === "pullup") {
    await bridge.pinMode(b.pin, "P");
    await bridge.watch(b.pin, "D", 60);
  } else if (b.mode === "digital") {
    await bridge.pinMode(b.pin, "I");
    await bridge.watch(b.pin, "D", 60);
  } else if (b.mode === "analog") {
    await bridge.pinMode(b.pin, "I");
    await bridge.watch(b.pin, "A", 120);
  }
}

// ------------------------------------------------------------------ bindings

export async function bindOutput(out, pin, mode) {
  hw.outputBindings[out.id] = { pin, mode };
  saveBindings();
  if (bridge) await bridge.pinMode(pin, "O");
}

export function unbindOutput(out) {
  delete hw.outputBindings[out.id];
  saveBindings();
}

export async function bindInput(inp, pin, mode) {
  hw.inputBindings[inp.id] = { pin, mode };
  saveBindings();
  if (bridge) await armInputWatcher(inp, hw.inputBindings[inp.id]);
}

export async function unbindInput(inp) {
  const b = hw.inputBindings[inp.id];
  delete hw.inputBindings[inp.id];
  saveBindings();
  if (bridge && b) await bridge.unwatch(b.pin);
}

// ------------------------------------------------------------------ flujo

// App.svelte registra aquí cómo empujar valores al backend (POST /inputs/…).
export function setHwInputSink(fn) {
  inputSink = fn;
}

// App.svelte mantiene frescas las defs (para mapear enums, nombres, etc.).
export function syncHwDefs(inputs, outputs) {
  inputDefs = inputs ?? [];
  outputDefs = outputs ?? [];
}

// Evento "command" del SSE: si el output está vinculado, actuar sobre el pin.
export async function hwApplyCommand(outputId, valor) {
  if (!bridge || !hw.connected) return;
  const b = hw.outputBindings[outputId];
  const out = outputDefs.find((o) => o.id === outputId);
  if (!b || !out) return;
  try {
    if (out.tipo === "bool" && b.mode === "digital") {
      await bridge.digitalWrite(b.pin, valor === true || valor === "true");
    } else if (out.tipo === "enum" && b.mode === "servo") {
      await bridge.servoWrite(b.pin, clamp(Number(valor), 0, 180));
    } else if (out.tipo === "enum" && b.mode === "pwm") {
      await bridge.analogWrite(b.pin, clamp(Number(valor), 0, 255));
    }
  } catch (e) {
    hw.error = String(e?.message || e);
  }
}

// Lectura de un pin vinculado a un input: mapear y empujar al backend.
function handleSensor(pin, raw) {
  hw.live[pin] = raw;
  if (!inputSink) return;
  for (const [id, b] of Object.entries(hw.inputBindings)) {
    if (b.pin !== pin) continue;
    const inp = inputDefs.find((i) => i.id === id);
    if (!inp) continue;
    const value = mapSensorValue(inp, b.mode, raw);
    if (value === null || value === undefined) continue;
    throttledSend(id, value);
  }
}

// Anti-rebote: no repetir el mismo valor; como mucho 1 POST cada 250 ms,
// con envío final (trailing) para no perder el último valor estable.
function throttledSend(id, value) {
  const prev = lastSent[id];
  if (prev && prev.value === value && !prev.pending) return;
  const now = Date.now();
  if (prev && now - prev.ms < 250) {
    if (prev.timer) clearTimeout(prev.timer);
    prev.pending = value;
    prev.timer = setTimeout(() => {
      const v = lastSent[id]?.pending;
      lastSent[id] = { value: v, ms: Date.now(), timer: null, pending: undefined };
      if (v !== undefined) inputSink(id, v);
    }, 250 - (now - prev.ms));
    return;
  }
  if (prev?.timer) clearTimeout(prev.timer);
  lastSent[id] = { value, ms: now, timer: null, pending: undefined };
  inputSink(id, value);
}
