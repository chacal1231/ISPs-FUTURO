#!/usr/bin/env python3
"""Descarga de Gmail los enlaces de abuso enviados por Cogent."""

import argparse
import csv
import html
import http.cookiejar
import imaplib
import os
import re
import sqlite3
import ssl
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import (
    HTTPCookieProcessor,
    Request,
    build_opener,
)


IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
BOGOTA_TZ = timezone(timedelta(hours=-5), name="America/Bogota")
COGENT_URL_RE = re.compile(
    r"https://abuse\.sys\.cogentco\.com[^\s<>\"']*", re.IGNORECASE
)
INTERNALDATE_RE = re.compile(br'INTERNALDATE "([^"]+)"', re.IGNORECASE)
CSV_FIELDS = (
    "fecha_objetivo",
    "uid",
    "message_id",
    "recibido",
    "remitente",
    "asunto",
    "url",
    "post_estado",
    "post_http",
    "post_resultado",
    "post_fecha",
)
VALID_COGENT_PATH_RE = re.compile(r"^/ash/collect/\d+/[A-Za-z0-9]+/?$")
TICKET_STATUS_RE = re.compile(
    r"<dt>\s*Ticket status\s*</dt>\s*<dd>\s*([^<]+?)\s*</dd>", re.IGNORECASE
)
HTTP_TIMEOUT_SECONDS = 30
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: List[str] = []

    def handle_starttag(self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


class CogentPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.csrf_token: Optional[str] = None
        self.text: List[str] = []

    def handle_starttag(self, tag: str, attrs: Sequence[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "input":
            return
        attributes = {name.lower(): value for name, value in attrs}
        if attributes.get("name") == "_token" and attributes.get("value"):
            self.csrf_token = attributes["value"]

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrae enlaces abuse.sys.cogentco.com de correos diarios en Gmail."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--date", help="Fecha a procesar en formato AAAA-MM-DD")
    group.add_argument("--month", help="Mes completo a procesar en formato AAAA-MM")
    group.add_argument(
        "--today", action="store_true", help="Procesar el día actual en vez del anterior"
    )
    group.add_argument(
        "--cron",
        action="store_true",
        help="Modo periódico: procesa hoy y cierra ayer en la primera ronda del día",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Mostrar los registros como CSV y no escribir el archivo de salida",
    )
    parser.add_argument(
        "--no-post",
        action="store_true",
        help="Extraer enlaces sin enviar respuestas a Cogent",
    )
    return parser.parse_args(argv)


def target_date(args: argparse.Namespace, now: Optional[datetime] = None) -> date:
    current = (now or datetime.now(BOGOTA_TZ)).astimezone(BOGOTA_TZ).date()
    if args.date:
        try:
            return datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("--date debe tener el formato AAAA-MM-DD") from exc
    return current if args.today else current - timedelta(days=1)


def processing_range(
    args: argparse.Namespace, now: Optional[datetime] = None
) -> Tuple[date, date, str]:
    if args.month:
        try:
            first_day = datetime.strptime(args.month, "%Y-%m").date().replace(day=1)
        except ValueError as exc:
            raise ValueError("--month debe tener el formato AAAA-MM") from exc
        if first_day.month == 12:
            next_month = first_day.replace(year=first_day.year + 1, month=1)
        else:
            next_month = first_day.replace(month=first_day.month + 1)
        return first_day, next_month, args.month

    wanted_date = target_date(args, now)
    return wanted_date, wanted_date + timedelta(days=1), wanted_date.isoformat()


def cron_processing_ranges(
    now: Optional[datetime] = None,
) -> List[Tuple[date, date, str]]:
    current_time = (now or datetime.now(BOGOTA_TZ)).astimezone(BOGOTA_TZ)
    current = current_time.date()
    ranges: List[Tuple[date, date, str]] = []
    if current_time.hour == 0 and current_time.minute < 30:
        previous = current - timedelta(days=1)
        ranges.append((previous, current, previous.isoformat()))
    ranges.append((current, current + timedelta(days=1), current.isoformat()))
    return ranges


def clean_url(url: str) -> str:
    return html.unescape(url).rstrip(".,;:!?)]}")


def ticket_key(url: str) -> str:
    """Identificador estable del ticket, sin query string ni slash final."""
    parsed = urlsplit(clean_url(url))
    path = parsed.path.rstrip("/") or "/"
    return "https://{}{}".format((parsed.hostname or "").lower(), path)


def extract_cogent_links(text: str, is_html: bool = False) -> List[str]:
    candidates: List[str] = []
    decoded = html.unescape(text)

    if is_html:
        parser = LinkParser()
        try:
            parser.feed(text)
            candidates.extend(parser.hrefs)
        except Exception:
            # Un HTML mal formado no impide buscar URLs en el texto original.
            pass

    candidates.extend(match.group(0) for match in COGENT_URL_RE.finditer(decoded))

    links: List[str] = []
    seen: Set[str] = set()
    for candidate in candidates:
        normalized = clean_url(candidate.strip())
        match = COGENT_URL_RE.match(normalized)
        if not match:
            continue
        normalized = clean_url(match.group(0))
        key = normalized.lower()
        if key not in seen:
            seen.add(key)
            links.append(normalized)
    return links


def message_links(message) -> List[str]:
    links: List[str] = []
    seen: Set[str] = set()

    parts: Iterable = message.walk() if message.is_multipart() else (message,)
    for part in parts:
        if part.get_content_maintype() != "text":
            continue
        if part.get_content_disposition() == "attachment":
            continue
        try:
            content = part.get_content()
        except (LookupError, UnicodeDecodeError):
            payload = part.get_payload(decode=True) or b""
            content = payload.decode("utf-8", errors="replace")
        if not isinstance(content, str):
            content = content.decode("utf-8", errors="replace")

        for link in extract_cogent_links(
            content, is_html=part.get_content_type() == "text/html"
        ):
            key = link.lower()
            if key not in seen:
                seen.add(key)
                links.append(link)
    return links


def exact_sender(message, expected: str) -> bool:
    addresses = getaddresses(message.get_all("From", []))
    return any(address.lower() == expected.lower() for _, address in addresses)


def internal_datetime(fetch_metadata: bytes, message) -> Optional[datetime]:
    match = INTERNALDATE_RE.search(fetch_metadata)
    if match:
        try:
            value = match.group(1).decode("ascii")
            parsed = parsedate_to_datetime(value)
            if parsed:
                return parsed
        except (UnicodeDecodeError, TypeError, ValueError):
            pass

    try:
        parsed = parsedate_to_datetime(str(message.get("Date", "")))
        if parsed:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=BOGOTA_TZ)
            return parsed
    except (TypeError, ValueError):
        pass
    return None


def imap_date(value: date) -> str:
    return value.strftime("%d-%b-%Y")


def normalized_text(value: str) -> str:
    return " ".join(value.split())


def parse_cogent_page(page: str) -> Tuple[Optional[str], str, Optional[str]]:
    parser = CogentPageParser()
    parser.feed(page)
    visible_text = normalized_text(" ".join(parser.text))
    status_match = TICKET_STATUS_RE.search(page)
    ticket_status = html.unescape(status_match.group(1)).strip() if status_match else None
    return parser.csrf_token, visible_text, ticket_status


def validate_cogent_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != "abuse.sys.cogentco.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not VALID_COGENT_PATH_RE.fullmatch(parsed.path)
    ):
        raise ValueError("URL de Cogent no permitida")


def read_http_response(response) -> Tuple[int, str]:
    status = response.getcode()
    charset = response.headers.get_content_charset() or "utf-8"
    body = response.read(MAX_RESPONSE_BYTES)
    return status, body.decode(charset, errors="replace")


def post_cogent_response(url: str, reply_text: str, change_status: str) -> Dict[str, str]:
    attempted_at = datetime.now(BOGOTA_TZ).isoformat(timespec="seconds")
    try:
        validate_cogent_url(url)
        cookie_jar = http.cookiejar.CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookie_jar))
        common_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-US,es-419;q=0.9,es;q=0.8,en;q=0.7",
            "User-Agent": "CorreosCogent/1.0",
        }

        get_request = Request(url, headers=common_headers, method="GET")
        with opener.open(get_request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            get_http, page = read_http_response(response)

        csrf_token, page_text, ticket_status = parse_cogent_page(page)
        wanted_text = normalized_text(reply_text)
        if wanted_text and wanted_text in page_text:
            return {
                "post_estado": "YA_EXISTIA",
                "post_http": str(get_http),
                "post_resultado": "La respuesta ya aparece en la comunicación del ticket",
                "post_fecha": attempted_at,
                "post_exito": "1",
            }
        if ticket_status and ticket_status.lower() in {"resolved", "closed"}:
            return {
                "post_estado": "YA_RESUELTO",
                "post_http": str(get_http),
                "post_resultado": "El ticket ya tiene estado {}".format(ticket_status),
                "post_fecha": attempted_at,
                "post_exito": "1",
            }
        if not csrf_token:
            raise RuntimeError("No se encontró el token CSRF en el formulario")

        body = urlencode(
            {"_token": csrf_token, "text": reply_text, "changeStatus": change_status}
        ).encode("utf-8")
        post_headers = dict(common_headers)
        post_headers.update(
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://abuse.sys.cogentco.com",
                "Referer": url,
            }
        )
        post_request = Request(url, data=body, headers=post_headers, method="POST")
        with opener.open(post_request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            post_http, response_page = read_http_response(response)

        _, response_text, response_status = parse_cogent_page(response_page)
        reply_visible = wanted_text and wanted_text in response_text
        status_changed = (
            change_status == "RESOLVED"
            and response_status
            and response_status.lower() in {"resolved", "closed"}
        )
        if not reply_visible and not status_changed:
            raise RuntimeError(
                "Cogent respondió HTTP {}, pero no confirmó la respuesta".format(post_http)
            )

        return {
            "post_estado": "ENVIADO",
            "post_http": str(post_http),
            "post_resultado": "Respuesta registrada en Cogent",
            "post_fecha": attempted_at,
            "post_exito": "1",
        }
    except HTTPError as exc:
        return {
            "post_estado": "ERROR",
            "post_http": str(exc.code),
            "post_resultado": "HTTP {} al enviar a Cogent".format(exc.code),
            "post_fecha": attempted_at,
            "post_exito": "0",
        }
    except (URLError, OSError, RuntimeError, ValueError) as exc:
        return {
            "post_estado": "ERROR",
            "post_http": "",
            "post_resultado": str(exc),
            "post_fecha": attempted_at,
            "post_exito": "0",
        }


def open_tracking_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=HTTP_TIMEOUT_SECONDS)
    os.chmod(str(path), 0o600)
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cogent_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            fecha_objetivo TEXT NOT NULL,
            gmail_uid TEXT NOT NULL,
            message_id TEXT NOT NULL,
            recibido TEXT NOT NULL,
            ticket_key TEXT NOT NULL,
            url TEXT NOT NULL,
            post_estado TEXT NOT NULL,
            success INTEGER NOT NULL,
            http_status TEXT NOT NULL,
            result TEXT NOT NULL,
            attempted_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cogent_tracking_ticket
        ON cogent_tracking(ticket_key)
        """
    )
    connection.commit()
    return connection


def process_posts(
    records: List[Dict[str, str]],
    tracking_path: Path,
    enabled: bool,
    reply_text: str,
    change_status: str,
) -> int:
    failures = 0
    with open_tracking_database(tracking_path) as connection:
        for record in records:
            if enabled:
                result = post_cogent_response(record["url"], reply_text, change_status)
                record.update(
                    {field: result[field] for field in CSV_FIELDS if field in result}
                )
            else:
                result = {
                    "post_estado": "OMITIDO",
                    "post_http": "",
                    "post_resultado": "Envío deshabilitado",
                    "post_fecha": "",
                    "post_exito": "1",
                }
                record.update(
                    {field: result[field] for field in CSV_FIELDS if field in result}
                )

            connection.execute(
                """
                INSERT INTO cogent_tracking (
                    recorded_at, fecha_objetivo, gmail_uid, message_id, recibido,
                    ticket_key, url, post_estado, success, http_status, result,
                    attempted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(BOGOTA_TZ).isoformat(timespec="seconds"),
                    record.get("fecha_objetivo", ""),
                    record.get("uid", ""),
                    record.get("message_id", ""),
                    record.get("recibido", ""),
                    ticket_key(record["url"]),
                    record["url"],
                    result["post_estado"],
                    int(result["post_exito"]),
                    result["post_http"],
                    result["post_resultado"],
                    result["post_fecha"],
                ),
            )
            connection.commit()
            if result["post_exito"] != "1":
                failures += 1
    return failures


def fetch_records(
    username: str,
    password: str,
    sender: str,
    start_date: date,
    end_date: date,
) -> List[Dict[str, str]]:
    # Se amplía un día a cada lado y luego se valida INTERNALDATE en Bogotá.
    # Así se evitan omisiones en los límites por diferencias de zona horaria.
    since = start_date - timedelta(days=1)
    before = end_date + timedelta(days=1)
    context = ssl.create_default_context()
    records: List[Dict[str, str]] = []

    with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=context) as mailbox:
        mailbox.login(username, password)
        status, _ = mailbox.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("Gmail no permitió abrir INBOX")

        status, result = mailbox.uid(
            "search",
            None,
            "FROM",
            '"{}"'.format(sender),
            "SINCE",
            imap_date(since),
            "BEFORE",
            imap_date(before),
        )
        if status != "OK":
            raise RuntimeError("Gmail no pudo ejecutar la búsqueda IMAP")

        uids = result[0].split() if result and result[0] else []
        for uid_bytes in uids:
            uid = uid_bytes.decode("ascii")
            status, fetched = mailbox.uid("fetch", uid, "(RFC822 INTERNALDATE)")
            if status != "OK" or not fetched:
                print("Advertencia: no se pudo descargar UID {}".format(uid), file=sys.stderr)
                continue

            metadata = b""
            raw_message: Optional[bytes] = None
            for item in fetched:
                if isinstance(item, tuple):
                    metadata += item[0]
                    raw_message = item[1]
            if raw_message is None:
                continue

            message = BytesParser(policy=policy.default).parsebytes(raw_message)
            if not exact_sender(message, sender):
                continue

            received = internal_datetime(metadata, message)
            if received is None:
                continue

            received_bogota = received.astimezone(BOGOTA_TZ)
            received_date = received_bogota.date()
            if not start_date <= received_date < end_date:
                continue

            received_text = received_bogota.isoformat(timespec="seconds")
            for url in message_links(message):
                records.append(
                    {
                        "fecha_objetivo": received_date.isoformat(),
                        "uid": uid,
                        "message_id": str(message.get("Message-ID", "")),
                        "recibido": received_text,
                        "remitente": sender,
                        "asunto": str(message.get("Subject", "")),
                        "url": url,
                    }
                )

        mailbox.logout()

    records.sort(key=lambda row: (row["recibido"], row["uid"], row["url"]))
    unique_records: List[Dict[str, str]] = []
    seen_tickets: Set[str] = set()
    for record in records:
        key = ticket_key(record["url"])
        if key in seen_tickets:
            continue
        seen_tickets.add(key)
        unique_records.append(record)
    return unique_records


def write_csv(records: List[Dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=".{}-".format(output_path.name), dir=str(output_path.parent), text=True
    )
    try:
        os.chmod(temporary_name, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(records)
        os.replace(temporary_name, str(output_path))
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def write_stdout(records: List[Dict[str, str]]) -> None:
    writer = csv.DictWriter(sys.stdout, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(records)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        ranges = cron_processing_ranges() if args.cron else [processing_range(args)]
    except ValueError as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 2

    username = os.environ.get("GMAIL_USER", "").strip()
    # Google presenta las claves de aplicación en grupos; se ignoran esos espacios.
    password = "".join(os.environ.get("GMAIL_APP_PASSWORD", "").split())
    sender = os.environ.get("COGENT_SENDER", "abuse@cogentco.com").strip()
    post_enabled = (
        os.environ.get("COGENT_POST_ENABLED", "true").strip().lower()
        in {"1", "true", "yes", "si", "sí"}
    ) and not args.no_post
    reply_text = os.environ.get(
        "COGENT_REPLY_TEXT", "Hello, already resolved and blocked the client."
    ).strip()
    change_status = os.environ.get("COGENT_CHANGE_STATUS", "RESOLVED").strip().upper()
    missing = [
        name
        for name, value in (("GMAIL_USER", username), ("GMAIL_APP_PASSWORD", password))
        if not value
    ]
    if missing:
        print("Error: faltan variables: {}".format(", ".join(missing)), file=sys.stderr)
        return 2
    if post_enabled and not reply_text:
        print("Error: COGENT_REPLY_TEXT no puede estar vacío", file=sys.stderr)
        return 2
    if change_status not in {"OPEN", "RESOLVED"}:
        print("Error: COGENT_CHANGE_STATUS debe ser OPEN o RESOLVED", file=sys.stderr)
        return 2
    try:
        project_dir = Path(__file__).resolve().parent
        failures = 0
        for start_date, end_date, output_name in ranges:
            records = fetch_records(username, password, sender, start_date, end_date)
            failures += process_posts(
                records,
                project_dir / "state" / "cogent_tracking.sqlite3",
                post_enabled,
                reply_text,
                change_status,
            )
            if args.stdout:
                write_stdout(records)
            else:
                output_path = project_dir / "output" / "{}.csv".format(output_name)
                write_csv(records, output_path)
                print(
                    "{}: {} ticket(s) guardado(s) en {}".format(
                        output_name, len(records), output_path
                    )
                )
        if failures:
            print("Error: {} POST(s) no fueron confirmados".format(failures), file=sys.stderr)
            return 1
        return 0
    except imaplib.IMAP4.error as exc:
        print("Error de autenticación o IMAP en Gmail: {}".format(exc), file=sys.stderr)
        return 1
    except (OSError, RuntimeError, sqlite3.Error) as exc:
        print("Error en la ejecución de Cogent: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
