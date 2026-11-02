#!/usr/bin/env python3
"""Make the snk snake grow longer as it eats contribution cells.

snk draws a fixed 4 segment snake (classes s0..s3), each one following the same
path as the head, delayed by one tick. We append extra tail segments (s4..sN)
that reuse the head keyframes with a bigger delay and fade in after a given
fraction of the cells has been eaten.
"""
import re
import sys

MAX_LEN = 14          # final snake length (snk default is 4)
TAIL_MIN_SIZE = 8.4   # smallest tail segment size (px)


def grow(svg: str) -> str:
    dur = int(re.search(r"animation:none linear (\d+)ms", svg).group(1))

    # time (in %) at which each contribution cell gets eaten
    eaten = sorted(
        float(m.group(1))
        for m in re.finditer(r"@keyframes c[0-9a-z]+\{([\d.]+)%\{fill:var\(--c\d\)\}", svg)
    )
    if not eaten:
        return svg

    # tick duration: snk moves one cell per tick
    tick_ms = 100 if dur % 100 == 0 else dur / round(dur / 100)

    rects = []
    css = []
    n_extra = MAX_LEN - 4
    for k in range(4, MAX_LEN):
        step = k - 3  # 1..n_extra
        # appear once this fraction of cells has been eaten
        frac = step / (n_extra + 1)
        t = eaten[min(len(eaten) - 1, int(frac * len(eaten)))]
        size = max(TAIL_MIN_SIZE, 9.9 - 0.15 * (k - 3))
        off = (16 - size) / 2
        rects.append(
            f'<rect class="s s{k}" x="{off:.1f}" y="{off:.1f}" width="{size:.1f}" '
            f'height="{size:.1f}" rx="{size * 0.33:.1f}" ry="{size * 0.33:.1f}"/>'
        )
        delay = -(dur - k * tick_ms)  # follow the head k ticks behind
        css.append(
            f"@keyframes v{k}{{0%,{t:.2f}%{{opacity:0}}{t + 0.02:.2f}%,100%{{opacity:1}}}}"
            f".s.s{k}{{animation-name:s0,v{k};animation-duration:{dur}ms,{dur}ms;"
            f"animation-delay:{delay:.0f}ms,0ms;animation-timing-function:linear,step-end;"
            f"animation-iteration-count:infinite,infinite;"
            f"transform-origin:0 0;opacity:0}}"
        )

    # s0 keyframes are also used by the head; extra tail rects reuse them
    svg = svg.replace("</style>", "".join(css) + "</style>", 1)
    last = list(re.finditer(r'<rect class="s s3"[^>]*/>', svg))[-1]
    svg = svg[: last.end()] + "".join(rects) + svg[last.end():]
    return svg


if __name__ == "__main__":
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            data = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(grow(data))
        print(f"grown: {path}")
