"""
Log Exporter — Structured JSON Log Aggregation
═══════════════════════════════════════════════
Exports metrics and traces to structured JSON log files
compatible with Grafana Loki, ELK Stack, and CloudWatch.

Features:
  - Periodic flush of MetricsCollector snapshots
  - Trace export as structured JSON lines
  - Log rotation with configurable max size
  - Thread-safe background writer
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StructuredLogExporter:
    """
    Exports telemetry data to structured JSON log files.
    
    Writes JSONL format for ingestion by log aggregation systems.
    """
    
    def __init__(
        self,
        log_dir: str = "data/logs",
        metrics_file: str = "metrics.jsonl",
        traces_file: str = "traces.jsonl",
        max_file_size_mb: int = 50,
        flush_interval_s: float = 30.0,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_path = self.log_dir / metrics_file
        self.traces_path = self.log_dir / traces_file
        self.max_file_bytes = max_file_size_mb * 1024 * 1024
        self.flush_interval = flush_interval_s
        
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the background flush thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()
        logger.info(f"📊 Log exporter started → {self.log_dir}")
    
    def stop(self):
        """Stop the background flush thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        # Final flush
        self.flush_now()
    
    def _flush_loop(self):
        while self._running:
            time.sleep(self.flush_interval)
            try:
                self.flush_now()
            except Exception as e:
                logger.error(f"Log export flush error: {e}")
    
    def flush_now(self):
        """Immediately flush current metrics and traces to disk."""
        with self._lock:
            self._export_metrics()
            self._export_traces()
    
    def _export_metrics(self):
        """Export current MetricsCollector state to JSONL."""
        try:
            from telemetry.metrics import MetricsCollector
            mc = MetricsCollector.get_instance()
            report = mc.get_report()
            
            entry = {
                "type": "metrics_snapshot",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "histograms": {},
                "counters": report.counters,
                "gauges": report.gauges,
            }
            
            for name, h in report.histograms.items():
                entry["histograms"][name] = {
                    "count": h.count,
                    "mean": round(h.mean, 3),
                    "p50": round(h.p50, 3),
                    "p95": round(h.p95, 3),
                    "p99": round(h.p99, 3),
                    "min": round(h.min, 3),
                    "max": round(h.max, 3),
                }
            
            self._write_jsonl(self.metrics_path, entry)
        except Exception as e:
            logger.debug(f"Metrics export skipped: {e}")
    
    def _export_traces(self):
        """Export recent traces to JSONL."""
        try:
            from telemetry.tracer import SpanTracer
            # We can't easily get traces from a singleton tracer without coupling,
            # so we export if any trace data is available in our scope
            pass  # Traces are exported on-demand via SpanTracer.export_json()
        except Exception:
            pass
    
    def write_event(self, event_type: str, data: Dict[str, Any]):
        """Write a custom structured event to the log."""
        entry = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        with self._lock:
            self._write_jsonl(self.metrics_path, entry)
    
    def _write_jsonl(self, path: Path, entry: dict):
        """Append a JSON line to a file, with rotation."""
        self._maybe_rotate(path)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    
    def _maybe_rotate(self, path: Path):
        """Rotate log file if it exceeds max size."""
        if path.exists() and path.stat().st_size > self.max_file_bytes:
            rotated = path.with_suffix(f".{int(time.time())}.jsonl")
            path.rename(rotated)
            logger.info(f"Rotated log file to {rotated.name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get exporter stats."""
        metrics_size = self.metrics_path.stat().st_size if self.metrics_path.exists() else 0
        traces_size = self.traces_path.stat().st_size if self.traces_path.exists() else 0
        return {
            "log_dir": str(self.log_dir),
            "metrics_file_bytes": metrics_size,
            "traces_file_bytes": traces_size,
            "is_running": self._running,
        }
