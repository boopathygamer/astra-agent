"""
Data Analyzer Tool — Universal Data Analysis for Everyone.
───────────────────────────────────────────────────────────
Makes data analysis accessible to non-technical users:
  - Parse and analyze CSV/JSON data
  - Basic statistics and summaries
  - Trend detection
  - Outlier identification
  - Comparative analysis
  - Chart description generation
"""

import csv
import io
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DataSummary:
    """Summary of a dataset."""
    row_count: int = 0
    column_count: int = 0
    columns: List[Dict[str, Any]] = field(default_factory=list)
    missing_values: Dict[str, int] = field(default_factory=dict)
    insights: List[str] = field(default_factory=list)


@dataclass
class ColumnProfile:
    """Profile of a single column."""
    name: str = ""
    dtype: str = ""         # numeric, text, date, boolean
    unique_count: int = 0
    missing_count: int = 0
    top_values: List[Tuple[str, int]] = field(default_factory=list)
    # Numeric-only fields
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    mean_val: Optional[float] = None
    median_val: Optional[float] = None


class DataAnalyzer:
    """
    Universal data analysis tool.

    Parses CSV/JSON data and produces insights without
    requiring the user to know pandas or statistics.
    """

    def __init__(self):
        logger.info("DataAnalyzer initialized")

    # ──────────────────────────────────────────
    # Data Parsing
    # ──────────────────────────────────────────

    def parse_csv(self, csv_text: str) -> List[Dict[str, str]]:
        """Parse CSV text into a list of dictionaries."""
        reader = csv.DictReader(io.StringIO(csv_text))
        return list(reader)

    def parse_json(self, json_text: str) -> Any:
        """Parse JSON text."""
        return json.loads(json_text)

    # ──────────────────────────────────────────
    # Analysis
    # ──────────────────────────────────────────

    def analyze(self, data: List[Dict]) -> DataSummary:
        """
        Analyze a dataset and produce a comprehensive summary.

        Args:
            data: List of dictionaries (rows)

        Returns:
            DataSummary with insights
        """
        if not data:
            return DataSummary(insights=["Empty dataset — no data to analyze"])

        columns = list(data[0].keys())
        row_count = len(data)

        # Profile each column
        col_profiles = []
        missing = {}
        for col in columns:
            profile = self._profile_column(data, col)
            col_profiles.append({
                "name": profile.name,
                "type": profile.dtype,
                "unique": profile.unique_count,
                "missing": profile.missing_count,
                "top_values": profile.top_values[:3],
            })
            if profile.dtype == "numeric":
                col_profiles[-1].update({
                    "min": profile.min_val,
                    "max": profile.max_val,
                    "mean": profile.mean_val,
                    "median": profile.median_val,
                })
            if profile.missing_count > 0:
                missing[col] = profile.missing_count

        # Generate insights
        insights = self._generate_insights(data, columns, col_profiles)

        return DataSummary(
            row_count=row_count,
            column_count=len(columns),
            columns=col_profiles,
            missing_values=missing,
            insights=insights,
        )

    def _profile_column(self, data: List[Dict], col: str) -> ColumnProfile:
        """Profile a single column."""
        values = [row.get(col, "") for row in data]
        non_empty = [v for v in values if v is not None and str(v).strip() != ""]

        # Detect type
        numeric_values = []
        for v in non_empty:
            try:
                numeric_values.append(float(str(v).replace(",", "")))
            except (ValueError, TypeError):
                pass

        is_numeric = len(numeric_values) > len(non_empty) * 0.8

        profile = ColumnProfile(
            name=col,
            dtype="numeric" if is_numeric else "text",
            unique_count=len(set(str(v) for v in non_empty)),
            missing_count=len(values) - len(non_empty),
        )

        if is_numeric and numeric_values:
            sorted_nums = sorted(numeric_values)
            profile.min_val = round(sorted_nums[0], 4)
            profile.max_val = round(sorted_nums[-1], 4)
            profile.mean_val = round(sum(sorted_nums) / len(sorted_nums), 4)
            mid = len(sorted_nums) // 2
            profile.median_val = round(
                sorted_nums[mid] if len(sorted_nums) % 2 else
                (sorted_nums[mid - 1] + sorted_nums[mid]) / 2, 4
            )
        else:
            # Top values for text columns
            counts = Counter(str(v) for v in non_empty)
            profile.top_values = counts.most_common(5)

        return profile

    def _generate_insights(
        self,
        data: List[Dict],
        columns: List[str],
        profiles: List[Dict],
    ) -> List[str]:
        """Generate human-readable insights from the data."""
        insights = []

        insights.append(f"Dataset has {len(data)} rows and {len(columns)} columns")

        for p in profiles:
            if p["type"] == "numeric":
                insights.append(
                    f"📊 {p['name']}: ranges from {p.get('min')} to {p.get('max')} "
                    f"(average: {p.get('mean')}, median: {p.get('median')})"
                )
                # Check for skew (mean vs median difference)
                mean = p.get("mean", 0) or 0
                median = p.get("median", 0) or 0
                if mean and median and abs(mean - median) > abs(mean) * 0.2:
                    if mean > median:
                        insights.append(f"  ⚠️ {p['name']} is right-skewed (outliers pulling mean up)")
                    else:
                        insights.append(f"  ⚠️ {p['name']} is left-skewed (outliers pulling mean down)")
            else:
                insights.append(
                    f"📝 {p['name']}: {p['unique']} unique values"
                    + (f", top: {p['top_values'][0][0]}" if p.get('top_values') else "")
                )

            if p.get("missing", 0) > 0:
                pct = p["missing"] / len(data) * 100
                insights.append(f"  ⚠️ {p['name']} has {p['missing']} missing values ({pct:.1f}%)")

        return insights

    # ──────────────────────────────────────────
    # Comparisons
    # ──────────────────────────────────────────

    def compare_groups(
        self,
        data: List[Dict],
        group_col: str,
        value_col: str,
    ) -> Dict[str, Any]:
        """Compare a numeric column across groups."""
        groups: Dict[str, List[float]] = {}
        for row in data:
            group = str(row.get(group_col, ""))
            try:
                val = float(str(row.get(value_col, "")).replace(",", ""))
                if group not in groups:
                    groups[group] = []
                groups[group].append(val)
            except (ValueError, TypeError):
                continue

        result = {}
        for group, values in groups.items():
            sorted_vals = sorted(values)
            n = len(sorted_vals)
            result[group] = {
                "count": n,
                "sum": round(sum(sorted_vals), 2),
                "mean": round(sum(sorted_vals) / n, 2) if n > 0 else 0,
                "min": sorted_vals[0] if sorted_vals else None,
                "max": sorted_vals[-1] if sorted_vals else None,
            }

        return {
            "group_column": group_col,
            "value_column": value_col,
            "groups": result,
            "group_count": len(groups),
        }

    # ──────────────────────────────────────────
    # Chart Descriptions
    # ──────────────────────────────────────────

    def suggest_charts(self, summary: DataSummary) -> List[Dict[str, str]]:
        """Suggest appropriate chart types for the data."""
        suggestions = []

        numeric_cols = [c for c in summary.columns if c["type"] == "numeric"]
        text_cols = [c for c in summary.columns if c["type"] == "text"]

        if numeric_cols:
            suggestions.append({
                "type": "Histogram",
                "column": numeric_cols[0]["name"],
                "reason": "Shows the distribution of values",
            })

        if len(numeric_cols) >= 2:
            suggestions.append({
                "type": "Scatter Plot",
                "columns": f"{numeric_cols[0]['name']} vs {numeric_cols[1]['name']}",
                "reason": "Reveals relationships between two numeric variables",
            })

        if text_cols and numeric_cols:
            suggestions.append({
                "type": "Bar Chart",
                "columns": f"{text_cols[0]['name']} × {numeric_cols[0]['name']}",
                "reason": "Compare values across categories",
            })

        if text_cols:
            suggestions.append({
                "type": "Pie Chart",
                "column": text_cols[0]["name"],
                "reason": f"Shows breakdown of {text_cols[0]['unique']} categories",
            })

        if summary.row_count > 10 and numeric_cols:
            suggestions.append({
                "type": "Line Chart",
                "column": numeric_cols[0]["name"],
                "reason": "Visualize trends over time or sequence",
            })

        return suggestions
