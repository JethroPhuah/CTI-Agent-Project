"""Synthetic CTI report generator used as a deterministic seed when
RSS feeds are unreachable in the demo environment.

Each report is realistic enough to exercise extractors (mentions IOCs,
CVEs, threat actors, malware families) without requiring network access.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from ingestion.extractors import extract_all
from ingestion.rss_ingestor import CTIDocument, _hash_id


_TEMPLATES = [
    {
        "title": "APT41 Pivots to Cloud Targets via ShadowPad and Cobalt Strike",
        "source": "Synthetic CTI",
        "body": (
            "Researchers attribute a recent intrusion campaign to APT41, a "
            "Chinese-nexus dual-purpose threat actor. The group leveraged "
            "ShadowPad and Cobalt Strike beacons hosted on attacker-controlled "
            "infrastructure (185.12.45.78, evil-cdn.example.org). Initial "
            "access exploited CVE-2023-3519 against unpatched Citrix appliances. "
            "Post-exploitation activity included PowerShell, PsExec, and "
            "Mimikatz to harvest credentials from cloud admin workstations. "
            "Indicators include MD5 hash 5f4dcc3b5aa765d61d8327deb882cf99 and "
            "SHA-256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855."
        ),
    },
    {
        "title": "LockBit Affiliate Deploys Conti-Style Ransomware Against Healthcare",
        "source": "Synthetic CTI",
        "body": (
            "A LockBit affiliate compromised a regional healthcare provider "
            "via a phishing email referencing CVE-2024-21412. Initial dropper "
            "deployed IcedID, followed by Cobalt Strike, BloodHound, and "
            "ultimately the LockBit 3.0 (Black) encryptor. C2 traffic was "
            "observed to 91.92.249.110 and lockbitsupp[.]com. Threat actor "
            "exhibits TTP overlap with Conti and BlackBasta. Samples: SHA-1 "
            "da39a3ee5e6b4b0d3255bfef95601890afd80709."
        ),
    },
    {
        "title": "Volt Typhoon Targets US Critical Infrastructure with Living-Off-the-Land",
        "source": "Synthetic CTI",
        "body": (
            "CISA and partner agencies confirmed Volt Typhoon, a PRC state-"
            "sponsored actor, has pre-positioned access in US critical "
            "infrastructure networks. The intrusion set favors living-off-the-"
            "land binaries (netsh, wmic, ntdsutil) and a custom web shell. "
            "Public-facing Fortinet appliances vulnerable to CVE-2022-42475 "
            "served as initial access. Domains observed: cdn-update[.]net, "
            "telemetry-sync[.]com. Recommended mitigations align with MITRE "
            "ATT&CK techniques T1078 (Valid Accounts) and T1059.001 (PowerShell)."
        ),
    },
    {
        "title": "Lazarus Group Resurfaces with Dream Job Campaign Targeting Aerospace",
        "source": "Synthetic CTI",
        "body": (
            "DPRK-attributed Lazarus Group is running a renewed Operation "
            "Dream Job campaign against aerospace and defense contractors. "
            "Spear-phishing lures impersonate recruiter messages on LinkedIn, "
            "delivering a trojanized PDF that drops PlugX. Secondary tooling "
            "includes a custom variant of Manuscrypt and a Sliver implant. "
            "Infrastructure: 198.51.100.42, 203.0.113.18, recruit-aero[.]net. "
            "CVE-2023-23397 was used for credential theft against on-prem "
            "Outlook clients."
        ),
    },
    {
        "title": "FIN7 Returns with Black Basta Ransomware-as-a-Service Affiliations",
        "source": "Synthetic CTI",
        "body": (
            "FIN7 has been observed working as an initial access broker for "
            "Black Basta and Conti successors. The actor uses Carbanak-style "
            "spearphishing and Brute Ratel C4 frameworks. Persistence is "
            "achieved through scheduled tasks and a custom AsyncRAT variant. "
            "Network indicators include 45.135.232.94 and badactor-cdn[.]xyz. "
            "Vulnerabilities exploited: CVE-2023-27532 (Veeam) and "
            "CVE-2024-1709 (ConnectWise ScreenConnect)."
        ),
    },
    {
        "title": "Kimsuky Phishing Campaign Targets South Korean Think Tanks",
        "source": "Synthetic CTI",
        "body": (
            "DPRK-aligned Kimsuky continues credential-theft operations "
            "against South Korean academics and policy researchers. The "
            "campaign delivers a malicious HWP document that exploits "
            "CVE-2022-41128 to deploy a custom backdoor. C2: kimsuky-news[.]com, "
            "203.0.113.99. Tooling overlap with Charming Kitten suggests "
            "shared infrastructure access."
        ),
    },
    {
        "title": "Mustang Panda Deploys PlugX Variant Against EU Diplomatic Targets",
        "source": "Synthetic CTI",
        "body": (
            "Mustang Panda (also tracked as RedDelta) has been observed "
            "delivering an updated PlugX variant against EU diplomatic "
            "missions. The lure document references EU-China summit "
            "preparations and exploits CVE-2023-38831 in WinRAR. Post-exploit "
            "tooling includes Cobalt Strike beacons and a custom credential "
            "stealer. C2 IPs: 192.0.2.55 and 198.51.100.77."
        ),
    },
    {
        "title": "BlackCat (ALPHV) Decommission and Successor Group Activity",
        "source": "Synthetic CTI",
        "body": (
            "Following the FBI takedown of BlackCat/ALPHV infrastructure, "
            "former affiliates have been observed regrouping under RansomHub. "
            "Initial access vectors include SocGholish drive-by-downloads "
            "and exploitation of CVE-2024-3400 (PAN-OS). Tooling: Sliver, "
            "Mimikatz, Rubeus, AdFind. Hashes observed: SHA-256 "
            "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08."
        ),
    },
    {
        "title": "Cl0p Mass Exploitation of MOVEit Successors Continues",
        "source": "Synthetic CTI",
        "body": (
            "Cl0p ransomware operators are again leveraging zero-day "
            "exploitation of file-transfer software, this time targeting "
            "Cleo MFT products via CVE-2024-50623. Data exfiltration is "
            "observed prior to encryption. Cl0p historically operates from "
            "infrastructure overlapping FIN11. Domains: cleo-data-leak[.]onion, "
            "cl0p-leak[.]top."
        ),
    },
    {
        "title": "Salt Typhoon Compromise of US Telecommunications Providers",
        "source": "Synthetic CTI",
        "body": (
            "Salt Typhoon, a PRC state-sponsored intrusion set, has gained "
            "long-term access to multiple US telecommunications providers. "
            "The actors exploited Cisco IOS XE devices via CVE-2023-20198 "
            "and used custom implants for traffic mirroring. Tooling overlaps "
            "with prior Volt Typhoon and Flax Typhoon operations."
        ),
    },
]


def generate() -> List[CTIDocument]:
    docs: List[CTIDocument] = []
    base = datetime.now(timezone.utc)
    for i, t in enumerate(_TEMPLATES):
        url = f"https://synthetic.local/cti/report-{i+1:03d}"
        meta = extract_all(t["body"])
        docs.append(CTIDocument(
            doc_id=_hash_id(url),
            source=t["source"],
            url=url,
            title=t["title"],
            published_at=(base - timedelta(days=i)).isoformat(),
            clean_text=t["body"],
            metadata=meta,
        ))
    return docs


if __name__ == "__main__":
    for d in generate():
        print(f"- [{d.published_at[:10]}] {d.title}")
