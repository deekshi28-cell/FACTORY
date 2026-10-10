"""
offline_check.py  -  KPI A10: "Works offline. Run the whole demo with the internet turned off.
                      Pass = zero outside calls."

Run from the project root (venv active, Ollama running):
    python Scripts\offline_check.py

What it does
  1. Installs a network guard: any connection or DNS lookup to a host that is NOT this
     computer (localhost / 127.x / ::1) is BLOCKED and recorded. So this test proves
     "zero outside calls" even if Wi-Fi is on. (Do the real Wi-Fi-off run as well.)
  2. Starts the whole system (embedding model, ChromaDB, Ollama) and asks English,
     Japanese, table and picture questions through the real web endpoint (/api/ask),
     then loads the returned picture through /api/image.
  3. Checks the web page files contain no external links (fonts, CDNs, scripts).
  4. Prints PASS / FAIL, the list of any blocked outside calls, and saves a report to
     Results\offline_check_report.txt that you can attach to the final report.
"""
import ipaddress
import os
import re
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402

# ---- 1. network guard ------------------------------------------------------------------
BLOCKED = []
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_getaddrinfo = socket.getaddrinfo


def _is_local(host):
    if host is None:
        return True
    host = str(host).strip("[]").lower()
    if host in ("localhost", "localhost.localdomain", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # a real hostname such as huggingface.co


def _record(kind, target):
    BLOCKED.append(f"{kind}: {target}")
    print(f"  !! BLOCKED outside call -> {kind} {target}")


def install_guard():
    def connect(self, address):
        host = address[0] if isinstance(address, (tuple, list)) else address
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_local(host):
            _record("connect", address)
            raise OSError(f"offline_check: outside connection blocked ({address})")
        return _real_connect(self, address)

    def connect_ex(self, address):
        host = address[0] if isinstance(address, (tuple, list)) else address
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _is_local(host):
            _record("connect_ex", address)
            return 111
        return _real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_local(host):
            _record("dns lookup", host)
            raise socket.gaierror(f"offline_check: outside lookup blocked ({host})")
        return _real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo


# ---- 3. static files: no external links ------------------------------------------------
def external_links_in_web_files():
    found = []
    app_dir = os.path.join(config.BASE_DIR, "app")
    for folder in ("templates", "static"):
        root = os.path.join(app_dir, folder)
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.lower().endswith((".html", ".css", ".js")):
                    continue
                path = os.path.join(dirpath, fn)
                text = open(path, encoding="utf-8", errors="ignore").read()
                for m in re.finditer(r"""(?:https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s"')>]*""", text):
                    url = m.group(0)
                    if re.search(r"localhost|127\.0\.0\.1|w3\.org", url):
                        continue
                    found.append(f"{os.path.relpath(path, app_dir)}: {url}")
    return found


QUESTIONS = [
    ("English text",  "What causes an E-09 ground fault?"),
    ("Japanese text", "E-01フォルトコードの意味は何ですか？"),
    ("English table", "What should I do for an E-04 overvoltage fault?"),
    ("Picture",       "What does the image of the UC100 controller show?"),
    ("Not found",     "What is the recommended dosage for ibuprofen?"),
]


def main():
    lines = []

    def say(msg=""):
        print(msg)
        lines.append(msg)

    install_guard()
    say("KPI A10 - offline check")
    say(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    say("Network guard ON: any non-local connection or DNS lookup is blocked and recorded.\n")

    import app as webapp  # imports search/retrieval/llm_client; loads nothing yet
    t0 = time.time()
    try:
        warm = webapp.search.init()
    except Exception as e:
        say(f"FAIL  startup error: {e}")
        say("      (If it says the embedding model is not cached: run once WITH internet using")
        say("       set FACTORY_ALLOW_MODEL_DOWNLOAD=1, then run this check again.)")
        return finish(lines, False)
    say(f"Startup OK ({time.time() - t0:.0f}s)\n")

    client = webapp.app.test_client()
    all_ok = True
    image_checked = False
    for label, q in QUESTIONS:
        t1 = time.time()
        try:
            resp = client.post("/api/ask", json={"question": q})
            data = resp.get_json() or {}
            ok = resp.status_code == 200 and bool((data.get("answer") or "").strip())
        except Exception as e:
            data, ok = {}, False
            say(f"  exception: {e}")
        say(f"[{'OK ' if ok else 'FAIL'}] {label:14} ({time.time() - t1:.0f}s) {q}")
        say("       answer : " + (data.get("answer", "")[:160].replace("\n", " ")))
        say("       sources: " + ", ".join(data.get("sources", [])[:3]))
        for url in data.get("image_urls", []):
            r = client.get(url)
            img_ok = r.status_code == 200 and r.mimetype.startswith("image/")
            say(f"       picture: {url} -> {'loaded OK' if img_ok else 'FAILED to load'}")
            image_checked = True
            ok = ok and img_ok
        all_ok = all_ok and ok
    if not image_checked:
        say("\nNOTE: no picture was returned for any question - open the web page and check a picture "
            "question by eye before you claim the picture part of the demo.")

    ext = external_links_in_web_files()
    say("\nExternal links in web page files: " + ("none" if not ext else ""))
    for e in ext:
        say("   " + e)
    all_ok = all_ok and not ext

    return finish(lines, all_ok)


def finish(lines, all_ok):
    passed = all_ok and not BLOCKED
    lines.append("")
    lines.append(f"Blocked outside calls: {len(BLOCKED)}")
    for b in BLOCKED:
        lines.append("   " + b)
    lines.append("RESULT: " + ("PASS - zero outside calls, all questions answered"
                               if passed else "FAIL - see messages above"))
    print("\n" + "\n".join(lines[-(len(BLOCKED) + 3):]))
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    out = os.path.join(config.RESULTS_DIR, "offline_check_report.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Report saved: {out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())