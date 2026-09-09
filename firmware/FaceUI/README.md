# FaceUI: working landscape touch and iPhone-inspired UI

The owner confirmed that touches were working well on 9 September 2026.
Commit `4d7d2cd` preserves that touch implementation before the UI polish.
See `../TOUCH_PINTRACE_RESULTS.md` for the measurements, previous failures,
and limits of the experimental resistance-ratio method.

## Preserve the working calibration

- Physical wiring and landscape orientation are unchanged.
- Measured electrode pairs: GPIO16/33 and GPIO17/21.
- Calibration version 13, NVS namespace `freeisp`, keys `vcal_ver` and `anch6`.
- UI changes retain the sampling routine and calibration keys. Do not erase
  flash or increment the calibration version for cosmetic changes.
- `nvs-working-v13.bin` is a local, ignored 20,480-byte backup of the NVS
  partition at `0x9000`, captured before uploading the UI polish. It belongs
  to this board and is not a universal calibration or a file to publish.

The polished UI centres each Settings card in its corresponding calibration
band, adds navigation arrows and clearer pressed feedback, and replaces
GPIO/debug details with a readable About screen. Dashboard figures are
explicitly labelled sample data. WiFi remains a placeholder; screen and alarm
presets are saved locally and are not connected to hardware controls here.

The subsequent front-screen redesign uses a light grouped background, rounded
white cards, blue actions, green port indicators and proportional FreeSans
bitmap fonts. Settings and About use the same typography and colour system.
Font masks are rendered in RAM and sent as horizontal spans to avoid the
LCD driver's costly per-pixel window writes. Touch sampling is unchanged
from working commit `f9ae322`; calibration remains version 13.

`home-preview.png` is a desktop layout preview, not a device photograph.
`Preview.ps1` regenerates it using the installed Adafruit font bitmaps;
its font path can be adjusted for a different workstation.

## Build and upload

```powershell
& 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' compile --upload -p COM6 --fqbn esp32:esp32:esp32 firmware/FaceUI
```

Do not use `--output-dir`. Retry once for an intermittent upload failure.

The latest redesign compiled on Arduino-ESP32 3.3.10 (371,640 bytes program,
25,884 bytes globals), uploaded to COM6, and passed the flasher's hash
verification. The normal UI loop reported idle contact after reboot, without
entering first-boot calibration. Physical visual acceptance of the new UI
is still for the owner to confirm; the earlier touch confirmation applies
to the preserved touch implementation.
