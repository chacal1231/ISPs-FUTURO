from __future__ import annotations

import argparse
import asyncio
import html
import json
import sys
import time
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from CheckListas import DNSBLS, IPScanResult, scan_targets

RISK_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
RISK_LABELS = {
    "HIGH": "ALTO",
    "MEDIUM": "MEDIO",
    "LOW": "BAJO",
}


def result_to_dict(result: IPScanResult) -> dict:
    return result.to_dict()


def build_payload(results: list[IPScanResult], elapsed: float) -> dict:
    sorted_results = sorted(results, key=lambda item: (RISK_ORDER[item.risk_level], item.ip))
    listed_ips = [item for item in sorted_results if item.listed_count > 0]
    total_hits = sum(item.listed_count for item in sorted_results)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed": round(elapsed, 2),
        "dnsbl_zones": len(DNSBLS),
        "listed_ips": len(listed_ips),
        "total_hits": total_hits,
        "results": [result_to_dict(result) for result in sorted_results],
    }


def write_json_report(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_html_report(payload: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"dnsbl-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"

    rows = []
    details = []
    total_zones = payload["dnsbl_zones"]

    for result in payload["results"]:
        risk_level = result["risk_level"]
        risk_class = risk_level.lower()
        label = RISK_LABELS[risk_level]
        listed_on = result["listed_on"]
        percent = 0 if total_zones == 0 else min(100, round((result["listed_count"] / total_zones) * 100))
        lists = ", ".join(html.escape(hit["blacklist"]) for hit in listed_on[:5])
        if len(listed_on) > 5:
            lists += f" +{len(listed_on) - 5}"

        rows.append(
            "<tr>"
            f"<td>{html.escape(result['ip'])}</td>"
            f"<td><span class='pill {risk_class}'>{label}</span></td>"
            f"<td>{result['listed_count']}</td>"
            f"<td><span class='bar'><span style='width:{percent}%'></span></span></td>"
            f"<td>{lists or '-'}</td>"
            "</tr>"
        )

        if result["listed_count"] > 0:
            hit_items = []
            for hit in listed_on:
                codes = ", ".join(html.escape(code) for code in hit["response_codes"]) or "-"
                detail = "; ".join(html.escape(item) for item in hit["details"]) or "Sin detalle TXT"
                hit_items.append(
                    "<li>"
                    f"<strong>{html.escape(hit['blacklist'])}</strong>"
                    f"<span>{html.escape(hit['zone'])}</span>"
                    f"<code>{codes}</code>"
                    f"<p>{detail}</p>"
                    "</li>"
                )
            details.append(
                f"<section class='detail {risk_class}'>"
                f"<h2>{html.escape(result['ip'])} <span>{label}</span></h2>"
                f"<ul>{''.join(hit_items)}</ul>"
                "</section>"
            )

    stats = [
        ("IPs escaneadas", len(payload["results"])),
        ("IPs listadas", payload["listed_ips"]),
        ("Hits totales", payload["total_hits"]),
        ("Zonas DNSBL", payload["dnsbl_zones"]),
        ("Tiempo", f"{payload['elapsed']:.2f}s"),
    ]
    cards = [
        f"<div class='stat'><span>{html.escape(title)}</span><strong>{html.escape(str(value))}</strong></div>"
        for title, value in stats
    ]

    html_doc = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reporte DNSBL</title>
  <style>{REPORT_CSS}</style>
</head>
<body>
  <header>
    <h1>Reporte DNSBL</h1>
    <p>Generado {html.escape(payload['generated_at'])}</p>
  </header>
  <main>
    <section class="stats">{''.join(cards)}</section>
    <section class="panel">
      <h2>Resumen</h2>
      <table>
        <thead>
          <tr><th>IP</th><th>Riesgo</th><th>Hits</th><th>Visual</th><th>Scanner de listas negras</th></tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    {''.join(details) if details else '<section class="panel"><h2>No se encontraron listados</h2></section>'}
  </main>
</body>
</html>
"""
    report_path.write_text(html_doc, encoding="utf-8")
    return report_path


async def execute_scan(options: dict) -> dict:
    targets = [target.strip() for target in options.get("targets", []) if target.strip()]
    if not targets:
        raise ValueError("Ingresa al menos una IPv4 o rango CIDR.")

    started = time.perf_counter()
    results = await scan_targets(
        targets,
        concurrency=int(options.get("concurrency", 80)),
        timeout=int(options.get("timeout", 5)),
        lifetime=int(options.get("timeout", 5)),
        max_hosts=int(options.get("max_hosts", 256)),
    )
    elapsed = time.perf_counter() - started
    payload = build_payload(results, elapsed)

    if options.get("save_report", True):
        report_path = write_html_report(payload, Path(options.get("report_dir") or "reports"))
        payload["report_path"] = str(report_path)

    if options.get("save_json"):
        json_path = Path(options.get("json_path") or "reports/dnsbl-last-result.json")
        write_json_report(payload, json_path)
        payload["json_path"] = str(json_path)

    return payload


APP_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Listas Negras DNSBL</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #eef3f8;
      --panel: #ffffff;
      --ink: #18212f;
      --muted: #627087;
      --line: #d7e0eb;
      --accent: #116466;
      --accent-2: #1f7a8c;
      --green: #15803d;
      --yellow: #b45309;
      --red: #be123c;
      --soft: #f8fafc;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }
    header {
      background: #102a43;
      color: #fff;
      padding: 24px clamp(16px, 4vw, 44px);
      border-bottom: 4px solid var(--accent-2);
    }
    h1 { margin: 0; font-size: clamp(26px, 4vw, 40px); letter-spacing: 0; }
    header p { margin: 6px 0 0; color: #c8d7e6; max-width: 780px; }
    main {
      width: min(1180px, calc(100% - 28px));
      margin: 22px auto 42px;
      display: grid;
      grid-template-columns: minmax(290px, 360px) 1fr;
      gap: 18px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .panel-head {
      padding: 15px 16px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    h2 { margin: 0; font-size: 18px; letter-spacing: 0; }
    form { padding: 16px; display: grid; gap: 14px; }
    label { display: grid; gap: 6px; color: var(--muted); font-size: 13px; font-weight: 700; }
    textarea, input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      padding: 10px 11px;
      outline: none;
    }
    textarea { min-height: 180px; resize: vertical; }
    textarea:focus, input:focus { border-color: var(--accent-2); box-shadow: 0 0 0 3px rgba(31, 122, 140, .16); }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--ink);
      font-size: 14px;
      font-weight: 600;
    }
    .check input { width: 16px; height: 16px; }
    button {
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      min-height: 42px;
      padding: 0 15px;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }
    button:hover { background: #0d5557; }
    button:disabled { cursor: wait; opacity: .72; }
    .status {
      padding: 10px 12px;
      border-radius: 6px;
      background: var(--soft);
      color: var(--muted);
      font-size: 14px;
      min-height: 42px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 10px;
      padding: 16px;
      border-bottom: 1px solid var(--line);
    }
    .stat {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: var(--soft);
    }
    .stat span { display: block; color: var(--muted); font-size: 12px; }
    .stat strong { display: block; margin-top: 4px; font-size: 24px; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; min-width: 720px; }
    th, td { padding: 11px 13px; text-align: left; border-bottom: 1px solid var(--line); vertical-align: middle; }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
    .pill {
      display: inline-flex;
      min-width: 68px;
      justify-content: center;
      border-radius: 999px;
      padding: 4px 9px;
      color: #fff;
      font-size: 12px;
      font-weight: 800;
    }
    .low { background: var(--green); }
    .medium { background: var(--yellow); }
    .high { background: var(--red); }
    .bar {
      display: block;
      width: 170px;
      height: 10px;
      background: #e4ebf3;
      border-radius: 999px;
      overflow: hidden;
    }
    .bar span { display: block; height: 100%; background: var(--accent-2); }
    .details { padding: 16px; display: grid; gap: 12px; }
    .detail {
      border: 1px solid var(--line);
      border-left: 5px solid var(--accent-2);
      border-radius: 8px;
      padding: 14px;
      background: #fff;
    }
    .detail.high { border-left-color: var(--red); }
    .detail.medium { border-left-color: var(--yellow); }
    .detail h3 { margin: 0 0 9px; font-size: 17px; }
    .detail ul { margin: 0; padding-left: 18px; }
    .detail li { margin-bottom: 10px; }
    code {
      display: inline-block;
      margin-left: 6px;
      padding: 2px 6px;
      border-radius: 5px;
      background: #eaf0f6;
    }
    .empty { padding: 32px 16px; color: var(--muted); text-align: center; }
    .links { padding: 0 16px 16px; color: var(--muted); font-size: 14px; }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      .stats { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <h1>Listas Negras DNSBL</h1>
    <p>Escanea IPv4 y rangos CIDR contra zonas DNSBL publicas desde una interfaz web local.</p>
  </header>
  <main>
    <section class="panel">
      <div class="panel-head"><h2>Escaneo</h2></div>
      <form id="scan-form">
        <label>IPs o rangos CIDR
          <textarea id="targets" placeholder="8.8.8.8&#10;1.1.1.1&#10;203.0.113.0/29"></textarea>
        </label>
        <div class="grid">
          <label>Max hosts
            <input id="max-hosts" type="number" min="1" value="256">
          </label>
          <label>Timeout
            <input id="timeout" type="number" min="1" value="5">
          </label>
        </div>
        <label>Concurrencia
          <input id="concurrency" type="number" min="1" value="80">
        </label>
        <label class="check">
          <input id="save-report" type="checkbox" checked>
          Guardar reporte HTML en reports/
        </label>
        <label class="check">
          <input id="save-json" type="checkbox">
          Guardar JSON del ultimo resultado
        </label>
        <button id="scan-button" type="submit">Escanear</button>
        <div id="status" class="status">Listo para escanear.</div>
      </form>
    </section>
    <section class="panel">
      <div class="panel-head"><h2>Resultados</h2><span id="generated"></span></div>
      <div id="results">
        <div class="empty">Ejecuta un escaneo para ver el resumen y el detalle.</div>
      </div>
    </section>
  </main>
  <script>
    const form = document.querySelector("#scan-form");
    const button = document.querySelector("#scan-button");
    const statusBox = document.querySelector("#status");
    const resultsBox = document.querySelector("#results");
    const generated = document.querySelector("#generated");
    const labels = { HIGH: "ALTO", MEDIUM: "MEDIO", LOW: "BAJO" };

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      }[char]));
    }

    function stat(title, value) {
      return `<div class="stat"><span>${title}</span><strong>${escapeHtml(value)}</strong></div>`;
    }

    function render(data) {
      generated.textContent = data.generated_at || "";
      const stats = [
        stat("IPs", data.results.length),
        stat("Listadas", data.listed_ips),
        stat("Hits", data.total_hits),
        stat("DNSBL", data.dnsbl_zones),
        stat("Tiempo", `${Number(data.elapsed).toFixed(2)}s`)
      ].join("");

      const rows = data.results.map(result => {
        const percent = data.dnsbl_zones ? Math.min(100, Math.round((result.listed_count / data.dnsbl_zones) * 100)) : 0;
        const lists = result.listed_on.slice(0, 5).map(hit => escapeHtml(hit.blacklist)).join(", ");
        const extra = result.listed_on.length > 5 ? ` +${result.listed_on.length - 5}` : "";
        return `<tr>
          <td>${escapeHtml(result.ip)}</td>
          <td><span class="pill ${result.risk_level.toLowerCase()}">${labels[result.risk_level]}</span></td>
          <td>${result.listed_count}</td>
          <td><span class="bar"><span style="width:${percent}%"></span></span></td>
          <td>${lists || "-"}${extra}</td>
        </tr>`;
      }).join("");

      const details = data.results
        .filter(result => result.listed_count > 0)
        .map(result => {
          const hits = result.listed_on.map(hit => {
            const codes = hit.response_codes.length ? hit.response_codes.map(escapeHtml).join(", ") : "-";
            const detail = hit.details.length ? hit.details.map(escapeHtml).join("; ") : "Sin detalle TXT";
            return `<li><strong>${escapeHtml(hit.blacklist)}</strong> <span>${escapeHtml(hit.zone)}</span><code>${codes}</code><p>${detail}</p></li>`;
          }).join("");
          return `<article class="detail ${result.risk_level.toLowerCase()}"><h3>${escapeHtml(result.ip)} ${labels[result.risk_level]}</h3><ul>${hits}</ul></article>`;
        }).join("");

      const links = [
        data.report_path ? `Reporte HTML: ${escapeHtml(data.report_path)}` : "",
        data.json_path ? `JSON: ${escapeHtml(data.json_path)}` : ""
      ].filter(Boolean).join(" | ");

      resultsBox.innerHTML = `
        <section class="stats">${stats}</section>
        <div class="table-wrap"><table>
          <thead><tr><th>IP</th><th>Riesgo</th><th>Hits</th><th>Visual</th><th>Listas negras</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div>
        ${links ? `<div class="links">${links}</div>` : ""}
        <section class="details">${details || '<div class="empty">No se encontraron listados.</div>'}</section>
      `;
    }

    form.addEventListener("submit", async event => {
      event.preventDefault();
      const targets = document.querySelector("#targets").value.split(/\\r?\\n|,/).map(item => item.trim()).filter(Boolean);
      button.disabled = true;
      statusBox.textContent = "Escaneando DNSBL, espera un momento...";

      try {
        const response = await fetch("/api/scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            targets,
            max_hosts: Number(document.querySelector("#max-hosts").value),
            timeout: Number(document.querySelector("#timeout").value),
            concurrency: Number(document.querySelector("#concurrency").value),
            save_report: document.querySelector("#save-report").checked,
            save_json: document.querySelector("#save-json").checked
          })
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "No se pudo ejecutar el escaneo.");
        }
        render(data);
        statusBox.textContent = "Escaneo completado.";
      } catch (error) {
        statusBox.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


REPORT_CSS = """
:root {
  color-scheme: light;
  --bg: #eef3f8;
  --panel: #ffffff;
  --ink: #18212f;
  --muted: #627087;
  --line: #d7e0eb;
  --green: #15803d;
  --yellow: #b45309;
  --red: #be123c;
  --cyan: #1f7a8c;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.45;
}
header {
  padding: 30px clamp(18px, 4vw, 52px) 24px;
  background: #102a43;
  color: white;
}
header h1 { margin: 0 0 8px; font-size: clamp(28px, 4vw, 42px); letter-spacing: 0; }
header p { margin: 0; color: #c8d7e6; }
main { padding: 24px clamp(18px, 4vw, 52px) 44px; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 22px; }
.stat { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
.stat span { display: block; color: var(--muted); font-size: 13px; }
.stat strong { display: block; margin-top: 5px; font-size: 26px; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; margin-bottom: 22px; }
.panel h2 { margin: 0; padding: 16px 18px; font-size: 18px; border-bottom: 1px solid var(--line); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid var(--line); vertical-align: middle; }
th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
.pill { display: inline-flex; min-width: 68px; justify-content: center; border-radius: 999px; padding: 4px 9px; color: white; font-size: 12px; font-weight: 800; }
.low { background: var(--green); }
.medium { background: var(--yellow); }
.high { background: var(--red); }
.bar { display: block; width: min(210px, 34vw); height: 10px; background: #e4ebf3; border-radius: 999px; overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--cyan); }
.detail { background: var(--panel); border: 1px solid var(--line); border-left-width: 5px; border-radius: 8px; margin-bottom: 12px; padding: 16px; }
.detail.high { border-left-color: var(--red); }
.detail.medium { border-left-color: var(--yellow); }
.detail h2 { margin: 0 0 12px; font-size: 18px; }
.detail h2 span { color: var(--muted); font-size: 14px; margin-left: 8px; }
.detail ul { margin: 0; padding-left: 20px; }
.detail li { margin: 0 0 12px; }
.detail li span { color: var(--muted); margin-left: 8px; }
code { display: inline-block; margin-left: 8px; padding: 2px 6px; border-radius: 6px; background: #eaf0f6; }
.detail p { margin: 4px 0 0; color: var(--muted); }
@media (max-width: 760px) {
  table, thead, tbody, tr, th, td { display: block; }
  thead { display: none; }
  tr { border-bottom: 1px solid var(--line); padding: 10px 0; }
  td { border: 0; padding: 6px 14px; }
}
"""


class ListasNegrasHandler(BaseHTTPRequestHandler):
    server_version = "ListasNegrasWeb/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.send_text(APP_HTML, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self.send_json({"status": "ok", "dnsbl_zones": len(DNSBLS)})
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Ruta no encontrada")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/scan":
            self.send_error(HTTPStatus.NOT_FOUND, "Ruta no encontrada")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8")
            options = json.loads(body or "{}")
            payload = asyncio.run(execute_scan(options))
            self.send_json(payload)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except json.JSONDecodeError:
            self.send_json({"error": "Solicitud JSON invalida."}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": f"Error inesperado: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args) -> None:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {format % args}")

    def send_text(self, content: str, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interfaz web local para escanear IPv4 contra DNSBL.")
    parser.add_argument("--host", default="127.0.0.1", help="Host donde se publica la interfaz web")
    parser.add_argument("--port", type=int, default=8000, help="Puerto de la interfaz web")
    parser.add_argument("--no-browser", action="store_true", help="No abrir el navegador automaticamente")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    address = (args.host, args.port)
    httpd = ThreadingHTTPServer(address, ListasNegrasHandler)
    url = f"http://{args.host}:{args.port}"

    print(f"ListasNegras web ejecutandose en {url}")
    print("Presiona Ctrl+C para detener el servidor.")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        httpd.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
