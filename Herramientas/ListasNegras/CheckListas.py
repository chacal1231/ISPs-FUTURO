from __future__ import annotations

import asyncio
import ipaddress
import time
from dataclasses import dataclass, field
from typing import Iterable

import dns.asyncresolver

CONCURRENCY_LIMIT = 80
DNS_TIMEOUT = 5
DNS_LIFETIME = 5
CACHE_TTL_SECONDS = 300

DNSBLS = {
    "S5H": "all.s5h.net",
    "Barracuda": "b.barracudacentral.org",
    "Spamcop": "bl.spamcop.net",
    "Woody": "blacklist.woody.ch",
    "Cymru Bogons": "bogons.cymru.com",
    "CBL": "cbl.abuseat.org",
    "Combined Abuse CH": "combined.abuse.ch",
    "WPBL": "db.wpbl.info",
    "UCEProtect L1": "dnsbl-1.uceprotect.net",
    "UCEProtect L2": "dnsbl-2.uceprotect.net",
    "UCEProtect L3": "dnsbl-3.uceprotect.net",
    "AntiCaptcha": "dnsbl.anticaptcha.net",
    "DroneBL": "dnsbl.dronebl.org",
    "INPS": "dnsbl.inps.de",
    "SORBS": "dnsbl.sorbs.net",
    "SPFBL": "dnsbl.spfbl.net",
    "Drone Abuse CH": "drone.abuse.ch",
    "Duinv Aupads": "duinv.aupads.org",
    "SORBS DUL": "dul.dnsbl.sorbs.net",
    "RATS Dyna": "dyna.spamrats.com",
    "DynIP Rothen": "dynip.rothen.com",
    "SORBS HTTP": "http.dnsbl.sorbs.net",
    "Backscatterer": "ips.backscatterer.org",
    "Manitu": "ix.dnsbl.manitu.net",
    "Korea Services": "korea.services.net",
    "SORBS Misc": "misc.dnsbl.sorbs.net",
    "RATS NoPtr": "noptr.spamrats.com",
    "Orvedb Aupads": "orvedb.aupads.org",
    "Spamhaus PBL": "pbl.spamhaus.org",
    "Gweep Proxy": "proxy.bl.gweep.ca",
    "PSBL": "psbl.surriel.com",
    "Gweep Relays": "relays.bl.gweep.ca",
    "Nether Relays": "relays.nether.net",
    "Spamhaus SBL": "sbl.spamhaus.org",
    "RBL JP Short": "short.rbl.jp",
    "Singular TTK": "singular.ttk.pte.hu",
    "SORBS SMTP": "smtp.dnsbl.sorbs.net",
    "SORBS SOCKS": "socks.dnsbl.sorbs.net",
    "Spam Abuse CH": "spam.abuse.ch",
    "Anonmails": "spam.dnsbl.anonmails.de",
    "SORBS Spam": "spam.dnsbl.sorbs.net",
    "RATS Spam": "spam.spamrats.com",
    "Digibase Spambot": "spambot.bls.digibase.ca",
    "SpamRBL IMP": "spamrbl.imp.ch",
    "Spamsources Fabel": "spamsources.fabel.dk",
    "Lashback UBL": "ubl.lashback.com",
    "Unsubscore": "ubl.unsubscore.com",
    "RBL JP Virus": "virus.rbl.jp",
    "SORBS Web": "web.dnsbl.sorbs.net",
    "WormRBL IMP": "wormrbl.imp.ch",
    "Spamhaus XBL": "xbl.spamhaus.org",
    "Mailspike Z": "z.mailspike.net",
    "Spamhaus ZEN": "zen.spamhaus.org",
    "Mailspike BL": "bl.mailspike.net",
    "SEM Black": "bl.spameatingmonkey.net",
    "Invaluement": "dnsbl.invaluement.com",
    "Hostkarma Black": "black.hostkarma.com",
    "Nordspam": "dbl.nordspam.com",
    "Truncate": "truncate.gbudb.net",
    "JustSpam": "dnsbl.justspam.org",
    "Kempt": "dnsbl.kempt.net",
    "SpamRATS Auth": "auth.spamrats.com",
    "Mailspike Rep": "rep.mailspike.net",
    "Blocklist.de": "bl.blocklist.de",
    "Interserver": "rbl.interserver.net",
    "Megarbl": "megarbl.net",
    "SORBS New Spam": "new.spam.dnsbl.sorbs.net",
}

_cache: dict[str, tuple[float, "DNSBLHit | None"]] = {}


@dataclass(frozen=True)
class DNSBLHit:
    blacklist: str
    zone: str
    response_codes: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "blacklist": self.blacklist,
            "zone": self.zone,
            "response_codes": self.response_codes,
            "details": self.details,
        }


@dataclass(frozen=True)
class IPScanResult:
    ip: str
    listed_count: int
    risk_level: str
    listed_on: list[DNSBLHit] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "listed_count": self.listed_count,
            "risk_level": self.risk_level,
            "listed_on": [hit.to_dict() for hit in self.listed_on],
        }


def build_resolver(timeout: int = DNS_TIMEOUT, lifetime: int = DNS_LIFETIME):
    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = timeout
    resolver.lifetime = lifetime
    return resolver


def reverse_ip(ip: str) -> str:
    parsed = ipaddress.ip_address(ip)
    if parsed.version != 4:
        raise ValueError("Only IPv4 addresses are supported by DNSBL zones")
    return ".".join(reversed(str(parsed).split(".")))


def calculate_risk(count: int) -> str:
    if count == 0:
        return "LOW"
    if count <= 2:
        return "MEDIUM"
    return "HIGH"


def expand_targets(targets: Iterable[str], max_hosts: int = 256) -> list[str]:
    ips: list[str] = []
    seen: set[str] = set()

    for raw_target in targets:
        target = raw_target.strip()
        if not target or target.startswith("#"):
            continue

        try:
            if "/" in target:
                network = ipaddress.ip_network(target, strict=False)
                if network.version != 4:
                    continue
                hosts = [str(ip) for ip in network.hosts()]
                if len(hosts) > max_hosts:
                    raise ValueError(
                        f"{target} expands to {len(hosts)} hosts; raise --max-hosts to allow it"
                    )
            else:
                address = ipaddress.ip_address(target)
                if address.version != 4:
                    continue
                hosts = [str(address)]
        except ValueError as exc:
            raise ValueError(f"Invalid target {target!r}: {exc}") from exc

        for ip in hosts:
            if ip not in seen:
                seen.add(ip)
                ips.append(ip)

    return ips


async def check_single_dnsbl(
    ip: str,
    name: str,
    zone: str,
    resolver,
    semaphore: asyncio.Semaphore,
) -> DNSBLHit | None:
    cache_key = f"{ip}:{zone}"
    cached = _cache.get(cache_key)
    now = time.monotonic()

    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    query = f"{reverse_ip(ip)}.{zone}"

    async with semaphore:
        try:
            a_task = resolver.resolve(query, "A")
            txt_task = resolver.resolve(query, "TXT")
            a_result, txt_result = await asyncio.gather(
                a_task,
                txt_task,
                return_exceptions=True,
            )

            if isinstance(a_result, Exception):
                _cache[cache_key] = (now, None)
                return None

            response_codes = [rdata.to_text() for rdata in a_result]
            valid_codes = [code for code in response_codes if code.startswith("127.")]
            if not valid_codes:
                _cache[cache_key] = (now, None)
                return None

            details: list[str] = []
            if not isinstance(txt_result, Exception):
                for txt in txt_result:
                    for value in txt.strings:
                        details.append(
                            value.decode(errors="replace")
                            if isinstance(value, bytes)
                            else str(value)
                        )

            result = DNSBLHit(
                blacklist=name,
                zone=zone,
                response_codes=valid_codes,
                details=details,
            )
            _cache[cache_key] = (now, result)
            return result
        except Exception:
            _cache[cache_key] = (now, None)
            return None


async def check_ip(
    ip: str,
    resolver=None,
    semaphore: asyncio.Semaphore | None = None,
    dnsbls: dict[str, str] | None = None,
) -> IPScanResult:
    resolver = resolver or build_resolver()
    semaphore = semaphore or asyncio.Semaphore(CONCURRENCY_LIMIT)
    zones = dnsbls or DNSBLS

    tasks = [
        check_single_dnsbl(ip, name, zone, resolver, semaphore)
        for name, zone in zones.items()
    ]
    results = await asyncio.gather(*tasks)
    listed_on = [result for result in results if result is not None]

    return IPScanResult(
        ip=ip,
        listed_count=len(listed_on),
        risk_level=calculate_risk(len(listed_on)),
        listed_on=listed_on,
    )


async def scan_targets(
    targets: Iterable[str],
    *,
    concurrency: int = CONCURRENCY_LIMIT,
    timeout: int = DNS_TIMEOUT,
    lifetime: int = DNS_LIFETIME,
    max_hosts: int = 256,
    dnsbls: dict[str, str] | None = None,
) -> list[IPScanResult]:
    ips = expand_targets(targets, max_hosts=max_hosts)
    resolver = build_resolver(timeout=timeout, lifetime=lifetime)
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        check_ip(ip, resolver=resolver, semaphore=semaphore, dnsbls=dnsbls)
        for ip in ips
    ]
    return await asyncio.gather(*tasks)
