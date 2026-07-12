# WiFi Signal Meter

A stateless 2.4 GHz WiFi signal-strength meter on a Raspberry Pi Pico 2 W with a Pimoroni Pico Display Pack 2.8", written in MicroPython. Walk around, watch the signal rise near routers.

Built as a compact, handheld RF-awareness tool and as a hands-on exercise in the RSSI-and-scanning fundamentals that underpin larger wireless projects (wardriving, RF activity mapping).

## Scope (what it is, and honestly what it isn't)

This uses the onboard CYW43439's **WiFi scan** to read the RSSI of visible access points. That is the honest boundary of the hardware:

- **It is:** a passive listing of nearby APs with signal strength, and an aggregate "how much AP energy is in the air" reading.
- **It is not** an SDR, and it is not monitor-mode packet sniffing. Those are separate tools with separate hardware.
- **"Activity" means aggregate AP signal presence, not channel airtime.** A loud beacon with zero traffic reads the same as a saturated link — the scan API does not expose CCA / channel-busy data. The meter sees *power*, not *occupancy*. (This is the same limitation an analog RF log-amp has: it integrates power in a band, it doesn't measure utilization.)

Scoping it to what the chip can actually do is the point, not a shortcoming.

## Hardware

- Raspberry Pi Pico 2 W (RP2350, onboard CYW43439 WiFi)
- Pimoroni Pico Display Pack 2.8" (320×240 IPS, 4 buttons, ST7789)

No wiring — the Display Pack seats directly on the Pico's headers.

## Features

**Mode A — AP List.** Scans and lists each network's SSID and RSSI, sorted strongest-first, each with a color-coded strength bar (green ≥ -55 dBm, yellow ≥ -70, red below). Scrolls when more than 8 networks are visible.

**Mode B — 2.4 GHz Activity Meter.** Aggregates everything heard into a single percentage + aggregate dBm reading with a bar. Rises for both proximity (near a strong AP) and congestion (many APs). Walk toward a router and watch it climb.

**Behavior.** Auto-rescans on a timer (default 5 s) in both modes so it feels live. Boots straight into Mode A scanning — instant-on. **Stateless: no SD logging**, so hard power-cycling is always safe and no power button is needed.

**Buttons** (A/B/X/Y):

| Button | GPIO | Action |
|--------|------|--------|
| A | 12 | Scroll up (Mode A) |
| B | 13 | Scroll down (Mode A) |
| X | 14 | Switch mode A ↔ B |
| Y | 15 | Manual rescan |

## How the Activity meter aggregates

Mode B converts each AP's dBm back to linear power (mW), sums them, and converts back to dBm — a **linear power sum**:

```
total_mW = sum(10 ** (rssi_dBm / 10) for each AP)
aggregate_dBm = 10 * log10(total_mW)
```

This is more physically honest than peak-RSSI or a threshold count: it rises for proximity *and* for congestion. In a sparse environment where one AP dominates, the sum is essentially that AP (log scale — the strongest signal carries the vast majority of the total power). In a dense environment (e.g. an apartment stack), ten comparable APs push the sum ~10 dB above any single peak, which peak-RSSI would miss entirely.

This is the software rehearsal for the analog power integration a log-amp does in an RF activity mapper.

## Firmware

This is the part worth getting exactly right. The Pico 2 W needs the **Pimoroni `pico2_w` MicroPython build**, which bundles both PicoGraphics (for the display) and the WiFi stack (for scanning). Stock micropython.org firmware has WiFi but **no PicoGraphics**; the plain `pico2` Pimoroni build has PicoGraphics but **no WiFi**.

1. Download the **`pico2_w`** asset (not `pico2`, not `pico_plus2_w`) from the Pimoroni RP2350 releases:
   <https://github.com/pimoroni/pimoroni-pico-rp2350/releases/latest>
2. Hold **BOOTSEL**, plug in USB, release when the `RP2350` drive mounts.
3. Copy the `.uf2` onto it (drag, or `cp pico2_w*.uf2 /media/<user>/RP2350/ && sync`). The drive disappears when done — that's success. On Linux the file manager may report a spurious write error as the board reboots mid-write; if the drive vanished, it worked.
4. Verify with `os.uname()`:

```python
import os; print(os.uname())
```

The **`machine=`** field must read `Raspberry Pi Pico 2 W with RP2350` — no "Plus," no "PSRAM." Trust `machine=`, not the version string (Pimoroni's version string is a shared branch name and can misreport the board).

Then confirm both halves:

```python
import picographics                      # no error = right build
import network, time
w = network.WLAN(network.STA_IF); w.active(True); time.sleep(1)
print("APs:", len(w.scan()))             # > 0 = WiFi working
```

### Recovery: "Could not write ... 0 bytes to /main.py"

That's a wedged littlefs filesystem, not a hardware fault. Reformat it in place (firmware untouched):

```python
import vfs, rp2
bdev = rp2.Flash()
vfs.umount("/")
vfs.VfsLfs2.mkfs(bdev, progsize=256)     # progsize=256 required on RP2350
vfs.mount(vfs.VfsLfs2(bdev, progsize=256), "/")
```

## Install

Copy `main.py` to the Pico (Thonny: *File → Save as → Raspberry Pi Pico*, name it `main.py` to auto-run on boot). Reset the board and it starts in Mode A.

## Calibration

Mode B's `FLOOR` and `CEIL` constants (top of `main.py`) set the empty/full endpoints of the bar. There is no universal "full" — only full-for-your-environment. To calibrate:

1. Stand in the deadest corner you have; note the Mode B percentage.
2. Stand next to your strongest router; note it there.
3. If the dead corner reads well above 0%, raise `FLOOR` toward that reading's dBm. If the router reads well below 100%, lower `CEIL` toward its dBm.

Defaults (`FLOOR = -95`, `CEIL = -35`) are a reasonable starting span.

## Roadmap

- **v2:** peak-hold on the Activity meter (retain the session-max reading).

## License

MIT — see [LICENSE](LICENSE).
