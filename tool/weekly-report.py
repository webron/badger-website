#!/usr/bin/env python3
"""Build the weekly badger.fit stats page and open it.

Meant to run unattended on a timer, so it has no dependencies beyond the Python
standard library and never fails the whole report because one source is down: a
source that cannot answer says so in its own panel and the rest still render.

Every headline figure is shown against the four weeks before it. On a site this
size a single forum post can make one week look ten times better than the last,
and a bare number invites reading that as growth.

Usage:
    tool/weekly-report.py              # build and open it
    tool/weekly-report.py --no-open    # build only (what the timer runs)
    tool/weekly-report.py --out PATH   # somewhere other than the default
"""

from __future__ import annotations

import html
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _stats_sources import (  # noqa: E402
    STORE_EVENTS, goatcounter, play, play_quality, search_console,
)

DEFAULT_OUT = Path.home() / "Development/badger-artifacts/site-stats/weekly.html"
WEEKS = 5  # this week plus the four it is measured against


def esc(value: object) -> str:
    return html.escape(str(value))


def weekly_buckets(daily: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Fold a run of days into trailing 7-day buckets, newest last."""
    counts = [count for _, count in daily]
    labels = [day for day, _ in daily]
    out = []
    for end in range(len(counts), 0, -7):
        start = max(0, end - 7)
        if end - start < 7 and out:
            break  # a part-week at the far end would read as a collapse
        out.append((labels[start], sum(counts[start:end])))
    return list(reversed(out))


def sparkline(buckets: list[tuple[str, int]]) -> str:
    """A bar per week, sized against the largest. Plain divs, no chart library."""
    if not buckets:
        return ""
    peak = max(count for _, count in buckets) or 1
    bars = []
    for i, (label, count) in enumerate(buckets):
        height = max(3, round(count / peak * 46))
        current = " current" if i == len(buckets) - 1 else ""
        bars.append(
            f'<div class="bar{current}" title="week of {esc(label)}: {count}">'
            f'<span style="height:{height}px"></span><em>{count}</em></div>'
        )
    return f'<div class="spark">{"".join(bars)}</div>'


def trend(buckets: list[tuple[str, int]], fallback: int) -> tuple[int, str]:
    """This week's figure and one sentence putting it against the weeks before.

    Both panels need this and they must phrase it identically, or the reader has
    to work out whether two differently-worded comparisons mean the same thing.
    """
    this_week = buckets[-1][1] if buckets else fallback
    prior = [c for _, c in buckets[:-1]]
    if not prior:
        return this_week, "No earlier weeks to compare against yet."

    average = round(sum(prior) / len(prior))
    if average == 0:
        return this_week, "Nothing in the weeks before this one."

    change = (this_week - average) / average
    if this_week == average:
        return this_week, f"The same as the previous {len(prior)}-week average."
    direction = "above" if change > 0 else "below"
    return this_week, (f"{abs(change):.0%} {direction} the previous "
                       f"{len(prior)}-week average of {average}.")


def rows_table(headers: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f'<p class="empty">{esc(empty)}</p>'
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def panel(title: str, subtitle: str, inner: str) -> str:
    sub = f'<p class="sub">{esc(subtitle)}</p>' if subtitle else ""
    return f'<section><h2>{esc(title)}</h2>{sub}{inner}</section>'


def error_panel(title: str, message: str) -> str:
    return panel(title, "", f'<p class="error">{esc(message)}</p>')


def build_goatcounter(days: int) -> str:
    gc = goatcounter(days)
    if "error" in gc:
        return error_panel("Website", gc["error"])

    buckets = weekly_buckets(gc["daily"])
    this_week, context = trend(buckets, gc["views"])

    parts = [
        f'<p class="figure">{this_week}<span> page views this week</span></p>',
        f'<p class="sub">{esc(context)}</p>',
        sparkline(buckets),
    ]

    parts.append("<h3>Pages</h3>")
    parts.append(rows_table(
        ["Views", "Page"],
        [[str(c), esc(p)] for p, c in gc["pages"][:15]],
        "No pages recorded in this window."))

    parts.append("<h3>Came from</h3>")
    parts.append(rows_table(
        ["Visits", "Source"],
        [[str(c), esc(n)] for n, c in gc["referrers"][:10]],
        "No referrers. Everyone typed the address or followed a private link."))

    parts.append("<h3>Countries</h3>")
    parts.append(rows_table(
        ["Visits", "Country"],
        [[str(c), esc(n)] for n, c in gc["countries"][:10]],
        "Nothing yet."))

    taps = [(label, gc["events"].get(path, 0)) for path, label in STORE_EVENTS.items()]
    taps = [t for t in taps if t[1] or "retired" not in t[0]]
    views = gc["views"] or 0
    parts.append("<h3>Store link taps</h3>")
    parts.append(rows_table(
        ["Taps", "Store", "Share of views"],
        [[str(c), esc(label), f"{c / views:.1%}" if views else "n/a"] for label, c in taps],
        "Nobody has tapped through to a store in this window."))

    return panel("Website", f"{gc['start']} to {gc['end']} UTC", "".join(parts))


def build_search_console(days: int) -> str:
    sc = search_console(days)
    if "error" in sc:
        return error_panel("Google search", sc["error"])

    parts = [
        f'<p class="figure">{sc["clicks"]}<span> clicks from search</span></p>',
        f'<p class="sub">Shown in results {sc["impressions"]} times. '
        f'Google\'s data lags a couple of days, so this window ends earlier than the website one.</p>',
    ]

    parts.append("<h3>What people searched for</h3>")
    parts.append(rows_table(
        ["Clicks", "Shown", "Avg position", "Query"],
        [[str(r["clicks"]), str(r["impressions"]), f'#{r["position"]:.1f}', esc(r["key"])]
         for r in sc["queries"][:20]],
        "Nothing yet. Google needs a few days after verification before it reports anything."))

    parts.append("<h3>Pages found in search</h3>")
    parts.append(rows_table(
        ["Clicks", "Shown", "Page"],
        [[str(r["clicks"]), str(r["impressions"]), esc(r["key"])] for r in sc["pages"][:10]],
        "Nothing yet."))

    return panel("Google search", f"{sc['start']} to {sc['end']}", "".join(parts))


def build_play(days: int) -> str:
    p = play(days)
    if "error" in p:
        return error_panel("Play Store", p["error"])

    buckets = weekly_buckets(p["daily"])
    this_week, context = trend(buckets, p["installs"])

    parts = [
        f'<p class="figure">{this_week}<span> installs this week</span></p>',
        f'<p class="sub">{esc(context)} {p["active"]} devices have Badger installed right now, '
        f'and {p["uninstalls"]} uninstalled over the window.</p>',
        sparkline(buckets),
    ]

    parts.append("<h3>Where store visits came from</h3>")
    parts.append(rows_table(
        ["Acquisitions", "Traffic source"],
        [[str(c), esc(name)] for name, c in p["sources"]],
        "No store acquisitions recorded in this window."))

    q = play_quality()
    parts.append("<h3>Quality</h3>")
    if "error" in q:
        parts.append(f'<p class="error">{esc(q["error"])}</p>')
    elif "empty" in q:
        parts.append(f'<p class="empty">{esc(q["empty"])}</p>')
    else:
        parts.append(rows_table(
            ["Rate", "Metric"],
            [[f"{v:.2%}", esc(k)] for k, v in q.items()],
            "Nothing reported."))

    note = ""
    if p["missing"]:
        # Play publishes a month's file once it has something to put in it, so a
        # gap early in the month is normal. Say so rather than showing a dip.
        note = (" Play has not published " + ", ".join(p["missing"])
                + " yet, so the newest days may be missing.")

    return panel("Play Store", f"{p['start']} to {p['end']}.{note}", "".join(parts))


CSS = """
:root{color-scheme:light dark;--bg:#F1EDE3;--card:#FBF8F1;--ink:#211E19;--muted:#6B655A;
--rule:#DCD5C6;--accent:#2E7E90;--bad:#9C3B2E}
@media(prefers-color-scheme:dark){:root{--bg:#1C1A16;--card:#252118;--ink:#EDE7DA;
--muted:#9A9284;--rule:#3A3428;--accent:#4FA3B5;--bad:#D97B68}}
*{box-sizing:border-box}
body{margin:0;padding:32px 20px 64px;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
.wrap{max-width:840px;margin:0 auto}
h1{font-size:26px;margin:0 0 4px}
.stamp{color:var(--muted);margin:0 0 28px;font-size:13px}
section{background:var(--card);border:1px solid var(--rule);border-radius:12px;
padding:22px 24px;margin-bottom:22px}
h2{font-size:19px;margin:0 0 2px}
h3{font-size:13px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
margin:26px 0 8px;font-weight:600}
.sub{color:var(--muted);font-size:13px;margin:0 0 14px}
.figure{font-size:40px;font-weight:700;margin:14px 0 2px;line-height:1;
font-variant-numeric:tabular-nums}
.figure span{font-size:15px;font-weight:400;color:var(--muted)}
.empty{color:var(--muted);font-size:13px;font-style:italic;margin:0}
.error{color:var(--bad);font-size:13px;margin:0}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;color:var(--muted);font-weight:600;font-size:11px;
text-transform:uppercase;letter-spacing:.06em;padding:0 10px 6px 0;
border-bottom:1px solid var(--rule)}
td{padding:6px 10px 6px 0;border-bottom:1px solid var(--rule);
word-break:break-word;font-variant-numeric:tabular-nums}
th:first-child,td:first-child{width:1%;white-space:nowrap;text-align:right;padding-right:14px}
tr:last-child td{border-bottom:none}
.spark{display:flex;align-items:flex-end;gap:8px;height:74px;margin:16px 0 4px}
.bar{display:flex;flex-direction:column;justify-content:flex-end;align-items:center;
flex:1;gap:4px}
.bar span{display:block;width:100%;background:var(--rule);border-radius:3px}
.bar.current span{background:var(--accent)}
.bar em{font-style:normal;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}
footer{color:var(--muted);font-size:12px;text-align:center;margin-top:8px}
"""


def main() -> None:
    argv = sys.argv[1:]
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)

    days = WEEKS * 7
    built = datetime.now().strftime("%A %-d %B %Y, %H:%M")

    body = "".join([
        build_goatcounter(days),
        build_search_console(days),
        build_play(days),
        panel("App Store", "",
              '<p class="empty">Waiting on the iOS release.</p>'),
    ])

    page = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>badger.fit weekly stats</title>"
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
        "<h1>badger.fit</h1>"
        f"<p class=\"stamp\">Built {esc(built)}. Each headline is measured against "
        f"the previous {WEEKS - 1} weeks.</p>"
        f"{body}"
        "<footer>Generated by tool/weekly-report.py</footer>"
        "</div></body></html>"
    )

    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out}")

    if "--no-open" not in argv:
        subprocess.run(["open", str(out)], check=False)


if __name__ == "__main__":
    main()
