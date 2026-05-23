import httpx

from .schemas import Advisory, AffectedRange

_OSV_URL = "https://api.osv.dev/v1"


async def fetch_advisories(name: str, ecosystem: str, timeout: int = 10) -> list[Advisory]:
    payload = {"package": {"name": name, "ecosystem": ecosystem}}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{_OSV_URL}/query", json=payload)
        r.raise_for_status()
    return [_parse(v, name, ecosystem) for v in r.json().get("vulns", [])]


def _parse(v: dict, package: str, ecosystem: str) -> Advisory:
    aliases = v.get("aliases", [])

    # OSV stores severity in database_specific for many ecosystems
    db_specific = v.get("database_specific", {})
    severity = db_specific.get("severity")

    # Fall back to CVSS vector severity if present
    if not severity:
        for s in v.get("severity", []):
            score_str = s.get("score", "")
            # CVSS:3.1/AV:N/... — extract base score from vector if numeric score absent
            if s.get("type") in ("CVSS_V3", "CVSS_V2") and "/" not in score_str:
                try:
                    val = float(score_str)
                    severity = _cvss_to_label(val)
                except ValueError:
                    pass
            break

    ranges: list[AffectedRange] = []
    fixed_version: str | None = None

    for affected in v.get("affected", []):
        pkg = affected.get("package", {})
        if pkg.get("name", "").lower() != package.lower():
            continue
        for r in affected.get("ranges", []):
            if r.get("type") != "ECOSYSTEM":
                continue
            intro = fixed = None
            for event in r.get("events", []):
                if "introduced" in event:
                    intro = event["introduced"]
                if "fixed" in event:
                    fixed = event["fixed"]
                    if fixed_version is None:
                        fixed_version = fixed
            ranges.append(AffectedRange(introduced=intro, fixed=fixed))

    refs = [ref["url"] for ref in v.get("references", []) if "url" in ref]

    return Advisory(
        id=v.get("id", ""),
        aliases=aliases,
        summary=v.get("summary", ""),
        details=v.get("details", ""),
        severity=severity,
        affected_ranges=ranges,
        fixed_version=fixed_version,
        published=v.get("published"),
        references=refs[:5],
        package=package,
        ecosystem=ecosystem,
    )


def _cvss_to_label(score: float) -> str:
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    return "LOW"
