#!/usr/bin/env python3
"""Animated contribution snake: eats the graph, explodes, re-spreads the
contributions, one of them is blue and hatches the next snake. Loops forever.

usage: snake_gen.py contributions.json chain.json out.svg [--theme dark|light]
chain.json: head positions [[x, y], ...] computed by the snk solver
(snake_chain.ts) -- the snake follows the original snk route, eating the
darkest cells first and the brightest last.
contributions.json: output of the GraphQL contributionCalendar query
(either the raw `gh api graphql` response or just the `weeks` list).
"""
import json
import math
import random
import sys

PITCH, SIZE = 12, 10
PADL, PADR, PADT, PADB = 26, 60, 36, 30
TICK = 0.03          # seconds per cell travelled by the snake
SEG = 12             # snake segments
GROW = 4             # head cells travelled per new segment
BLUE = "#2F80FF"
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
THEMES = {
    "dark": {"empty": "#161b22", "lv": ["#01311f", "#034525", "#0f6d31", "#00c647"]},
    "light": {"empty": "#ebedf0", "lv": ["#9be9a8", "#40c463", "#30a14e", "#216e39"]},
}
EASE_OUT = "cubic-bezier(.12,.75,.25,1)"


def load(path):
    d = json.load(open(path))
    if "data" in d:
        d = d["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    elif "weeks" in d:
        d = d["weeks"]
    return d


def build_cells(weeks):
    cells = []
    for c, w in enumerate(weeks):
        for d in w["contributionDays"]:
            cells.append((c, d["weekday"], LEVELS[d["contributionLevel"]]))
    return cells


def build_route(cells, chain):
    """head route (without the off-grid entry), cut right after the last
    contribution is eaten; also returns the index each cell is eaten at."""
    lv = {(c, r): l for c, r, l in cells}
    chain = [tuple(p) for p in chain]
    if len(chain) > 1 and chain[0] not in lv:
        chain = chain[1:]
    eaten, last = {}, 0
    for i, p in enumerate(chain):
        if lv.get(p, 0) > 0 and p not in eaten:
            eaten[p] = i
            last = i
    return chain[:last + 1], eaten


def f1(v):
    return "%g" % round(v, 1)


def tf(x, y, s=1.0, r=0.0):
    return "translate(%spx,%spx) rotate(%sdeg) scale(%s)" % (f1(x), f1(y), f1(r), "%g" % round(s, 2))


class Gen:
    def __init__(self, weeks, chain, theme):
        self.theme = THEMES[theme]
        self.cells = build_cells(weeks)
        self.path, self.eaten = build_route(self.cells, chain)
        self.n = len(self.path)
        self.cols = len(weeks)
        self.rng = random.Random(7)
        self.A = (self.n - 1) * TICK                 # snake finishes eating
        self.T = self.A + 5.2                         # full loop
        self.B = self.A + 0.5                         # cells start flying back
        self.kfs = []
        self.body = []

    # --- geometry -------------------------------------------------------
    def center(self, c, r):
        return PADL + c * PITCH + SIZE / 2, PADT + r * PITCH + SIZE / 2

    def pos(self, idx):
        idx = max(0.0, min(self.n - 1.0, idx))
        i = int(math.floor(idx))
        j = min(self.n - 1, i + 1)
        a = self.center(*self.path[i][:2])
        b = self.center(*self.path[j][:2])
        t = idx - i
        return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t

    def corners(self):
        p = self.path
        out = [0]
        for i in range(1, self.n - 1):
            d1 = (p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1])
            d2 = (p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1])
            if d1 != d2:
                out.append(i)
        out.append(self.n - 1)
        return out

    # --- keyframes ------------------------------------------------------
    def keyframes(self, stops):
        """stops: list of (time, opacity, transform[, easing])"""
        stops = sorted(stops, key=lambda s: s[0])
        out, last = [], -1.0
        for s in stops:
            pct = round(max(0.0, min(100.0, s[0] / self.T * 100)), 3)
            if pct <= last:
                pct = round(last + 0.002, 3)
            if pct > 100:
                pct = 100.0
            last = pct
            e = ("animation-timing-function:%s;" % s[3]) if len(s) > 3 else ""
            out.append("%s%%{opacity:%s;transform:%s;%s}" % (
                ("%.3f" % pct).rstrip("0").rstrip("."), ("%.2f" % s[1]).rstrip("0").rstrip("."), s[2], e))
        name = "k%d" % len(self.kfs)
        self.kfs.append("@keyframes %s{%s}" % (name, "".join(out)))
        return name

    def node(self, tag, attrs, stops, base_tf=None):
        name = self.keyframes(stops)
        style = "animation-name:%s" % name
        if base_tf:
            style = "transform:%s;%s" % (base_tf, style)
        self.body.append('<%s %s class="a" style="%s"/>' % (tag, attrs, style))

    # --- scene ----------------------------------------------------------
    def build(self):
        th, T, A, B = self.theme, self.T, self.A, self.B
        W = self.cols * PITCH + PADL + PADR - (PITCH - SIZE)
        H = 7 * PITCH + PADT + PADB - (PITCH - SIZE)
        end = self.center(*self.path[-1][:2])
        start = self.center(*self.path[0][:2])

        # static empty grid
        for c, r, _ in self.cells:
            x = PADL + c * PITCH
            y = PADT + r * PITCH
            self.body.append('<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s"/>' % (x, y, SIZE, SIZE, th["empty"]))

        # contribution cells: eaten -> fly back from the explosion
        maxd = max(math.hypot(self.center(c, r)[0] - end[0], self.center(c, r)[1] - end[1]) for c, r, _ in self.cells) or 1
        for (c, r, lv) in self.cells:
            if lv == 0:
                continue
            idx = self.eaten[(c, r)]
            hx, hy = self.center(c, r)
            d = math.hypot(hx - end[0], hy - end[1])
            e = max(0.0, idx * TICK - 0.03)
            s = B + 1.5 * d / maxd + self.rng.random() * 0.2
            fl = 0.75 + self.rng.random() * 0.25
            stops = [
                (0, 1, tf(hx, hy)),
                (e, 1, tf(hx, hy)),
                (e + 0.10, 0, tf(hx, hy, .3)),
                (s - 0.01, 0, tf(hx, hy, .3)),
                (s, 0, tf(end[0], end[1], .3)),
                (s + 0.08, 1, tf(end[0], end[1], .3), EASE_OUT),
                (s + fl, 1, tf(hx, hy)),
                (T, 1, tf(hx, hy)),
            ]
            self.node("rect", 'x="-5" y="-5" width="10" height="10" rx="2" fill="%s"' % th["lv"][lv - 1], stops)

        self.explosion(end, A)
        self.blue_cell(start, end, B)
        self.snake()
        return W, H

    def explosion(self, end, A):
        T = self.T
        # flash + shockwave rings
        self.node("circle", 'r="9" fill="%s"' % BLUE, [
            (0, 0, tf(*end, .2)), (A, 0, tf(*end, .2)), (A + .002, .95, tf(*end, .3)),
            (A + .45, 0, tf(*end, 4.5), EASE_OUT), (T, 0, tf(*end, 4.5))])
        for k, (dur, big) in enumerate([(0.8, 6), (1.1, 9)]):
            lag = k * 0.12
            self.node("circle", 'r="9" fill="none" stroke="%s" stroke-width="2" vector-effect="non-scaling-stroke"' % BLUE, [
                (0, 0, tf(*end, .2)), (A + lag, 0, tf(*end, .2)), (A + lag + .002, .9, tf(*end, .3)),
                (A + lag + dur, 0, tf(*end, big), EASE_OUT), (T, 0, tf(*end, big))])
        # sparks
        colors = [BLUE, "#7fb0ff", "#ffffff", self.theme["lv"][3], self.theme["lv"][2]]
        for _ in range(34):
            a = self.rng.random() * math.tau
            dist = 35 + self.rng.random() * 110
            s = 2 + self.rng.random() * 3.2
            t1 = 0.6 + self.rng.random() * 0.7
            ex, ey = end[0] + math.cos(a) * dist, end[1] + math.sin(a) * dist
            col = self.rng.choice(colors)
            self.node("rect", 'x="%s" y="%s" width="%s" height="%s" rx="1" fill="%s"' % (f1(-s / 2), f1(-s / 2), f1(s), f1(s), col), [
                (0, 0, tf(*end)), (A, 0, tf(*end)), (A + .002, 1, tf(*end)),
                (A + t1, 0, tf(ex, ey, .3, self.rng.random() * 360), EASE_OUT), (T, 0, tf(ex, ey, .3))])

    def ring(self, at, center, dur=0.8):
        T = self.T
        stops = []
        if at > 0:
            stops += [(0, 0, tf(*center, .3)), (at, 0, tf(*center, .3))]
        stops += [(at + .002, .9, tf(*center, .4)), (at + dur, 0, tf(*center, 3.2), EASE_OUT), (T, 0, tf(*center, 3.2))]
        self.node("circle", 'r="8" fill="none" stroke="%s" stroke-width="2" vector-effect="non-scaling-stroke"' % BLUE, stops)

    def blue_cell(self, start, end, B):
        T = self.T
        land = B + 2.4
        # ghost trail first (drawn below), then the real one
        for j in range(5, -1, -1):
            lag = j * 0.07
            op = 1 if j == 0 else 0.5 / j
            stops = [
                (0, 0, tf(*start)),
                (B + .15 + lag, 0, tf(*end, .3)),
                (B + .2 + lag, op, tf(*end, .3), "cubic-bezier(.35,.0,.2,1)"),
                (land + lag, op, tf(*start)),
            ]
            if j == 0:
                stops += [(land + .15, 1, tf(*start, 1.5)), (land + .35, 1, tf(*start)),
                          (T - .01, 1, tf(*start)), (T, 1, tf(*start))]
            else:
                stops += [(land + lag + .1, 0, tf(*start)), (T, 0, tf(*start))]
            self.node("rect", 'x="-5" y="-5" width="10" height="10" rx="2.5" fill="%s"' % BLUE, stops)
        self.ring(land, start, .8)   # landing
        self.ring(0, start, .9)      # birth of the new snake

    def snake(self):
        T, A = self.T, self.A
        corners = self.corners()
        rng = self.rng
        end = self.center(*self.path[-1][:2])
        for k in range(SEG - 1, -1, -1):          # tail first so the head is on top
            size = max(6.5, 10 - 0.28 * k)
            g = 0 if k == 0 else GROW * k * TICK    # appear when head reaches GROW*k
            times = {0.0, A}
            for i in corners:
                t = (i + k) * TICK
                if t <= A:
                    times.add(round(t, 4))
            if k:
                times.update({round(g, 4), round(g + .15, 4)})
            stops = []
            for t in sorted(times):
                x, y = self.pos(t / TICK - k)
                op = 1.0 if k == 0 else max(0.0, min(1.0, (t - g) / .15))
                stops.append((t, op, tf(x, y)))
            # burst
            x, y = self.pos(self.n - 1 - k)
            ang = math.atan2(y - end[1], x - end[0]) + (rng.random() - .5) * 2.4
            dist = 45 + rng.random() * 90
            b0 = A + k * 0.03
            stops.append((b0, 1, tf(x, y)))
            stops.append((b0 + .8, 0, tf(x + math.cos(ang) * dist, y + math.sin(ang) * dist, .2, (rng.random() - .5) * 540), EASE_OUT))
            stops.append((T, 0, tf(x, y, .2)))
            h = size / 2
            self.node("rect", 'x="%s" y="%s" width="%s" height="%s" rx="3" fill="%s"' % (f1(-h), f1(-h), f1(size), f1(size), BLUE), stops)

    def svg(self):
        W, H = self.build()
        css = ".a{animation-duration:%.3fs;animation-iteration-count:infinite;animation-timing-function:linear}" % self.T
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">'
                '<style>%s%s</style>%s</svg>') % (W, H, W, H, css, "".join(self.kfs), "".join(self.body))


def main():
    args = sys.argv[1:]
    theme = "dark"
    if "--theme" in args:
        i = args.index("--theme")
        theme = args[i + 1]
        del args[i:i + 2]
    src, chain, out = args
    svg = Gen(load(src), json.load(open(chain)), theme).svg()
    open(out, "w").write(svg)
    print("%s: %d bytes" % (out, len(svg)))


if __name__ == "__main__":
    main()
