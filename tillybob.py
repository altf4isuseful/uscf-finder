#!/usr/bin/env python3
"""
Tillybob game server and fraction engine.

Run:  python3 tillybob.py            (then open http://localhost:8000)
      python3 tillybob.py --port 9000 --open

The browser game (index.html) asks this server for:
  GET  /api/ping                  -> {"engine": "python"}
  GET  /api/problem?tier=0..5     -> a fraction problem built with fractions.Fraction
  GET  /api/sequence?tier=0..5    -> a "put these in order" lock puzzle
  POST /api/scene   {kind, stats} -> a cutscene whose lines depend on the player's stats
  POST /api/ending  {stats}       -> the ending, chosen from the player's stats

If the server is not running, index.html falls back to a JavaScript copy of this
logic, so keep the two in sync when you change the rules.
Only the Python standard library is used.
"""
import argparse
import json
import random
import sys
import webbrowser
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from math import gcd
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Fraction helpers
# --------------------------------------------------------------------------

def fs(fr: Fraction) -> str:
    """Format a Fraction as 'n/d', or just 'n' when it is a whole number."""
    return str(fr.numerator) if fr.denominator == 1 else f"{fr.numerator}/{fr.denominator}"


def lcm(a: int, b: int) -> int:
    return a // gcd(a, b) * b


def simp_note(n: int, d: int) -> str:
    fr = Fraction(n, d)
    return f", which simplifies to {fs(fr)}" if fr.denominator != d else ""


def frac_choices(answer: Fraction, extras):
    """Return (choices, answer_str): the right answer plus 3 plausible wrong ones."""
    wrong = []

    def add(n, d):
        if n <= 0 or d <= 0:
            return
        f = Fraction(n, d)
        if f == answer:
            return
        s = fs(f)
        if s not in wrong:
            wrong.append(s)

    for n, d in extras:           # common mistakes first
        add(n, d)
    an, ad = answer.numerator, answer.denominator
    near = [(an + 1, ad), (an, ad + 1), (max(1, an - 1), ad), (an, max(1, ad - 1)),
            (an + 1, ad + 1), (an + 2, ad), (an, ad + 2), (an * 2 + 1, ad * 2)]
    random.shuffle(near)
    for n, d in near:
        add(n, d)
    k = 2
    while len(wrong) < 3 and k < 40:
        add(an + k, ad)
        add(an, ad + k)
        k += 1
    choices = [fs(answer)] + wrong[:3]
    random.shuffle(choices)
    return choices, fs(answer)


def int_choices(answer: int, extras):
    wrong = []
    for x in list(extras) + [answer + 1, answer - 1, answer + 2, answer - 2, answer + 3, answer * 2]:
        if x > 0 and x != answer and str(x) not in wrong:
            wrong.append(str(x))
    random.shuffle(wrong)
    choices = [str(answer)] + wrong[:3]
    random.shuffle(choices)
    return choices, str(answer)


# --------------------------------------------------------------------------
# Problem generators (one per kind)
# --------------------------------------------------------------------------

def add_same():
    d = random.randint(5, 12)
    a = random.randint(1, d - 3)
    b = random.randint(1, d - 1 - a)
    ans = Fraction(a + b, d)
    ch, an = frac_choices(ans, [(a + b, 2 * d)])
    return dict(kind="Add fractions", prompt=f"{a}/{d} + {b}/{d} = ?", choices=ch, answer=an,
                explain=f"Same denominator ({d}), so add the tops: {a} + {b} = {a + b}. "
                        f"That gives {a + b}/{d}{simp_note(a + b, d)}.")


def sub_same():
    d = random.randint(5, 12)
    a = random.randint(3, d - 1)
    b = random.randint(1, a - 1)
    ans = Fraction(a - b, d)
    ch, an = frac_choices(ans, [(a + b, d)])
    return dict(kind="Subtract fractions", prompt=f"{a}/{d} − {b}/{d} = ?", choices=ch, answer=an,
                explain=f"Same denominator ({d}), so subtract the tops: {a} − {b} = {a - b}. "
                        f"That gives {a - b}/{d}{simp_note(a - b, d)}.")


def simplify():
    while True:
        q = random.randint(2, 9)
        p = random.randint(1, q - 1)
        if gcd(p, q) == 1:
            break
    m = random.randint(2, 5)
    n, d = p * m, q * m
    ch, an = frac_choices(Fraction(p, q), [(n - m, d - m)])
    return dict(kind="Simplify", prompt=f"Simplify {n}/{d}", choices=ch, answer=an,
                explain=f"Divide the top and bottom by {m}: {n} ÷ {m} = {p} and {d} ÷ {m} = {q}. "
                        f"So {n}/{d} = {p}/{q}.")


def of_number():
    q = random.randint(2, 6)
    p = random.randint(1, q - 1)
    k = random.randint(2, 6)
    w = q * k
    ans = p * k
    ch, an = int_choices(ans, [k, w - ans, p * w])
    return dict(kind="Fraction of a number", prompt=f"{p}/{q} of {w} = ?", choices=ch, answer=an,
                explain=f"Split {w} into {q} equal parts: {w} ÷ {q} = {k}. "
                        f"Take {p} of them: {p} × {k} = {ans}.")


def add_unlike():
    d1, d2 = random.choice([(2, 3), (2, 4), (3, 4), (3, 6), (2, 6), (4, 6), (2, 5), (4, 8), (3, 5), (2, 8)])
    a, b = random.randint(1, d1 - 1), random.randint(1, d2 - 1)
    L = lcm(d1, d2)
    top = a * (L // d1) + b * (L // d2)
    ch, an = frac_choices(Fraction(top, L), [(a + b, d1 + d2)])
    return dict(kind="Unlike denominators", prompt=f"{a}/{d1} + {b}/{d2} = ?", choices=ch, answer=an,
                explain=f"Common denominator {L}: {a}/{d1} = {a * L // d1}/{L} and {b}/{d2} = {b * L // d2}/{L}. "
                        f"Add the tops: {top}/{L}{simp_note(top, L)}.")


def sub_unlike():
    while True:
        d1, d2 = random.choice([(2, 3), (3, 4), (3, 6), (2, 4), (4, 6), (2, 5), (3, 5), (4, 8)])
        if random.random() < 0.5:
            d1, d2 = d2, d1
        a, b = random.randint(1, d1 - 1), random.randint(1, d2 - 1)
        L = lcm(d1, d2)
        top = a * (L // d1) - b * (L // d2)
        if top > 0:
            break
    ch, an = frac_choices(Fraction(top, L), [(abs(a - b) or 1, abs(d1 - d2) or 1)])
    return dict(kind="Unlike denominators", prompt=f"{a}/{d1} − {b}/{d2} = ?", choices=ch, answer=an,
                explain=f"Common denominator {L}: {a}/{d1} = {a * L // d1}/{L} and {b}/{d2} = {b * L // d2}/{L}. "
                        f"Subtract the tops: {top}/{L}{simp_note(top, L)}.")


def multiply():
    a = random.randint(1, 4)
    b = random.randint(a + 1, 8)
    c = random.randint(1, 4)
    d = random.randint(c + 1, 8)
    ch, an = frac_choices(Fraction(a * c, b * d), [(a + c, b + d)])
    return dict(kind="Multiply fractions", prompt=f"{a}/{b} × {c}/{d} = ?", choices=ch, answer=an,
                explain=f"Multiply the tops ({a} × {c} = {a * c}) and the bottoms ({b} × {d} = {b * d}): "
                        f"{a * c}/{b * d}{simp_note(a * c, b * d)}.")


def compare():
    fr = []
    for _ in range(300):
        if len(fr) == 4:
            break
        d = random.randint(2, 9)
        n = random.randint(1, d - 1)
        v = n / d
        if all(abs(v - o[2]) > 0.03 for o in fr):
            fr.append((n, d, v))
    best = max(fr, key=lambda t: t[2])
    names = [f"{n}/{d}" for n, d, _ in fr]
    random.shuffle(names)
    dec = ", ".join(f"{n}/{d} = {v:.2f}" for n, d, v in fr)
    return dict(kind="Compare", prompt="Which fraction is the largest?", choices=names, answer=f"{best[0]}/{best[1]}",
                explain=f"As decimals: {dec}. The largest is {best[0]}/{best[1]}.")


MAKERS = dict(add_same=add_same, sub_same=sub_same, simplify=simplify, of_number=of_number,
              add_unlike=add_unlike, sub_unlike=sub_unlike, multiply=multiply, compare=compare)
TIERS = [
    ["add_same", "sub_same", "simplify"],
    ["add_same", "sub_same", "simplify", "of_number"],
    ["add_unlike", "of_number", "simplify"],
    ["add_unlike", "multiply", "compare", "of_number"],
    ["add_unlike", "sub_unlike", "multiply", "compare"],
    ["add_unlike", "sub_unlike", "multiply", "compare", "of_number", "simplify"],
]


def problem(tier: int) -> dict:
    tier = max(0, min(5, tier))
    return MAKERS[random.choice(TIERS[tier])]()


def sequence(tier: int) -> dict:
    """A lock puzzle: tap the fractions from smallest to greatest."""
    n = 3 if tier < 3 else 4
    items = []
    for _ in range(300):
        if len(items) == n:
            break
        d = random.choice([2, 3, 4, 5, 6, 8, 10])
        nu = random.randint(1, d - 1)
        f = Fraction(nu, d)
        if all(abs(float(f) - float(o)) > 0.04 for o in items):
            items.append(f)
    shown = items[:]
    random.shuffle(shown)
    order = [shown.index(f) for f in sorted(shown)]
    explain = "  <  ".join(f"{f.numerator}/{f.denominator} = {float(f):.2f}" for f in sorted(shown))
    return dict(items=[f"{f.numerator}/{f.denominator}" for f in shown], order=order, explain=explain)


# --------------------------------------------------------------------------
# Cutscene and ending logic: the story changes with the player's stats
# --------------------------------------------------------------------------

def scene(kind: str, st: dict) -> dict:
    joy = st.get("joy", 0)
    if kind == "meeting":
        if joy >= 60:
            return dict(variant="joyful", lines=[
                ["Mira", "Look at this place. Walls, a fire, laughter. It feels like home again."],
                ["Odo", "We should give it a name. Tillyville."],
                ["Tillybob", "Every block you all placed made it real."]])
        if joy < 40:
            return dict(variant="tense", lines=[
                ["Odo", "Folks are tired. Too few roofs, too little bread."],
                ["Mira", "People have to feel safe before they feel brave."],
                ["Tillybob", "Then I build shelters first, and share the loaf."]])
        return dict(variant="neutral", lines=[
            ["Pip", "Everyone is here! Even Moss brought his drum."],
            ["Tillybob", "A good start. Keep building, keep counting."]])
    if kind == "camp_win":
        if st.get("campTeam", 0) * 2 >= st.get("campKills", 1):
            return dict(variant="together", lines=[
                ["Freed villagers", "You came with a squad. We watched you crack those cages together!"],
                ["Tillybob", "Maths is a team sport."]])
        return dict(variant="solo", lines=[
            ["Freed villagers", "You came alone? Next time let us stand beside you."],
            ["Tillybob", "Noted. Rally with G, and the cages get easier."]])
    if kind == "night_before":
        vill = st.get("villagers", 0)
        if vill >= 6 and joy >= 60:
            return dict(variant="vigil", gift=4, lines=[
                ["Narrator", "The whole settlement gathers around the fire. Someone hums."],
                ["Mira", "Take this bread. And take our thanks."],
                ["Tillybob", "I am not walking in alone, then."]])
        if vill < 4 or joy < 35:
            return dict(variant="alone", gift=0, lines=[
                ["Narrator", "The fire is small. Few people look up as you pass."],
                ["Tillybob", "If I lose, nobody here can stop him."],
                ["Tillybob", "Then I just will not lose."]])
        return dict(variant="quiet", gift=2, lines=[
            ["Narrator", "A few villagers wave from their doorways."],
            ["Pip", "Be careful. He has your face."],
            ["Tillybob", "That is why I know his steps."]])
    return dict(variant="none", lines=[])


def ending(st: dict) -> dict:
    joy, vill = st.get("joy", 0), st.get("villagers", 0)
    if joy >= 75 and vill >= 8:
        r = dict(tag="tillyville", title="Tillyville Rises", lines=[
            "Smoke from a hundred small hearths curls into the evening.",
            "The villagers carry you on their shoulders to the new square.",
            "Pip names the town after you. You pretend to object."])
    elif st.get("accuracy", 0) >= 92 and st.get("solved", 0) >= 12:
        r = dict(tag="scholar", title="Perfect Denominators", lines=[
            "Every cage broke on the first try, and the villagers noticed.",
            "Pip pins your best worked solution to the village wall.",
            "A school grows up around it."])
    elif st.get("blocks", 0) >= 50:
        r = dict(tag="architect", title="The Builder’s Hill", lines=[
            "You turn the ruined clearing into terraces and towers.",
            "Travellers come from far away to see what blocks can do.",
            "You are asked to design a bridge."])
    elif joy < 35:
        r = dict(tag="lonely", title="Quiet Victor", lines=[
            "The lava hisses, then goes still.",
            "Few villagers cheer. They are tired, and not yet sure of you.",
            "You walk home slowly, thinking about roofs and bread."])
    else:
        r = dict(tag="hero", title="Hero of Web Hollow", lines=[
            "The lava settles and the arena goes quiet.",
            "Pip runs across the sand and hugs your leg.",
            "The spider cages stay dark. The fractions stay solved."])
    extra = []
    if st.get("zombified", 0) > 0:
        extra.append("A faint green tint lingers in your fingertips.")
    deaths = st.get("deaths", 0)
    if deaths > 0:
        extra.append(f"You fell {deaths} time{'s' if deaths > 1 else ''} on the way. "
                     "The villagers say that counts as practice.")
    r["extra"] = extra
    return r


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------

SKELETON_HEAD = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                 "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">"
                 "</head><body>")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode("utf-8"))

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        try:
            tier = int(q.get("tier", ["0"])[0])
        except ValueError:
            tier = 0
        if url.path == "/api/ping":
            return self._json({"engine": "python", "python": sys.version.split()[0]})
        if url.path == "/api/problem":
            return self._json(problem(tier))
        if url.path == "/api/sequence":
            return self._json(sequence(tier))
        if url.path in ("/", "/index.html"):
            page = (HERE / "index.html").read_text(encoding="utf-8")
            # index.html is written as a page fragment; add the document skeleton
            # so the browser does not use quirks mode.
            if not page.lstrip().lower().startswith("<!doctype"):
                page = SKELETON_HEAD + page + "</body></html>"
            return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "bad json"}, 400)
        path = urlparse(self.path).path
        if path == "/api/scene":
            return self._json(scene(str(data.get("kind", "")), data.get("stats", {}) or {}))
        if path == "/api/ending":
            return self._json(ending(data.get("stats", {}) or {}))
        return self._json({"error": "unknown route"}, 404)

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet


def main():
    ap = argparse.ArgumentParser(description="Tillybob game server")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="open the game in your browser")
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"Tillybob is running at {url}  (Ctrl+C to stop)")
    if args.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
