#!/usr/bin/env python3
"""
USCF tournament sequence finder: Python fetches, HTML finds.

Run:   python app.py            then open http://localhost:8000
Needs: Python 3.8+, no extra packages, internet access.

The page asks this server for tournament histories by USCF ID
(/api/history?ids=12743305,12345678). The server calls the public USCF
ratings API and returns rows in the player,uscf_id,tournament,date format
the page already understands.

Command line use (writes a CSV you can also load into the page):
    python app.py --ids 12743305 12345678 --out history.csv

NOTE: the USCF endpoint and field names below are the ones the current
ratings site uses as far as I know. Adjust API_BASE / pick_* if USCF changes
its API.
"""
import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_BASE = "https://ratings-api.uschess.org/api/v1"
PAGE_SIZE = 100
HERE = os.path.dirname(os.path.abspath(__file__))
HEADERS = {"User-Agent": "tournament-sequence-finder/1.0", "Accept": "application/json"}


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def pick(d, *keys):
    for k in keys:
        if isinstance(d, dict) and d.get(k):
            return str(d[k]).strip()
    return ""


def player_name(uscf_id):
    try:
        m = get_json(f"{API_BASE}/members/{uscf_id}")
    except Exception:
        return str(uscf_id)
    first = pick(m, "firstName", "first_name")
    last = pick(m, "lastName", "last_name")
    full = f"{first} {last}".strip()
    return full or pick(m, "name") or str(uscf_id)


def events_for(uscf_id):
    """All rated events for one member, as (name, date) pairs."""
    out, offset = [], 0
    while True:
        qs = urllib.parse.urlencode({"Offset": offset, "Size": PAGE_SIZE})
        data = get_json(f"{API_BASE}/members/{uscf_id}/events?{qs}")
        items = data if isinstance(data, list) else (data.get("items") or data.get("events") or [])
        for it in items:
            ev = it.get("event", it) if isinstance(it, dict) else {}
            name = pick(ev, "name", "eventName", "event_name") or pick(it, "name", "eventName")
            date = (pick(ev, "endDate", "end_date", "startDate", "start_date", "date")
                    or pick(it, "endDate", "startDate", "date"))[:10]
            if name:
                out.append((name, date))
        if len(items) < PAGE_SIZE:
            return out
        offset += PAGE_SIZE
        time.sleep(0.2)  # be polite to USCF


def history_rows(ids):
    rows, errors = [], {}
    for uid in ids:
        try:
            name = player_name(uid)
            for ev_name, date in events_for(uid):
                rows.append({"player": name, "uscf_id": uid, "tournament": ev_name, "date": date})
        except urllib.error.HTTPError as e:
            errors[uid] = f"USCF returned HTTP {e.code}"
        except Exception as e:  # network, JSON, etc.
            errors[uid] = str(e)
    return rows, errors


def rows_to_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["player", "uscf_id", "tournament", "date"])
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def clean_ids(raw):
    ids = []
    for part in raw.replace(",", " ").split():
        digits = "".join(c for c in part if c.isdigit())
        if digits and digits not in ids:
            ids.append(digits)
    return ids[:50]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if url.path == "/api/history":
            ids = clean_ids(urllib.parse.parse_qs(url.query).get("ids", [""])[0])
            if not ids:
                return self._send(400, json.dumps({"error": "Give at least one USCF ID."}), "application/json")
            rows, errors = history_rows(ids)
            return self._send(200, json.dumps({"csv": rows_to_csv(rows), "errors": errors, "rows": len(rows)}),
                              "application/json")
        self._send(404, "Not found", "text/plain")

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", nargs="+", help="USCF IDs; fetch and write CSV instead of starting the server")
    ap.add_argument("--out", default="history.csv")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    if args.ids:
        rows, errors = history_rows(clean_ids(" ".join(args.ids)))
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            f.write(rows_to_csv(rows))
        print(f"Wrote {len(rows)} rows to {args.out}")
        for uid, msg in errors.items():
            print(f"  {uid}: {msg}", file=sys.stderr)
        return

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Open http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
