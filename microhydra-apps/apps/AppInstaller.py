"""AppInstaller - installs / updates the apps from szuszjan's microhydra-apps over Wi-Fi.

Uses the Wi-Fi network set in MicroHydra's Settings app.
Downloads apps/index.json from GitHub, lets you pick apps, and saves them to /apps.

Keys:
  ; .        move
  SPC        select / unselect
  a          select all
  ENT        install selected (or the highlighted one if none selected)
  ESC / G0   exit
"""

import json
import os
import time

import machine
import network
import requests
from lib import display, userinput
from lib.hydra import config


_REPO = const("https://raw.githubusercontent.com/szuszjan/szuszjan.github.io/")
_PATH = const("/microhydra-apps/apps/")
# tried in order; the first one that has index.json is used
BRANCHES = ("main", "ccr-7347e944-2ijb9a")
_APPS_DIR = const("/apps/")

_W = const(240)
_H = const(135)

# tiny 4-bit framebuffer: leaves enough RAM for HTTPS (palette colors only!)
DISPLAY = display.Display(use_tiny_buf=True)
CONFIG = config.Config()
INPUT = userinput.UserInput()
NIC = network.WLAN(network.STA_IF)

P = CONFIG.palette
BG, BG_DARK, MID, FG, WHITE, RED, GREEN = P[2], P[1], P[5], P[8], P[10], P[11], P[12]

LOG = []


def log(text, color=None):
    """Simple scrolling text log (used while connecting / downloading)."""
    LOG.append((text, FG if color is None else color))
    while len(LOG) > 12:
        LOG.pop(0)
    DISPLAY.fill(BG)
    DISPLAY.rect(0, 0, _W, 12, BG_DARK, fill=True)
    DISPLAY.text("App Installer", 4, 2, FG)
    y = 16
    for t, c in LOG:
        DISPLAY.text(t[:30], 0, y, c)
        y += 9
    DISPLAY.show()


def wait_key(msg="ENT = continue"):
    log(msg, MID)
    time.sleep_ms(300)
    INPUT.get_new_keys()
    while True:
        keys = INPUT.get_new_keys()
        if keys:
            return keys
        time.sleep_ms(20)


def connect_wifi():
    if not CONFIG["wifi_ssid"]:
        log("Wi-Fi is not set up!", RED)
        log("Open Settings -> wifi_ssid")
        log("and wifi_pass, then retry.")
        wait_key("any key = exit")
        machine.reset()
    log("Wi-Fi: " + CONFIG["wifi_ssid"])
    NIC.active(True)
    if not NIC.isconnected():
        try:
            NIC.connect(CONFIG["wifi_ssid"], CONFIG["wifi_pass"])
        except OSError as e:
            log("connect error: %s" % e, RED)
        for i in range(40):
            if NIC.isconnected():
                break
            if i % 4 == 0:
                log("connecting... %ds" % (i // 2))
            time.sleep_ms(500)
    if not NIC.isconnected():
        log("Could not connect :(", RED)
        wait_key("any key = exit")
        machine.reset()
    log("connected!", GREEN)


def get(url):
    return requests.get(url, headers={"User-Agent": "MicroHydra-AppInstaller"})


def fetch_index():
    for branch in BRANCHES:
        log("index from '%s'..." % branch)
        try:
            r = get(_REPO + branch + _PATH + "index.json")
            if r.status_code == 200:
                apps = json.loads(r.text)
                r.close()
                return branch, apps
            r.close()
            log("  HTTP %d" % r.status_code, MID)
        except Exception as e:  # noqa: BLE001
            log("  error: %s" % e, RED)
    return None, None


def download(branch, filename):
    """Stream a file to /apps (via a temp file, so a failed download keeps the old app)."""
    tmp = _APPS_DIR + filename + ".part"
    dest = _APPS_DIR + filename
    if "/" in filename:  # app folder
        try:
            os.mkdir(_APPS_DIR + filename.split("/")[0])
        except OSError:
            pass
    r = get(_REPO + branch + _PATH + filename)
    if r.status_code != 200:
        r.close()
        raise OSError("HTTP %d" % r.status_code)
    size = 0
    with open(tmp, "wb") as f:
        while True:
            chunk = r.raw.read(1024)
            if not chunk:
                break
            f.write(chunk)
            size += len(chunk)
    r.close()
    try:
        os.remove(dest)
    except OSError:
        pass
    os.rename(tmp, dest)
    return size


def installed():
    try:
        return set(os.listdir(_APPS_DIR))
    except OSError:
        os.mkdir(_APPS_DIR.rstrip("/"))
        return set()


def choose(apps):
    """App list with checkboxes. Returns list of selected app dicts, or None."""
    have = installed()
    sel = 0
    chosen = set()
    rows = 9
    while True:
        keys = INPUT.get_new_keys()
        if "ESC" in keys or "G0" in keys:
            return None
        for k in keys:
            if k in ("UP", ";"):
                sel = (sel - 1) % len(apps)
            elif k in ("DOWN", "."):
                sel = (sel + 1) % len(apps)
            elif k == "SPC":
                if sel in chosen:
                    chosen.remove(sel)
                else:
                    chosen.add(sel)
            elif k == "a":
                chosen = set() if len(chosen) == len(apps) else set(range(len(apps)))
            elif k == "ENT":
                return [apps[i] for i in sorted(chosen or {sel})]

        DISPLAY.fill(BG)
        DISPLAY.rect(0, 0, _W, 12, BG_DARK, fill=True)
        DISPLAY.text("Pick apps", 4, 2, FG)
        DISPLAY.text("SPC sel  ENT install", 76, 2, MID)
        first = min(max(0, sel - rows // 2), max(0, len(apps) - rows))
        for r in range(min(rows, len(apps))):
            i = first + r
            app = apps[i]
            y = 15 + r * 11
            if i == sel:
                DISPLAY.rect(0, y - 2, _W, 11, BG_DARK, fill=True)
            box = "[x]" if i in chosen else "[ ]"
            DISPLAY.text(box, 2, y, WHITE if i in chosen else MID)
            DISPLAY.text(app["name"], 30, y, FG if i == sel else WHITE)
            if app.get("dir", app.get("file")) in have:
                DISPLAY.text("installed", _W - 74, y, GREEN)
        desc = apps[sel].get("desc", "")
        DISPLAY.hline(0, _H - 20, _W, MID)
        DISPLAY.text(desc[:30], 0, _H - 17, MID)
        DISPLAY.text(desc[30:60], 0, _H - 8, MID)
        DISPLAY.show()
        time.sleep_ms(20)


def main():
    log("Starting...")
    connect_wifi()
    branch, apps = fetch_index()
    if not apps:
        log("Could not get the app list.", RED)
        wait_key("any key = exit")
        machine.reset()
    while True:
        picked = choose(apps)
        if picked is None:
            machine.reset()
        LOG.clear()
        ok = 0
        for app in picked:
            log("%s..." % app["name"])
            try:
                if "dir" in app:
                    size = 0
                    for f in app["files"]:
                        size += download(branch, app["dir"] + "/" + f)
                else:
                    size = download(branch, app["file"])
                log("  ok, %d bytes" % size, GREEN)
                ok += 1
            except Exception as e:  # noqa: BLE001
                log("  failed: %s" % e, RED)
        log("Installed %d/%d." % (ok, len(picked)), GREEN if ok == len(picked) else RED)
        keys = wait_key("ENT=launcher  other=back")
        if "ENT" in keys:
            machine.reset()


main()
