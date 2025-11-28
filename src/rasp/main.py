# MicroPython — independent buttons sending serial.write() AND printing to Thonny
from machine import Pin, UART
import time

# ----- Serial UART -----
uart = UART(0, baudrate=115200)

def send(msg):
    text = msg + "\n"
    print(msg)            # shows in Thonny shell / USB CDC
    uart.write(text)      # sends to physical UART pins GP0 (TX) / GP1 (RX)

PIN_A = 21   # pino do botão A
PIN_B = 20   # pino do botão B

DEBOUNCE_MS = 25
HELD_PRINT_INTERVAL_MS = 200
POLL_MS = 10

def now_ms():
    return time.ticks_ms()

# ----- Botão simples -----
class SimpleButton:
    def __init__(self, name, pin_num):
        self.name = name
        self.pin = Pin(pin_num, Pin.IN, Pin.PULL_UP)
        self.last_raw = self.pin.value()
        self.last_change = now_ms()
        self.stable = self.last_raw
        self.pressed_time = None
        self.last_held_print = None

    def update(self, current_time):
        raw = self.pin.value()

        # raw changed → reset debounce timer
        if raw != self.last_raw:
            self.last_raw = raw
            self.last_change = current_time

        # stable state changed?
        if time.ticks_diff(current_time, self.last_change) >= DEBOUNCE_MS:
            if raw != self.stable:
                self.stable = raw
                if self.stable == 0:
                    # DOWN event
                    self.pressed_time = current_time
                    self.last_held_print = current_time
                    send("{} DOWN".format(self.name))
                else:
                    # UP event
                    if self.pressed_time is None:
                        dur = 0
                    else:
                        dur = time.ticks_diff(current_time, self.pressed_time)

                    send("{} UP".format(self.name))

                    # reset
                    self.pressed_time = None
                    self.last_held_print = None

        # HELD loop
        if self.stable == 0 and self.pressed_time is not None:
            if time.ticks_diff(current_time, self.last_held_print) >= HELD_PRINT_INTERVAL_MS:
                dur = time.ticks_diff(current_time, self.pressed_time)
                send("{} HELD".format(self.name))
                self.last_held_print = current_time

# ----- Inicializa botões -----
btnA = SimpleButton("A", PIN_A)
btnB = SimpleButton("B", PIN_B)

send("Started — monitoring A({}) and B({})".format(PIN_A, PIN_B))

# ----- Loop principal -----
try:
    while True:
        t = now_ms()
        btnA.update(t)
        btnB.update(t)
        time.sleep_ms(POLL_MS)
except KeyboardInterrupt:
    send("Stopped.")

