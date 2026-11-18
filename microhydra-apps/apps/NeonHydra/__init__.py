"""NEON HYDRA - an old school demo for MicroHydra (M5Stack Cardputer).

~3 minutes of raster bars, sine scrollers, plasma, vector balls, tunnel,
twister, rotozoomer and fire, with an original 4 channel chiptune
synthesized live.

Keys: SPC next part, ; . volume, f FPS + free memory, ESC / G0 exit.
Install: copy the whole NeonHydra folder into /apps (flash or SD card).

This file is deliberately tiny: it starts the debug log first, so even an
error while loading the big modules ends up in neonhydra_log.txt.
"""

import gc

try:
    from . import nhlog
except ImportError:
    from apps.NeonHydra import nhlog

nhlog.reset_log()
nhlog.log("bootstrap")

try:
    try:
        from . import demo  # noqa: F401  (runs the demo)
    except ImportError as e:
        if "demo" not in str(e) and "NeonHydra" not in str(e):
            raise
        from apps.NeonHydra import demo  # noqa: F401
except Exception as err:  # noqa: BLE001
    nhlog.log("FATAL while loading the demo", err)
    try:
        import time

        from lib.display import Display
        gc.collect()
        d = Display(use_tiny_buf=True)
        pal = d.palette  # tiny buffer: colors are palette entries
        d.fill(pal[0])
        d.text("NEON HYDRA failed:", 4, 10, pal[8])
        msg = repr(err)
        for i in range(6):
            d.text(msg[i * 29:(i + 1) * 29], 4, 30 + i * 12, pal[10])
        d.text("details: neonhydra_log.txt", 4, 110, pal[5])
        d.show()
        time.sleep(6)
    except Exception:  # noqa: BLE001
        pass
    raise
