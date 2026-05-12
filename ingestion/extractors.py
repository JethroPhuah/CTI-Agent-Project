"""Lightweight regex + dictionary-based extractors for IOCs and threat
actors. Designed to be cheap to run on every chunk during ingestion so
the metadata is available for downstream graph/IOC enrichment.
"""
from __future__ import annotations

import re
from typing import Dict, List

import iocextract

# A small seed list of high-frequency threat actors. Extend as needed;
# the LangGraph retrieval agent will fall back to the Neo4j KG for
# anything not in this dictionary.
_THREAT_ACTORS = {
    "APT1", "APT3", "APT10", "APT28", "APT29", "APT32", "APT33", "APT34",
    "APT37", "APT38", "APT39", "APT40", "APT41",
    "Lazarus", "Lazarus Group", "Kimsuky", "FIN7", "FIN8", "FIN11",
    "Cobalt Group", "Carbanak", "Sandworm", "Turla", "Equation Group",
    "Conti", "LockBit", "REvil", "BlackCat", "ALPHV", "BlackBasta",
    "Cl0p", "RansomHub", "Royal", "Akira", "Play", "Volt Typhoon",
    "Salt Typhoon", "Flax Typhoon", "Mustang Panda", "Bitter",
    "Charming Kitten", "Magic Hound",
}

_MALWARE_FAMILIES = {
    "Cobalt Strike", "Mimikatz", "Emotet", "TrickBot", "QakBot", "QBot",
    "IcedID", "Bazar", "BumbleBee", "PlugX", "ShadowPad", "Winnti",
    "Sliver", "Brute Ratel", "AsyncRAT", "DarkComet", "njRAT",
    "PoisonIvy", "Gh0st RAT", "FlawedAmmyy", "BlackEnergy", "Industroyer",
    "WannaCry", "NotPetya", "Stuxnet", "Triton", "TRITON",
    "Ryuk", "Maze", "DoppelPaymer", "Sodinokibi",
}

_TOOL_NAMES = {
    "PowerShell", "PsExec", "Bloodhound", "SharpHound", "Rubeus",
    "Impacket", "Metasploit", "Empire", "Covenant", "Havoc", "Nighthawk",
    "Nmap", "Mimikatz", "ProcDump", "Responder", "Certify", "Certipy",
    "AdFind", "Advanced IP Scanner", "Anydesk", "TeamViewer",
}


def extract_iocs(text: str) -> Dict[str, List[str]]:
    """Extract IPs, domains, URLs, hashes, emails, CVEs."""
    return {
        "ipv4": sorted(set(iocextract.extract_ipv4s(text, refang=True))),
        "domains": sorted(set(iocextract.extract_urls(text, refang=True))),
        "urls": sorted(set(iocextract.extract_urls(text, refang=True))),
        "hashes_md5": sorted(set(iocextract.extract_md5_hashes(text))),
        "hashes_sha1": sorted(set(iocextract.extract_sha1_hashes(text))),
        "hashes_sha256": sorted(set(iocextract.extract_sha256_hashes(text))),
        "emails": sorted(set(iocextract.extract_emails(text, refang=True))),
        "cves": sorted(set(re.findall(r"CVE-\d{4}-\d{4,7}", text, re.IGNORECASE))),
    }


def _find_terms(text: str, vocabulary: set) -> List[str]:
    found = []
    lower = text.lower()
    for term in vocabulary:
        # Word-boundary regex; case-insensitive
        if re.search(rf"\b{re.escape(term)}\b", lower, re.IGNORECASE):
            found.append(term)
    return sorted(set(found))


def extract_threat_actors(text: str) -> List[str]:
    return _find_terms(text, _THREAT_ACTORS)


def extract_malware(text: str) -> List[str]:
    return _find_terms(text, _MALWARE_FAMILIES)


def extract_tools(text: str) -> List[str]:
    return _find_terms(text, _TOOL_NAMES)


def extract_all(text: str) -> Dict[str, object]:
    return {
        "iocs": extract_iocs(text),
        "threat_actors": extract_threat_actors(text),
        "malware": extract_malware(text),
        "tools": extract_tools(text),
    }
