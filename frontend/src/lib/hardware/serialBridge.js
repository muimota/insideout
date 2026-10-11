// Puente WebSerial ⇄ placa (firmware lab_serial, protocolo de líneas de texto).
// Capa de transporte pura: no sabe nada de Svelte ni del laboratorio.
// Solo abre el puerto, envía órdenes y emite lecturas de sensores.

export class SerialBridge {
  constructor() {
    this.port = null;
    this.writer = null;
    this.reading = false;
    this.boardName = "";
    // Callbacks asignables:
    this.onInput = null; // (pin: number, value: number) => void  (líneas "IN ...")
    this.onClose = null; // () => void  (desconexión física o lógica)
    this._waiters = [];  // promesas pendientes de una línea concreta
  }

  static supported() {
    return typeof navigator !== "undefined" && "serial" in navigator;
  }

  get connected() {
    return !!this.port;
  }

  async connect(baudRate = 115200) {
    this.port = await navigator.serial.requestPort();
    await this.port.open({ baudRate });
    this.writer = this.port.writable.getWriter();
    this.reading = true;
    this._readLoop();
    const hello = await this._waitLine(
      (l) => l.startsWith("LABSERIAL") && l,
      2000,
      () => this.send("HELLO"),
    );
    this.boardName = hello.split(" ").slice(2).join(" ") || "placa";
  }

  async disconnect() {
    this.reading = false;
    try {
      this.writer?.releaseLock();
    } catch {
      /* ya liberado */
    }
    this.writer = null;
    try {
      await this.port?.close();
    } catch {
      /* puerto ya cerrado */
    }
    this.port = null;
  }

  async send(line) {
    if (!this.writer) return;
    await this.writer.write(new TextEncoder().encode(line + "\n"));
  }

  // ---- Atajos del protocolo lab_serial ----
  pinMode(pin, mode) {
    return this.send(`PM ${pin} ${mode}`); // mode: "I" | "P" | "O"
  }
  digitalWrite(pin, v) {
    return this.send(`DW ${pin} ${v ? 1 : 0}`);
  }
  analogWrite(pin, v) {
    return this.send(`AW ${pin} ${v}`);
  }
  servoWrite(pin, deg) {
    return this.send(`SV ${pin} ${deg}`);
  }
  watch(pin, mode, intervalMs) {
    return this.send(`WATCH ${pin} ${mode} ${intervalMs}`); // mode: "D" | "A"
  }
  unwatch(pin) {
    return this.send(`UNWATCH ${pin}`);
  }

  // ---- Internos ----

  async _readLoop() {
    const decoder = new TextDecoder();
    let buf = "";
    while (this.reading && this.port?.readable) {
      const reader = this.port.readable.getReader();
      try {
        while (this.reading) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let i;
          while ((i = buf.indexOf("\n")) >= 0) {
            const line = buf.slice(0, i).trim();
            buf = buf.slice(i + 1);
            if (line) this._handleLine(line);
          }
        }
      } catch {
        // Cable desconectado o puerto cerrado: salimos del bucle.
        break;
      } finally {
        reader.releaseLock();
      }
    }
    this.reading = false;
    this.port = null;
    this.onClose?.();
  }

  _handleLine(line) {
    // Resolver primero los waiters (p. ej. la respuesta a HELLO).
    this._waiters = this._waiters.filter((w) => !w(line));
    const m = line.match(/^IN (\d+) (\d+)$/);
    if (m) this.onInput?.(Number(m[1]), Number(m[2]));
  }

  // Espera una línea que satisfaga `match`; `kick` reenvía la petición.
  _waitLine(match, timeoutMs, kick) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this._waiters = this._waiters.filter((w) => w !== waiter);
        reject(new Error("La placa no respondió (timeout)"));
      }, timeoutMs);
      const waiter = (line) => {
        const res = match(line);
        if (res) {
          clearTimeout(timer);
          resolve(res);
        }
        return !!res;
      };
      this._waiters.push(waiter);
      kick?.();
    });
  }
}
