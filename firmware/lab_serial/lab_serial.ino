/*
 * lab_serial.ino — Firmware genérico (filosofía Firmata) para el
 * Laboratorio de Deliberación entre Agentes.
 *
 * La placa NO conoce agentes, inputs ni outputs: solo expone sus pines
 * mediante un protocolo de líneas de texto por el puerto serie (115200).
 * Toda la lógica de mapeo pin ↔ input/output vive en el navegador
 * (frontend/src/lib/hardware/), que habla con la placa vía WebSerial.
 *
 * Compatible: Arduino Uno/Nano/Mega (AVR) y ESP32 (core 3.x).
 *
 * Protocolo (una orden por línea, terminada en '\n'):
 *
 *   Orden                Respuesta            Efecto
 *   -------------------  -------------------  --------------------------
 *   HELLO                LABSERIAL 1 <board>  identificación
 *   PM <pin> <I|P|O>     OK                  pinMode INPUT/INPUT_PULLUP/OUTPUT
 *   DW <pin> <0|1>       OK                  digitalWrite
 *   AW <pin> <0-255>     OK                  PWM (8 bits)
 *   SV <pin> <0-180>     OK                  servo (attach perezoso)
 *   DR <pin>             IN <pin> <0|1>      digitalRead
 *   AR <pin>             IN <pin> <0-1023>   analogRead normalizado
 *   WATCH <pin> <D|A> <ms>  OK              emite "IN <pin> <valor>" al cambiar
 *   UNWATCH <pin>        OK
 *   (orden inválida)     ERR <motivo>
 *
 * Las lecturas de sensores llegan siempre como líneas "IN <pin> <valor>".
 * Ejemplo de sesión (visible en el Monitor Serie):
 *   > HELLO
 *   < LABSERIAL 1 esp32
 *   > PM 13 O
 *   < OK
 *   > DW 13 1        → enciende el LED del pin 13
 *   > WATCH 34 A 100 → la placa empieza a avisar: IN 34 517 ...
 */

#if defined(ESP32)
  #include <ESP32Servo.h>  // instalar "ESP32Servo" desde el Gestor de Librerías
  #define BOARD_NAME "esp32"
#elif defined(ARDUINO_ARCH_AVR)
  #include <Servo.h>
  #define BOARD_NAME "arduino-avr"
#else
  #include <Servo.h>
  #define BOARD_NAME "arduino"
#endif

const int MAX_SERVOS = 4;
const int MAX_WATCHERS = 8;
// Umbral analógico (sobre 0..1023) para notificar cambios: evita ruido del ADC.
const int ANALOG_THRESHOLD = 8;

struct ServoSlot {
  int pin;
  Servo srv;
};
ServoSlot servos[MAX_SERVOS];

struct Watcher {
  int pin = -1;
  char mode = 'D';  // 'D' o 'A'
  unsigned long interval = 0;
  unsigned long lastMs = 0;
  int lastValue = -1;
};
Watcher watchers[MAX_WATCHERS];

char lineBuf[64];
int lineLen = 0;

// ---------------------------------------------------------------- utilidades

int readAnalog(int pin) {
  int raw = analogRead(pin);
#if defined(ESP32)
  return map(raw, 0, 4095, 0, 1023);  // ADC de 12 bits → escala común 0..1023
#else
  return raw;  // AVR ya devuelve 0..1023
#endif
}

void pwmWrite(int pin, int value) {
#if defined(ESP32)
  ledcAttach(pin, 5000, 8);  // core ESP32 3.x: canal PWM autoasignado
  ledcWrite(pin, value);
#else
  analogWrite(pin, value);
#endif
}

void report(int pin, int value) {
  Serial.print("IN ");
  Serial.print(pin);
  Serial.print(" ");
  Serial.println(value);
}

void ok() { Serial.println("OK"); }
void err(const char *msg) {
  Serial.print("ERR ");
  Serial.println(msg);
}

Servo *getServo(int pin) {
  for (int i = 0; i < MAX_SERVOS; i++)
    if (servos[i].pin == pin) return &servos[i].srv;
  for (int i = 0; i < MAX_SERVOS; i++)
    if (servos[i].pin == -1) {
      servos[i].pin = pin;
      servos[i].srv.attach(pin);
      return &servos[i].srv;
    }
  return NULL;
}

Watcher *findWatcher(int pin) {
  for (int i = 0; i < MAX_WATCHERS; i++)
    if (watchers[i].pin == pin) return &watchers[i];
  return NULL;
}

char *nextTok() { return strtok(NULL, " "); }

bool nextInt(int &out) {
  char *t = nextTok();
  if (!t) return false;
  out = atoi(t);
  return true;
}

// ------------------------------------------------------------------ comandos

void handleLine() {
  lineBuf[lineLen] = '\0';
  lineLen = 0;
  char *cmd = strtok(lineBuf, " ");
  if (!cmd) return;

  if (!strcmp(cmd, "HELLO")) {
    Serial.print("LABSERIAL 1 ");
    Serial.println(BOARD_NAME);
    return;
  }

  if (!strcmp(cmd, "PM")) {
    int pin;
    if (!nextInt(pin)) return err("PM <pin> <I|P|O>");
    char *m = nextTok();
    if (!m) return err("PM <pin> <I|P|O>");
    if (m[0] == 'I') pinMode(pin, INPUT);
    else if (m[0] == 'P') pinMode(pin, INPUT_PULLUP);
    else if (m[0] == 'O') pinMode(pin, OUTPUT);
    else return err("modo desconocido (I|P|O)");
    return ok();
  }

  if (!strcmp(cmd, "DW")) {
    int pin, v;
    if (!nextInt(pin) || !nextInt(v)) return err("DW <pin> <0|1>");
    digitalWrite(pin, v ? HIGH : LOW);
    return ok();
  }

  if (!strcmp(cmd, "AW")) {
    int pin, v;
    if (!nextInt(pin) || !nextInt(v)) return err("AW <pin> <0-255>");
    pwmWrite(pin, constrain(v, 0, 255));
    return ok();
  }

  if (!strcmp(cmd, "SV")) {
    int pin, deg;
    if (!nextInt(pin) || !nextInt(deg)) return err("SV <pin> <0-180>");
    Servo *s = getServo(pin);
    if (!s) return err("sin slots de servo libres");
    s->write(constrain(deg, 0, 180));
    return ok();
  }

  if (!strcmp(cmd, "DR")) {
    int pin;
    if (!nextInt(pin)) return err("DR <pin>");
    report(pin, digitalRead(pin));
    return;
  }

  if (!strcmp(cmd, "AR")) {
    int pin;
    if (!nextInt(pin)) return err("AR <pin>");
    report(pin, readAnalog(pin));
    return;
  }

  if (!strcmp(cmd, "WATCH")) {
    int pin, ms;
    char m[2] = {0, 0};
    char *mt;
    if (!nextInt(pin) || !(mt = nextTok()) || !nextInt(ms))
      return err("WATCH <pin> <D|A> <ms>");
    m[0] = mt[0];
    if (m[0] != 'D' && m[0] != 'A') return err("WATCH modo D|A");
    Watcher *w = findWatcher(pin);
    if (!w) {
      for (int i = 0; i < MAX_WATCHERS; i++)
        if (watchers[i].pin == -1) { w = &watchers[i]; break; }
    }
    if (!w) return err("sin watchers libres");
    w->pin = pin;
    w->mode = m[0];
    w->interval = (unsigned long)ms;
    w->lastMs = 0;
    w->lastValue = -1;
    return ok();
  }

  if (!strcmp(cmd, "UNWATCH")) {
    int pin;
    if (!nextInt(pin)) return err("UNWATCH <pin>");
    Watcher *w = findWatcher(pin);
    if (w) w->pin = -1;
    return ok();
  }

  err("orden desconocida");
}

// ------------------------------------------------------------- watchers

void runWatchers() {
  unsigned long now = millis();
  for (int i = 0; i < MAX_WATCHERS; i++) {
    Watcher *w = &watchers[i];
    if (w->pin < 0) continue;
    if (now - w->lastMs < w->interval) continue;
    w->lastMs = now;
    int v = (w->mode == 'A') ? readAnalog(w->pin) : digitalRead(w->pin);
    bool changed = (w->mode == 'A')
      ? (w->lastValue < 0 || abs(v - w->lastValue) >= ANALOG_THRESHOLD)
      : (v != w->lastValue);
    if (changed) {
      w->lastValue = v;
      report(w->pin, v);
    }
  }
}

// -------------------------------------------------------------------- bucle

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < MAX_SERVOS; i++) servos[i].pin = -1;
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      handleLine();
    } else if (lineLen < (int)sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    } else {
      lineLen = 0;  // línea demasiado larga: descartar
    }
  }
  runWatchers();
}
