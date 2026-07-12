"""
WiFi Signal Meter - Raspberry Pi Pico 2 W + Pimoroni Pico Display Pack 2.8"

A stateless 2.4 GHz WiFi signal-strength meter in MicroPython.

Two modes:
  A - AP List:  each network's SSID + RSSI with a color-coded strength bar.
  B - Activity: single aggregate "how busy is 2.4 GHz" reading (linear power sum).

Buttons (A/B/X/Y = GPIO 12/13/14/15):
  A - scroll up (Mode A)
  B - scroll down (Mode A)
  X - switch mode A <-> B
  Y - manual rescan

Scope note: this uses the CYW43439's WiFi scan (RSSI of visible APs). It is not
SDR and not monitor-mode sniffing. "Activity" means aggregate AP signal presence,
not channel airtime/utilization - the scan does not expose CCA/channel-busy data.

Firmware: requires the Pimoroni pico2_w MicroPython build (RP2350 repo), which
bundles PicoGraphics AND the WiFi stack. See README.
"""

import network, time, math
from machine import Pin
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY_2

# ---- tunables ----
SCAN_INTERVAL = 5000     # ms between auto-rescans
FLOOR = -95              # Mode B: bar empty at/below this dBm  (calibrate to your space)
CEIL  = -35              # Mode B: bar full at/above this dBm   (calibrate to your space)
ROWS_VISIBLE = 8         # Mode A: AP rows on screen at once

# ---- display ----
display = PicoGraphics(display=DISPLAY_PICO_DISPLAY_2)
display.set_backlight(0.8)
WIDTH, HEIGHT = display.get_bounds()   # 320 x 240

BLACK = display.create_pen(0, 0, 0)
WHITE = display.create_pen(255, 255, 255)
GREEN = display.create_pen(0, 255, 0)
YELLOW = display.create_pen(255, 200, 0)
RED = display.create_pen(255, 60, 60)
GREY = display.create_pen(90, 90, 90)

def rssi_pen(rssi):
    if rssi >= -55: return GREEN
    if rssi >= -70: return YELLOW
    return RED

# ---- buttons (A/B/X/Y = 12/13/14/15) ----
btn_a = Pin(12, Pin.IN, Pin.PULL_UP)
btn_b = Pin(13, Pin.IN, Pin.PULL_UP)
btn_x = Pin(14, Pin.IN, Pin.PULL_UP)
btn_y = Pin(15, Pin.IN, Pin.PULL_UP)
prev = {"a": 1, "b": 1, "x": 1, "y": 1}

def pressed(pin, key):
    """True once on the falling edge (press), not while held."""
    now = pin.value()
    fell = (prev[key] == 1 and now == 0)
    prev[key] = now
    return fell

# ---- wifi ----
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
time.sleep(1)

nets = []            # list of (ssid_str, rssi, channel)
def do_scan():
    global nets
    raw = wlan.scan()
    raw.sort(key=lambda n: n[3], reverse=True)
    nets = [(n[0].decode("utf-8", "replace") or "<hidden>", n[3], n[2]) for n in raw]

# ---- Mode B aggregate ----
def activity_dbm():
    if not nets: return None
    total_mw = sum(10 ** (r / 10) for (_, r, _) in nets)
    return 10 * math.log10(total_mw)

def bar(x, y, w, h, pct, pen):
    display.set_pen(GREY); display.rectangle(x, y, w, h)
    fill = int(w * pct / 100)
    display.set_pen(pen); display.rectangle(x, y, fill, h)

# ---- drawing ----
def draw_mode_a(scroll):
    display.set_pen(BLACK); display.clear()
    display.set_pen(GREEN)
    display.text("Mode A - AP List  ({})".format(len(nets)), 8, 6, WIDTH, 2)
    y = 34
    view = nets[scroll:scroll + ROWS_VISIBLE]
    if not view:
        display.set_pen(WHITE); display.text("scanning...", 8, y, WIDTH, 2)
    for (ssid, rssi, ch) in view:
        display.set_pen(WHITE)
        label = ssid if len(ssid) <= 16 else ssid[:15] + "~"
        display.text(label, 8, y, WIDTH, 2)
        display.set_pen(WHITE)
        display.text("{:>4}".format(rssi), 200, y, WIDTH, 2)
        pct = max(0, min(100, (rssi - FLOOR) / (CEIL - FLOOR) * 100))
        bar(244, y + 2, 68, 12, pct, rssi_pen(rssi))
        y += 24
    display.set_pen(GREY)
    display.text("A/B scroll  X mode  Y rescan", 8, 222, WIDTH, 1)
    display.update()

def draw_mode_b():
    display.set_pen(BLACK); display.clear()
    display.set_pen(GREEN)
    display.text("Mode B - 2.4GHz Activity", 8, 6, WIDTH, 2)
    agg = activity_dbm()
    if agg is None:
        display.set_pen(WHITE); display.text("nothing heard", 8, 90, WIDTH, 3)
    else:
        pct = max(0, min(100, (agg - FLOOR) / (CEIL - FLOOR) * 100))
        display.set_pen(WHITE)
        display.text("{:.0f}%".format(pct), 8, 60, WIDTH, 6)
        display.text("{:.1f} dBm  ({} APs)".format(agg, len(nets)), 8, 130, WIDTH, 2)
        pen = GREEN if pct < 40 else (YELLOW if pct < 75 else RED)
        bar(8, 165, WIDTH - 16, 30, pct, pen)
    display.set_pen(GREY)
    display.text("X mode  Y rescan", 8, 222, WIDTH, 1)
    display.update()

# ---- main loop ----
mode = "A"
scroll = 0
do_scan()
last_scan = time.ticks_ms()

def redraw():
    if mode == "A": draw_mode_a(scroll)
    else: draw_mode_b()

redraw()

while True:
    changed = False

    if pressed(btn_x, "x"):
        mode = "B" if mode == "A" else "A"
        scroll = 0
        changed = True

    if pressed(btn_y, "y"):
        do_scan()
        last_scan = time.ticks_ms()
        changed = True

    if mode == "A":
        if pressed(btn_a, "a") and scroll > 0:
            scroll -= 1; changed = True
        if pressed(btn_b, "b") and scroll + ROWS_VISIBLE < len(nets):
            scroll += 1; changed = True
    else:
        prev["a"] = btn_a.value()   # keep edge state fresh while unused
        prev["b"] = btn_b.value()

    if time.ticks_diff(time.ticks_ms(), last_scan) >= SCAN_INTERVAL:
        do_scan()
        last_scan = time.ticks_ms()
        if scroll + ROWS_VISIBLE > len(nets):
            scroll = max(0, len(nets) - ROWS_VISIBLE)
        changed = True

    if changed:
        redraw()
    time.sleep(0.05)
