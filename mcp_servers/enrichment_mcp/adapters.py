"""Modular enrichment adapters.

Pattern: each provider is a class with `available()` and `enrich(value, ioc_type)`.
The MCP server iterates over registered adapters; adding a new source is a
matter of writing one more adapter class and adding it to the list at the
bottom of this file.
"""
from __future__ import annotations

import hashlib
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx

log = logging.getLogger(__name__)


class EnrichmentAdapter(ABC):
    name: str = ""

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def enrich(self, value: str, ioc_type: str) -> Dict[str, Any]: ...


# ---------------------------------------------------------------------
# Helpers — deterministic mock so the same IOC always returns the same
# verdict (good for caching + reproducible demos).
# ---------------------------------------------------------------------

def _stable_score(value: str, *, lo: int, hi: int) -> int:
    h = int(hashlib.sha256(value.encode()).hexdigest()[:8], 16)
    return lo + (h % (hi - lo + 1))


def _mock_response(provider: str, value: str, ioc_type: str, **extra) -> Dict[str, Any]:
    return {
        "provider": provider,
        "mode": "mock",
        "ioc_value": value,
        "ioc_type": ioc_type,
        **extra,
        "note": (
            f"Synthetic enrichment. Set the {provider.upper()}_API_KEY env "
            "var to query the live API."
        ),
    }


# ---------------------------------------------------------------------
# VirusTotal
# ---------------------------------------------------------------------
class VirusTotalAdapter(EnrichmentAdapter):
    name = "virustotal"

    def __init__(self) -> None:
        self.api_key = os.getenv("VIRUSTOTAL_API_KEY", "")

    def available(self) -> bool:
        return bool(self.api_key)

    def enrich(self, value: str, ioc_type: str) -> Dict[str, Any]:
        if not self.available():
            malicious = _stable_score(value, lo=0, hi=15)
            total = 70
            return _mock_response(
                "virustotal", value, ioc_type,
                stats={"malicious": malicious, "suspicious": _stable_score(value + "s", lo=0, hi=5),
                       "harmless": total - malicious, "total_engines": total},
                reputation=_stable_score(value, lo=-50, hi=20),
                last_analysis_date="2025-04-15T00:00:00Z",
            )

        try:
            endpoint = self._endpoint(value, ioc_type)
            if not endpoint:
                return {"provider": self.name, "error": f"unsupported ioc_type: {ioc_type}"}
            with httpx.Client(timeout=15) as c:
                r = c.get(endpoint, headers={"x-apikey": self.api_key})
                r.raise_for_status()
                data = r.json().get("data", {}).get("attributes", {})
            return {
                "provider": self.name,
                "mode": "live",
                "ioc_value": value,
                "ioc_type": ioc_type,
                "stats": data.get("last_analysis_stats", {}),
                "reputation": data.get("reputation"),
                "last_analysis_date": data.get("last_analysis_date"),
            }
        except Exception as e:  # noqa: BLE001
            log.error("VT live call failed: %s", e)
            return {"provider": self.name, "error": str(e), "mode": "live_failed"}

    def _endpoint(self, value: str, ioc_type: str) -> Optional[str]:
        base = "https://www.virustotal.com/api/v3"
        if ioc_type == "ipv4":
            return f"{base}/ip_addresses/{value}"
        if ioc_type == "domain":
            return f"{base}/domains/{value}"
        if ioc_type in ("md5", "sha1", "sha256"):
            return f"{base}/files/{value}"
        if ioc_type == "url":
            import base64 as _b
            url_id = _b.urlsafe_b64encode(value.encode()).decode().rstrip("=")
            return f"{base}/urls/{url_id}"
        return None


# ---------------------------------------------------------------------
# AbuseIPDB
# ---------------------------------------------------------------------
class AbuseIPDBAdapter(EnrichmentAdapter):
    name = "abuseipdb"

    def __init__(self) -> None:
        self.api_key = os.getenv("ABUSEIPDB_API_KEY", "")

    def available(self) -> bool:
        return bool(self.api_key)

    def enrich(self, value: str, ioc_type: str) -> Dict[str, Any]:
        if ioc_type not in ("ipv4", "ipv6"):
            return {"provider": self.name, "error": "AbuseIPDB only supports IPs"}

        if not self.available():
            confidence = _stable_score(value, lo=0, hi=100)
            return _mock_response(
                "abuseipdb", value, ioc_type,
                abuse_confidence_score=confidence,
                country_code="US" if confidence < 50 else "RU",
                isp="Synthetic ISP",
                total_reports=_stable_score(value + "r", lo=0, hi=200),
            )

        try:
            with httpx.Client(timeout=15) as c:
                r = c.get(
                    "https://api.abuseipdb.com/api/v2/check",
                    params={"ipAddress": value, "maxAgeInDays": 90},
                    headers={"Key": self.api_key, "Accept": "application/json"},
                )
                r.raise_for_status()
                d = r.json().get("data", {})
            return {
                "provider": self.name,
                "mode": "live",
                "ioc_value": value,
                "ioc_type": ioc_type,
                "abuse_confidence_score": d.get("abuseConfidenceScore"),
                "country_code": d.get("countryCode"),
                "isp": d.get("isp"),
                "total_reports": d.get("totalReports"),
            }
        except Exception as e:  # noqa: BLE001
            log.error("AbuseIPDB live call failed: %s", e)
            return {"provider": self.name, "error": str(e), "mode": "live_failed"}


# ---------------------------------------------------------------------
# Recorded Future (mock-only by default — RF API is paid + bespoke)
# ---------------------------------------------------------------------
class RecordedFutureAdapter(EnrichmentAdapter):
    name = "recordedfuture"

    def __init__(self) -> None:
        self.api_key = os.getenv("RECORDEDFUTURE_API_KEY", "")

    def available(self) -> bool:
        return bool(self.api_key)

    def enrich(self, value: str, ioc_type: str) -> Dict[str, Any]:
        # Even with key set, return structured mock for portfolio safety.
        risk = _stable_score(value, lo=0, hi=99)
        criticality = "Malicious" if risk > 65 else "Suspicious" if risk > 35 else "Informational"
        return _mock_response(
            "recordedfuture", value, ioc_type,
            risk_score=risk,
            criticality=criticality,
            evidence_details=[
                {"rule": "Historically Reported as a Threat Actor IP",
                 "evidence_string": f"Linked to threat actor activity (score={risk})"},
                {"rule": "Recently Active C&C Server",
                 "evidence_string": "Active in last 30 days"},
            ],
        )


# ---------------------------------------------------------------------
# Registered providers — append new ones here.
# ---------------------------------------------------------------------
ADAPTERS = [
    VirusTotalAdapter(),
    AbuseIPDBAdapter(),
    RecordedFutureAdapter(),
]


def get_adapter(name: str) -> Optional[EnrichmentAdapter]:
    for a in ADAPTERS:
        if a.name == name:
            return a
    return None
