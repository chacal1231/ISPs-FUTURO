from __future__ import annotations

import argparse
import asyncio
import html
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from CheckListas import DNSBLS, IPScanResult, scan_targets

RISK_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
RISK_LABELS = {
    "HIGH": "ALTO",
    "MEDIUM": "MEDIO",
    "LOW": "BAJO",
}


def load_targets(args) -> list[str]:
    targets = list(args.targets or [])

    if args.file:
        source = Path(args.file)
        targets.extend(source.read_text(encoding="utf-8").splitlines())

    return [target.strip() for target in targets if target.strip()]


def colorize(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    colors = {
        "red": "\033[31m",
        "yellow": "\033[33m",
        "green": "\033[32m",
        "cyan": "\033[36m",
        "bold": "\033[1m",
    }
    return f"{colors[color]}{text}\033[0m"


def risk_color(risk: str) -> str:
    return {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}.get(risk, "cyan")


def risk_bar(result: IPScanResult, total_zones: int) -> str:
    width = 18
    filled = 0 if total_zones == 0 else round((result.listed_count / total_zones) * width)
    filled = max(1, filled) if result.listed_count else 0
    return "[" + "#" * filled + "." * (width - filled) + "]"


def render_console(results: list[IPScanResult], elapsed: float, use_color: bool) -> str:
    sorted_results = sorted(results, key=lambda item: (RISK_ORDER[item.risk_level], item.ip))
    listed_ips = [item for item in results if item.listed_count > 0]
    total_hits = sum(item.listed_count for item in results)
    total_zones = len(DNSBLS)

    lines = [
        "",
        colorize("DNSBL scan results", "bold", use_color),
        f"IPs scanned: {len(results)} | DNSBL zones: {total_zones} | Listed IPs: {len(listed_ips)} | Hits: {total_hits} | Time: {elapsed:.2f}s",
        "",
        f"{'IP':<16} {'RISK':<8} {'HITS':<7} {'VISUAL':<20} BLACKLISTS",
        "-" * 92,
    ]

    for result in sorted_results:
        label = RISK_LABELS[result.risk_level]
        risk = colorize(label.ljust(8), risk_color(result.risk_level), use_color)
        lists = ", ".join(hit.blacklist for hit in result.listed_on[:4])
        if len(result.listed_on) > 4:
            lists += f" +{len(result.listed_on) - 4}"
        lines.append(
            f"{result.ip:<16} {risk} {result.listed_count:<7} "
            f"{risk_bar(result, total_zones):<20} {lists or '-'}"
        )

    flagged = [item for item in sorted_results if item.listed_count > 0]
    if flagged:
        lines.extend(["", "Details"])
        for result in flagged:
            lines.append(f"- {result.ip} ({RISK_LABELS[result.risk_level]})")
            for hit in result.listed_on:
                codes = ", ".join(hit.response_codes) or "-"
                detail = "; ".join(hit.details) if hit.details else "No TXT detail"
                lines.append(f"  - {hit.blacklist} ({hit.zone}) [{codes}] {detail}")

    return "\n".join(lines)


def result_to_dict(result: IPScanResult) -> dict:
    return result.to_dict()


def write_json(results: list[IPScanResult], output_path: Path) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dnsbl_zones": len(DNSBLS),
        "results": [result_to_dict(result) for result in results],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_html_report(results: list[IPScanResult], output_dir: Path, elapsed: float) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"dnsbl-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"

    sorted_results = sorted(results, key=lambda item: (RISK_ORDER[item.risk_level], item.ip))
    listed_ips = [item for item in results if item.listed_count > 0]
    total_hits = sum(item.listed_count for item in results)
    total_zones = len(DNSBLS)

    cards = []
    rows = []
    details = []

    for result in sorted_results:
        risk_class = result.risk_level.lower()
        label = RISK_LABELS[result.risk_level]
        percent = 0 if total_zones == 0 else min(100, round((result.listed_count / total_zones) * 100))
        lists = ", ".join(html.escape(hit.blacklist) for hit in result.listed_on[:5])
        if len(result.listed_on) > 5:
            lists += f" +{len(result.listed_on) - 5}"

        rows.append(
            "<tr>"
            f"<td>{html.escape(result.ip)}</td>"
            f"<td><span class='pill {risk_class}'>{label}</span></td>"
            f"<td>{result.listed_count}</td>"
            f"<td><span class='bar'><span style='width:{percent}%'></span></span></td>"
            f"<td>{lists or '-'}</td>"
            "</tr>"
        )

        if result.listed_count > 0:
            hit_items = []
            for hit in result.listed_on:
                codes = ", ".join(html.escape(code) for code in hit.response_codes) or "-"
                detail = "; ".join(html.escape(item) for item in hit.details) or "No TXT detail"
                hit_items.append(
                    "<li>"
                    f"<strong>{html.escape(hit.blacklist)}</strong>"
                    f"<span>{html.escape(hit.zone)}</span>"
                    f"<code>{codes}</code>"
                    f"<p>{detail}</p>"
                    "</li>"
                )
            details.append(
                f"<section class='detail {risk_class}'>"
                f"<h2>{html.escape(result.ip)} <span>{label}</span></h2>"
                f"<ul>{''.join(hit_items)}</ul>"
                "</section>"
            )

    stats = [
        ("IPs scanned", len(results)),
        ("Listed IPs", len(listed_ips)),
        ("Total hits", total_hits),
        ("DNSBL zones", total_zones),
        ("Elapsed", f"{elapsed:.2f}s"),
    ]
    for title, value in stats:
        cards.append(f"<div class='stat'><span>{html.escape(str(title))}</span><strong>{html.escape(str(value))}</strong></div>")

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DNSBL scan report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #647084;
      --line: #dce3ee;
      --green: #147a48;
      --yellow: #a26100;
      --red: #be123c;
      --cyan: #0f6f85;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    header {{
      padding: 32px clamp(18px, 4vw, 52px) 24px;
      background: #14213d;
      color: white;
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: clamp(28px, 4vw, 42px);
      letter-spacing: 0;
    }}
    header p {{ margin: 0; color: #cbd5e1; }}
    main {{ padding: 24px clamp(18px, 4vw, 52px) 44px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 22px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .stat span {{ display: block; color: var(--muted); font-size: 13px; }}
    .stat strong {{ display: block; margin-top: 5px; font-size: 26px; }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 22px;
    }}
    .panel h2 {{ margin: 0; padding: 16px 18px; font-size: 18px; border-bottom: 1px solid var(--line); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--line); vertical-align: middle; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }}
    tr:last-child td {{ border-bottom: 0; }}
    .pill {{
      display: inline-flex;
      min-width: 68px;
      justify-content: center;
      border-radius: 999px;
      padding: 4px 9px;
      color: white;
      font-size: 12px;
      font-weight: 700;
    }}
    .low {{ background: var(--green); }}
    .medium {{ background: var(--yellow); }}
    .high {{ background: var(--red); }}
    .bar {{
      display: block;
      width: min(210px, 34vw);
      height: 10px;
      background: #e8edf5;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar span {{ display: block; height: 100%; background: var(--cyan); }}
    .detail {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-left-width: 5px;
      border-radius: 8px;
      margin-bottom: 12px;
      padding: 16px;
    }}
    .detail.high {{ border-left-color: var(--red); background: white; }}
    .detail.medium {{ border-left-color: var(--yellow); background: white; }}
    .detail h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .detail h2 span {{ color: var(--muted); font-size: 14px; margin-left: 8px; }}
    .detail ul {{ margin: 0; padding-left: 20px; }}
    .detail li {{ margin: 0 0 12px; }}
    .detail li span {{ color: var(--muted); margin-left: 8px; }}
    code {{
      display: inline-block;
      margin-left: 8px;
      padding: 2px 6px;
      border-radius: 6px;
      background: #edf2f7;
    }}
    .detail p {{ margin: 4px 0 0; color: var(--muted); }}
    @media (max-width: 760px) {{
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ border-bottom: 1px solid var(--line); padding: 10px 0; }}
      td {{ border: 0; padding: 6px 14px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>DNSBL scan report</h1>
    <p>Generated {html.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</p>
  </header>
  <main>
    <section class="stats">{''.join(cards)}</section>
    <section class="panel">
      <h2>Summary</h2>
      <table>
        <thead>
          <tr><th>IP</th><th>Risk</th><th>Hits</th><th>Visual</th><th>Blacklists</th></tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    {''.join(details) if details else '<section class="panel"><h2>No listings found</h2></section>'}
  </main>
</body>
</html>
"""

    report_path.write_text(html_doc, encoding="utf-8")
    return report_path


async def run(args) -> int:
    targets = load_targets(args)
    if not targets:
        print("No targets provided. Pass IPs/CIDR arguments or use --file.", file=sys.stderr)
        return 2

    started = time.perf_counter()
    results = await scan_targets(
        targets,
        concurrency=args.concurrency,
        timeout=args.timeout,
        lifetime=args.timeout,
        max_hosts=args.max_hosts,
    )
    elapsed = time.perf_counter() - started

    print(render_console(results, elapsed, use_color=not args.no_color))

    if args.json:
        json_path = Path(args.json)
        write_json(results, json_path)
        print(f"\nJSON report: {json_path}")

    if not args.no_html:
        report_path = write_html_report(results, Path(args.report_dir), elapsed)
        print(f"HTML report: {report_path}")

    return 1 if args.fail_on_listed and any(item.listed_count > 0 for item in results) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan IPv4 addresses or CIDR ranges against public DNSBL zones.",
    )
    parser.add_argument("targets", nargs="*", help="IPv4 addresses or CIDR ranges")
    parser.add_argument("-f", "--file", help="File with one IPv4/CIDR target per line")
    parser.add_argument("--max-hosts", type=int, default=256, help="Maximum hosts expanded from one CIDR")
    parser.add_argument("--concurrency", type=int, default=80, help="Maximum concurrent DNS queries")
    parser.add_argument("--timeout", type=int, default=5, help="DNS timeout in seconds")
    parser.add_argument("--report-dir", default="reports", help="Directory for HTML reports")
    parser.add_argument("--json", help="Optional JSON output path")
    parser.add_argument("--no-html", action="store_true", help="Do not generate an HTML report")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors in the terminal")
    parser.add_argument("--fail-on-listed", action="store_true", help="Exit with code 1 if any IP is listed")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nScan interrupted.", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
