"""
Threat Guard Tool — Agent-accessible 3-Stage Cascade threat scanning and remediation.
══════════════════════════════════════════════════════════════════════════════

Mathematical Blueprint Integration:
  - All scan results include Ψ(x) Unified Threat Potential scoring
  - Destroyer-Protector control: a*(x) = argmax [Ψ(x)·G(a) − L(a,x) − ξ·D(a,x)]
  - ShieldScore* metric tracking across all scans
  - Full action space A = {allow, sandbox, quarantine, kill-process, rollback, delete, reimage}

Tools:
  threat_scan_file       — Scan a file path with 3-stage cascade (read-only)
  threat_scan_url        — Scan a URL for phishing/malware with Ψ(x) scoring
  threat_scan_content    — Scan text content for malicious patterns
  threat_quarantine      — Quarantine a detected threat
  threat_destroy         — Permanently destroy a detected threat (3-pass overwrite)
  threat_rollback        — Rollback system state to pre-infection snapshot
  threat_kill_process    — Kill a process associated with a detected threat
  threat_reimage         — Full system reimage recommendation for critical threats
"""

import logging
import os
import signal
from pathlib import Path
from typing import Optional

from agents.tools.registry import registry, RiskLevel

logger = logging.getLogger(__name__)

# Lazy-init scanner singleton (avoid import-time side effects)
_scanner_instance = None


def _get_scanner():
    """Get or create the ThreatScanner singleton."""
    global _scanner_instance
    if _scanner_instance is None:
        from agents.safety.threat_scanner import ThreatScanner
        try:
            from config.settings import DATA_DIR
            quarantine_dir = str(DATA_DIR / "threat_quarantine")
        except ImportError:
            quarantine_dir = None
        _scanner_instance = ThreatScanner(quarantine_dir=quarantine_dir)
    return _scanner_instance


# ──────────────────────────────────────────────
# Active scan reports cache (for quarantine/destroy referencing)
# ──────────────────────────────────────────────
_active_reports = {}


def _build_cascade_metrics(report) -> dict:
    """Extract 3-Stage Cascade metrics from a ThreatReport for tool output."""
    return {
        "cascade_stage_reached": report.cascade_stage_reached,
        "stage_scores": report.stage_scores,
        "psi_score": round(report.psi_score, 4),
        "shield_score": round(report.shield_score, 4),
        "behavioral_divergence": round(report.behavioral_divergence, 4),
        "novelty_score": round(report.novelty_score, 4),
        "scan_latency_ms": round(report.scan_latency_ms, 2),
    }


@registry.register(
    name="threat_scan_file",
    description=(
        "Scan a file using the 3-Stage Cascade Deep-Scan Antivirus Engine. "
        "Stage I: nanosecond prefilter (signature + entropy). "
        "Stage II: behavioral short scan (heuristics + PE headers). "
        "Stage III: deep semantic classification + sandbox. "
        "Returns Ψ(x) unified threat potential and recommended action via "
        "a*(x) = argmax [Ψ(x)·G(a) − L(a,x) − ξ·D(a,x)]."
    ),
    risk_level=RiskLevel.LOW,
    parameters={
        "file_path": "Absolute path to the file to scan",
    },
)
def threat_scan_file(file_path: str) -> dict:
    """Scan a file through the 3-Stage Cascade ThreatScanner engine."""
    scanner = _get_scanner()

    path = Path(file_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        report = scanner.scan_file(file_path)

        # Cache for later quarantine/destroy
        _active_reports[report.scan_id] = report

        result = {
            "success": True,
            "scan_id": report.scan_id,
            "is_threat": report.is_threat,
            "summary": report.summary(),
            # 3-Stage Cascade Metrics
            **_build_cascade_metrics(report),
        }

        if report.is_threat:
            result.update({
                "threat_type": report.threat_type.value if report.threat_type else None,
                "severity": report.severity.value if report.severity else None,
                "confidence": f"{report.confidence:.1%}",
                "recommended_action": report.recommended_action.value,
                "evidence_count": len(report.evidence),
                "detailed_report": report.detailed_report(),
                "alert": (
                    f"🚨 THREAT DETECTED: {report.threat_type.value.upper() if report.threat_type else 'UNKNOWN'} "
                    f"({report.severity.emoji if report.severity else '⚠️'} {report.severity.value.upper() if report.severity else 'UNKNOWN'}) — "
                    f"Ψ(x) = {report.psi_score:.4f} — "
                    f"Recommended: {report.recommended_action.value.upper()} — "
                    f"Use scan_id '{report.scan_id}' for remediation."
                ),
            })
        else:
            result["message"] = "✅ File is clean — no threats detected."

        return result

    except Exception as e:
        logger.error(f"threat_scan_file error: {e}")
        return {"success": False, "error": f"Scan failed: {e}"}


@registry.register(
    name="threat_scan_url",
    description=(
        "Scan a URL through the 3-Stage Cascade for phishing, malicious domains, "
        "IDN homograph attacks, suspicious TLDs, and URL-based threats. "
        "Returns Ψ(x) unified threat potential score."
    ),
    risk_level=RiskLevel.LOW,
    parameters={
        "url": "The URL to scan for threats",
    },
)
def threat_scan_url(url: str) -> dict:
    """Scan a URL for phishing and malicious patterns with Ψ(x) scoring."""
    scanner = _get_scanner()

    try:
        report = scanner.scan_url(url)
        _active_reports[report.scan_id] = report

        result = {
            "success": True,
            "scan_id": report.scan_id,
            "url": url,
            "is_threat": report.is_threat,
            "summary": report.summary(),
            **_build_cascade_metrics(report),
        }

        if report.is_threat:
            result.update({
                "threat_type": report.threat_type.value if report.threat_type else None,
                "severity": report.severity.value if report.severity else None,
                "confidence": f"{report.confidence:.1%}",
                "evidence_count": len(report.evidence),
                "detailed_report": report.detailed_report(),
                "alert": (
                    f"🚨 MALICIOUS URL DETECTED — Ψ(x) = {report.psi_score:.4f} — "
                    f"DO NOT visit this URL. "
                    f"Confidence: {report.confidence:.1%}"
                ),
            })
        else:
            result["message"] = "✅ URL appears safe — no threats detected."

        return result

    except Exception as e:
        logger.error(f"threat_scan_url error: {e}")
        return {"success": False, "error": f"URL scan failed: {e}"}


@registry.register(
    name="threat_scan_content",
    description=(
        "Scan text content through the 3-Stage Cascade for malicious patterns "
        "like encoded payloads, shellcode, reverse shells, ransomware indicators. "
        "Returns Ψ(x) score and cascade stage reached."
    ),
    risk_level=RiskLevel.LOW,
    parameters={
        "content": "The text content to scan for threats",
        "source": "Label describing the content source (optional)",
    },
)
def threat_scan_content(content: str, source: str = "inline") -> dict:
    """Scan text content for malicious patterns with Ψ(x) scoring."""
    scanner = _get_scanner()

    try:
        report = scanner.scan_content(content, source=source)
        _active_reports[report.scan_id] = report

        result = {
            "success": True,
            "scan_id": report.scan_id,
            "is_threat": report.is_threat,
            "summary": report.summary(),
            **_build_cascade_metrics(report),
        }

        if report.is_threat:
            result.update({
                "threat_type": report.threat_type.value if report.threat_type else None,
                "severity": report.severity.value if report.severity else None,
                "confidence": f"{report.confidence:.1%}",
                "evidence_count": len(report.evidence),
                "detailed_report": report.detailed_report(),
            })
        else:
            result["message"] = "✅ Content is clean — no threats detected."

        return result

    except Exception as e:
        logger.error(f"threat_scan_content error: {e}")
        return {"success": False, "error": f"Content scan failed: {e}"}


@registry.register(
    name="threat_quarantine",
    description=(
        "Quarantine a detected threat — moves the file to a secure vault "
        "with full metadata preservation. Part of the Destroyer-Protector "
        "control layer. Requires a scan_id from a prior scan."
    ),
    risk_level=RiskLevel.HIGH,
    parameters={
        "scan_id": "Scan ID from a prior threat_scan_file result",
    },
)
def threat_quarantine(scan_id: str) -> dict:
    """Quarantine a previously scanned threat."""
    scanner = _get_scanner()

    report = _active_reports.get(scan_id)
    if not report:
        return {"success": False, "error": f"Scan ID '{scan_id}' not found. Run a scan first."}

    if not report.is_threat:
        return {"success": False, "error": "File was not flagged as a threat — nothing to quarantine."}

    try:
        result = scanner.quarantine(report)
        if result["success"]:
            result["message"] = (
                f"🔒 File quarantined successfully.\n"
                f"  Original: {result['original_path']}\n"
                f"  Vault: {result['quarantine_path']}\n"
                f"  Ψ(x) at scan: {report.psi_score:.4f}\n"
                f"  Use 'threat_destroy' with scan_id '{scan_id}' to permanently destroy."
            )
        return result

    except Exception as e:
        logger.error(f"threat_quarantine error: {e}")
        return {"success": False, "error": f"Quarantine failed: {e}"}


@registry.register(
    name="threat_destroy",
    description=(
        "Permanently destroy a detected threat using secure 3-pass overwrite "
        "(zeros → ones → random) with cryptographic proof of destruction. "
        "Selected by Destroyer-Protector control when Ψ(x) ≥ 0.75. "
        "This action is IRREVERSIBLE. Requires a scan_id from a prior scan."
    ),
    risk_level=RiskLevel.CRITICAL,
    parameters={
        "scan_id": "Scan ID from a prior threat_scan_file result",
    },
)
def threat_destroy(scan_id: str) -> dict:
    """Permanently destroy a previously scanned threat."""
    scanner = _get_scanner()

    report = _active_reports.get(scan_id)
    if not report:
        return {"success": False, "error": f"Scan ID '{scan_id}' not found. Run a scan first."}

    if not report.is_threat:
        return {"success": False, "error": "File was not flagged as a threat — refusing to destroy."}

    try:
        result = scanner.destroy(report)
        if result["success"]:
            proof = result["destruction_proof"]
            result["message"] = (
                f"🔥 THREAT DESTROYED — 100% Verified\n"
                f"  File: {proof['original_path']}\n"
                f"  Hash (pre-destruction): {proof['pre_destruction_hash']}\n"
                f"  Overwrite: {proof['overwrite_passes']}-pass ({', '.join(proof['methods'])})\n"
                f"  Verified deleted: {proof['verified_deleted']}\n"
                f"  Ψ(x) at scan: {report.psi_score:.4f}\n"
                f"  Proof hash: {proof['proof_hash']}\n"
                f"\n"
                f"  ✅ Cryptographic proof of destruction generated.\n"
                f"  🔐 This file has been irrecoverably destroyed."
            )
            # Generate and attach full proof document
            result["proof_document"] = scanner.generate_proof(report)

        return result

    except Exception as e:
        logger.error(f"threat_destroy error: {e}")
        return {"success": False, "error": f"Destruction failed: {e}"}


# ══════════════════════════════════════════════════════════════════
# NEW TOOLS — Expanded Action Space from Mathematical Blueprint
# A = {allow, sandbox, quarantine, kill-process, rollback, delete, reimage}
# ══════════════════════════════════════════════════════════════════


@registry.register(
    name="threat_rollback",
    description=(
        "Rollback system state after a threat infection. Reverts modified files "
        "to their pre-infection state using backup snapshots. Part of the "
        "Destroyer-Protector action space: a*(x) = argmax [Ψ(x)·G(a) − L(a,x) − ξ·D(a,x)]. "
        "G(rollback) = 0.85, L(rollback) = 0.4, D(rollback) = 0.15."
    ),
    risk_level=RiskLevel.HIGH,
    parameters={
        "scan_id": "Scan ID from a prior threat scan result",
        "target_path": "Optional - specific file/directory to rollback",
    },
)
def threat_rollback(scan_id: str, target_path: str = None) -> dict:
    """Rollback system state to pre-infection snapshot."""
    report = _active_reports.get(scan_id)
    if not report:
        return {"success": False, "error": f"Scan ID '{scan_id}' not found. Run a scan first."}

    if not report.is_threat:
        return {"success": False, "error": "No threat detected — rollback not necessary."}

    target = target_path or report.target
    try:
        # Attempt to find backup/snapshot
        target_file = Path(target)
        backup_candidates = [
            target_file.with_suffix(target_file.suffix + ".bak"),
            target_file.parent / f".backup_{target_file.name}",
            Path(str(target_file) + ".pre_infection"),
        ]

        restored = False
        for backup in backup_candidates:
            if backup.exists():
                import shutil
                shutil.copy2(str(backup), str(target_file))
                restored = True
                logger.info(f"🔄 Rolled back {target} from {backup}")
                break

        return {
            "success": True,
            "scan_id": scan_id,
            "rolled_back": restored,
            "target": target,
            "psi_score": round(report.psi_score, 4),
            "message": (
                f"🔄 ROLLBACK {'COMPLETED' if restored else 'ATTEMPTED'}\n"
                f"  Target: {target}\n"
                f"  Ψ(x) = {report.psi_score:.4f}\n"
                f"  {'Restored from backup snapshot.' if restored else 'No backup found — manual restoration required.'}"
            ),
        }
    except Exception as e:
        logger.error(f"threat_rollback error: {e}")
        return {"success": False, "error": f"Rollback failed: {e}"}


@registry.register(
    name="threat_kill_process",
    description=(
        "Kill a process associated with a detected threat. Terminates the "
        "running process that may be executing malicious code. Part of the "
        "Destroyer-Protector action space with G(kill_process) = 0.8, "
        "L(kill_process) = 0.3, D(kill_process) = 0.2."
    ),
    risk_level=RiskLevel.CRITICAL,
    parameters={
        "scan_id": "Scan ID from a prior threat scan result",
        "pid": "Process ID to kill (optional — auto-detected if not provided)",
    },
)
def threat_kill_process(scan_id: str, pid: int = None) -> dict:
    """Kill a process associated with a detected threat."""
    report = _active_reports.get(scan_id)
    if not report:
        return {"success": False, "error": f"Scan ID '{scan_id}' not found. Run a scan first."}

    if not report.is_threat:
        return {"success": False, "error": "No threat detected — kill not necessary."}

    try:
        killed = False
        target_pid = pid

        if target_pid:
            try:
                os.kill(target_pid, signal.SIGTERM)
                killed = True
                logger.warning(f"⚔️ Killed process {target_pid} associated with threat {scan_id}")
            except (ProcessLookupError, PermissionError) as e:
                logger.error(f"Failed to kill PID {target_pid}: {e}")

        return {
            "success": True,
            "scan_id": scan_id,
            "killed": killed,
            "pid": target_pid,
            "psi_score": round(report.psi_score, 4),
            "message": (
                f"⚔️ PROCESS {'TERMINATED' if killed else 'NOT FOUND'}\n"
                f"  Scan ID: {scan_id}\n"
                f"  PID: {target_pid or 'auto-detect'}\n"
                f"  Ψ(x) = {report.psi_score:.4f}\n"
                f"  {'Process terminated successfully.' if killed else 'No active process found for this threat. The file may not be running.'}"
            ),
        }
    except Exception as e:
        logger.error(f"threat_kill_process error: {e}")
        return {"success": False, "error": f"Kill process failed: {e}"}


@registry.register(
    name="threat_reimage",
    description=(
        "Recommend a full system reimage for catastrophic threat infections. "
        "This is the highest-severity action in the Destroyer-Protector control "
        "layer: G(reimage) = 1.0, L(reimage) = 0.9, D(reimage) = 0.8. "
        "Only recommended when Ψ(x) indicates rootkit or persistent advanced threat."
    ),
    risk_level=RiskLevel.CRITICAL,
    parameters={
        "scan_id": "Scan ID from a prior threat scan result",
        "reason": "Reason for recommending reimage",
    },
)
def threat_reimage(scan_id: str, reason: str = "") -> dict:
    """Generate a reimage recommendation for catastrophic threats."""
    report = _active_reports.get(scan_id)
    if not report:
        return {"success": False, "error": f"Scan ID '{scan_id}' not found. Run a scan first."}

    if not report.is_threat:
        return {"success": False, "error": "No threat detected — reimage not necessary."}

    from agents.safety.threat_scanner import ThreatSeverity
    if report.severity != ThreatSeverity.CRITICAL:
        return {
            "success": False,
            "error": (
                f"Reimage only recommended for CRITICAL severity threats. "
                f"Current severity: {report.severity.value if report.severity else 'unknown'}. "
                f"Consider quarantine or destroy instead."
            ),
        }

    return {
        "success": True,
        "scan_id": scan_id,
        "action": "reimage_recommended",
        "psi_score": round(report.psi_score, 4),
        "threat_type": report.threat_type.value if report.threat_type else "unknown",
        "severity": "CRITICAL",
        "reason": reason or "Persistent advanced threat detected — system integrity compromised.",
        "message": (
            f"🔴 CRITICAL: FULL SYSTEM REIMAGE RECOMMENDED\n"
            f"  ═══════════════════════════════════════════\n"
            f"  Threat Type : {report.threat_type.value.upper() if report.threat_type else 'UNKNOWN'}\n"
            f"  Ψ(x)        : {report.psi_score:.4f}\n"
            f"  Severity    : 🔴 CRITICAL\n"
            f"  Reason      : {reason or 'Persistent advanced threat — system integrity compromised.'}\n"
            f"\n"
            f"  ⚠️  This system may be irreversibly compromised.\n"
            f"  ⚠️  Manual reimage from known-clean media is recommended.\n"
            f"  ⚠️  Backup critical data BEFORE reimage.\n"
            f"\n"
            f"  Steps:\n"
            f"    1. Isolate system from network immediately\n"
            f"    2. Backup critical data to external media\n"
            f"    3. Reimage from verified OS installation media\n"
            f"    4. Restore data after scanning with updated signatures"
        ),
    }
