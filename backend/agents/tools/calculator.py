"""
Advanced Calculator Tool — Universal Computation Engine.
────────────────────────────────────────────────────────
Goes far beyond basic math. Supports:
  - Scientific calculations (trig, log, powers)
  - Unit conversions (length, weight, temperature, etc.)
  - Financial calculations (interest, mortgage, ROI)
  - Statistical operations (mean, median, std dev)
  - Date/time math (days between, add months)
  - Percentage operations
  - Currency-like formatting
"""

import math
import statistics
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class AdvancedCalculator:
    """
    Universal calculator that handles math, stats, finance, units, and dates.
    Registered as a tool that any domain can use.
    """

    def __init__(self):
        self._history: List[Dict] = []

    # ──────────────────────────────────────────
    # Core Math
    # ──────────────────────────────────────────

    def evaluate(self, expression: str) -> Dict[str, Any]:
        """
        Safely evaluate a mathematical expression using AST parsing.

        Args:
            expression: Math expression like "2 * (3 + 4)" or "sqrt(144)"

        Returns:
            {"result": number, "expression": str, "formatted": str}
        """
        import ast
        import operator

        # Safe namespace with math functions
        safe_ns = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "int": int, "float": float,
            "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
            "log2": math.log2, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "asin": math.asin, "acos": math.acos,
            "atan": math.atan, "pi": math.pi, "e": math.e,
            "ceil": math.ceil, "floor": math.floor,
            "factorial": math.factorial, "gcd": math.gcd,
            "degrees": math.degrees, "radians": math.radians,
        }


        # Allowed binary operators
        _ops = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
            ast.Pow: operator.pow, ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        def _safe_eval(node):
            """Recursively evaluate an AST node using only safe operations."""
            if isinstance(node, ast.Expression):
                return _safe_eval(node.body)
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError(f"Unsupported constant: {node.value!r}")
            elif isinstance(node, ast.BinOp):
                op_fn = _ops.get(type(node.op))
                if not op_fn:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op_fn(_safe_eval(node.left), _safe_eval(node.right))
            elif isinstance(node, ast.UnaryOp):
                op_fn = _ops.get(type(node.op))
                if not op_fn:
                    raise ValueError(f"Unsupported unary: {type(node.op).__name__}")
                return op_fn(_safe_eval(node.operand))
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in safe_ns:
                    fn = safe_ns[node.func.id]
                    args = [_safe_eval(a) for a in node.args]
                    return fn(*args)
                raise ValueError(f"Unknown function: {ast.dump(node.func)}")
            elif isinstance(node, ast.Name):
                if node.id in safe_ns:
                    val = safe_ns[node.id]
                    if isinstance(val, (int, float)):
                        return val
                    raise ValueError(f"'{node.id}' is callable, not a value")
                raise ValueError(f"Unknown name: {node.id}")
            else:
                raise ValueError(f"Unsupported expression: {type(node).__name__}")

        try:
            clean = expression.replace("^", "**").replace("×", "*").replace("÷", "/")
            tree = ast.parse(clean, mode="eval")
            result = _safe_eval(tree)
            entry = {
                "result": result,
                "expression": expression,
                "formatted": self._format_number(result),
            }
            self._history.append(entry)
            return entry
        except Exception as e:
            return {"result": None, "expression": expression, "error": str(e)}

    # ──────────────────────────────────────────
    # Unit Conversions
    # ──────────────────────────────────────────

    _CONVERSIONS = {
        # Length (to meters)
        "km": 1000, "m": 1, "cm": 0.01, "mm": 0.001,
        "mile": 1609.344, "yard": 0.9144, "foot": 0.3048, "inch": 0.0254,

        # Weight (to grams)
        "kg": 1000, "g": 1, "mg": 0.001,
        "lb": 453.592, "oz": 28.3495, "ton": 907185,

        # Volume (to liters)
        "liter": 1, "ml": 0.001, "gallon": 3.78541,
        "cup": 0.236588, "tablespoon": 0.0147868, "teaspoon": 0.00492892,
    }

    def convert_units(self, value: float, from_unit: str, to_unit: str) -> Dict[str, Any]:
        """Convert between compatible units."""
        from_u = from_unit.lower()
        to_u = to_unit.lower()

        # Temperature (special case — check before stripping plurals)
        temp_units = ("celsius", "c", "fahrenheit", "f", "kelvin", "k")
        if from_u in temp_units or to_u in temp_units:
            return self._convert_temperature(value, from_u, to_u)

        # Strip plural 's' for other units
        from_u = from_u.rstrip("s")
        to_u = to_u.rstrip("s")

        if from_u not in self._CONVERSIONS or to_u not in self._CONVERSIONS:
            return {"error": f"Unknown units: {from_unit} or {to_unit}"}

        # Convert: from → base → to
        base_value = value * self._CONVERSIONS[from_u]
        result = base_value / self._CONVERSIONS[to_u]

        return {
            "result": round(result, 6),
            "from": f"{value} {from_unit}",
            "to": f"{round(result, 6)} {to_unit}",
            "formatted": f"{value} {from_unit} = {self._format_number(result)} {to_unit}",
        }

    def _convert_temperature(self, value: float, from_u: str, to_u: str) -> Dict:
        """Handle temperature conversions."""
        # Normalize unit names
        units = {"celsius": "C", "c": "C", "fahrenheit": "F", "f": "F", "kelvin": "K", "k": "K"}
        f = units.get(from_u, from_u.upper())
        t = units.get(to_u, to_u.upper())

        # Convert to Celsius first
        if f == "F":
            celsius = (value - 32) * 5 / 9
        elif f == "K":
            celsius = value - 273.15
        else:
            celsius = value

        # Convert from Celsius
        if t == "F":
            result = celsius * 9 / 5 + 32
        elif t == "K":
            result = celsius + 273.15
        else:
            result = celsius

        return {
            "result": round(result, 2),
            "formatted": f"{value}°{f} = {round(result, 2)}°{t}",
        }

    # ──────────────────────────────────────────
    # Financial Calculations
    # ──────────────────────────────────────────

    def compound_interest(
        self,
        principal: float,
        annual_rate: float,
        years: float,
        compounds_per_year: int = 12,
    ) -> Dict[str, Any]:
        """Calculate compound interest."""
        r = annual_rate / 100
        n = compounds_per_year
        amount = principal * (1 + r / n) ** (n * years)
        interest = amount - principal
        return {
            "principal": principal,
            "final_amount": round(amount, 2),
            "interest_earned": round(interest, 2),
            "rate": f"{annual_rate}%",
            "period": f"{years} years",
            "formatted": (
                f"${self._format_number(principal)} at {annual_rate}% for {years} years "
                f"= ${self._format_number(amount)} (${self._format_number(interest)} interest)"
            ),
        }

    def loan_payment(
        self,
        principal: float,
        annual_rate: float,
        years: float,
    ) -> Dict[str, Any]:
        """Calculate monthly loan payment."""
        r = annual_rate / 100 / 12
        n = years * 12
        if r == 0:
            payment = principal / n
        else:
            payment = principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        total = payment * n
        return {
            "monthly_payment": round(payment, 2),
            "total_paid": round(total, 2),
            "total_interest": round(total - principal, 2),
            "formatted": (
                f"Loan of ${self._format_number(principal)} at {annual_rate}% for {years} years: "
                f"${self._format_number(payment)}/month "
                f"(total: ${self._format_number(total)}, interest: ${self._format_number(total - principal)})"
            ),
        }

    def roi(self, initial: float, final: float) -> Dict[str, Any]:
        """Calculate return on investment."""
        gain = final - initial
        roi_pct = (gain / initial) * 100 if initial != 0 else 0
        return {
            "initial": initial,
            "final": final,
            "gain": round(gain, 2),
            "roi_percent": round(roi_pct, 2),
            "formatted": f"ROI: {round(roi_pct, 2)}% (${self._format_number(gain)} gain)",
        }

    # ──────────────────────────────────────────
    # Statistics
    # ──────────────────────────────────────────

    def stats(self, numbers: List[float]) -> Dict[str, Any]:
        """Calculate comprehensive statistics for a list of numbers."""
        if not numbers:
            return {"error": "Empty list"}

        n = len(numbers)
        result = {
            "count": n,
            "sum": round(sum(numbers), 4),
            "mean": round(statistics.mean(numbers), 4),
            "median": round(statistics.median(numbers), 4),
            "min": min(numbers),
            "max": max(numbers),
            "range": round(max(numbers) - min(numbers), 4),
        }

        if n >= 2:
            result["std_dev"] = round(statistics.stdev(numbers), 4)
            result["variance"] = round(statistics.variance(numbers), 4)

        try:
            result["mode"] = statistics.mode(numbers)
        except statistics.StatisticsError:
            result["mode"] = "no unique mode"

        return result

    # ──────────────────────────────────────────
    # Date Math
    # ──────────────────────────────────────────

    def days_between(self, date1: str, date2: str) -> Dict[str, Any]:
        """Calculate days between two dates (YYYY-MM-DD format)."""
        try:
            d1 = datetime.strptime(date1, "%Y-%m-%d")
            d2 = datetime.strptime(date2, "%Y-%m-%d")
            delta = abs((d2 - d1).days)
            return {
                "days": delta,
                "weeks": round(delta / 7, 1),
                "months": round(delta / 30.44, 1),
                "years": round(delta / 365.25, 2),
                "formatted": f"{delta} days ({round(delta / 7, 1)} weeks) between {date1} and {date2}",
            }
        except ValueError as e:
            return {"error": f"Invalid date format: {e}. Use YYYY-MM-DD"}

    def add_days(self, date: str, days: int) -> Dict[str, Any]:
        """Add days to a date."""
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            result = d + timedelta(days=days)
            return {
                "result": result.strftime("%Y-%m-%d"),
                "day_of_week": result.strftime("%A"),
                "formatted": f"{date} + {days} days = {result.strftime('%A, %B %d, %Y')}",
            }
        except ValueError as e:
            return {"error": str(e)}

    # ──────────────────────────────────────────
    # Percentage Operations
    # ──────────────────────────────────────────

    def percentage(self, operation: str, value: float, percent: float) -> Dict[str, Any]:
        """
        Percentage operations.

        Operations: 'of' (what is X% of Y), 'change' (% change from X to Y),
                    'add' (X + Y%), 'subtract' (X - Y%)
        """
        if operation == "of":
            result = value * percent / 100
            return {"result": round(result, 4), "formatted": f"{percent}% of {value} = {round(result, 4)}"}
        elif operation == "change":
            if value == 0:
                return {"error": "Cannot calculate % change from 0"}
            change = ((percent - value) / value) * 100
            return {"result": round(change, 2), "formatted": f"Change from {value} to {percent} = {round(change, 2)}%"}
        elif operation == "add":
            result = value * (1 + percent / 100)
            return {"result": round(result, 4), "formatted": f"{value} + {percent}% = {round(result, 4)}"}
        elif operation == "subtract":
            result = value * (1 - percent / 100)
            return {"result": round(result, 4), "formatted": f"{value} - {percent}% = {round(result, 4)}"}
        return {"error": f"Unknown operation: {operation}"}

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _format_number(n) -> str:
        """Format a number nicely."""
        if isinstance(n, float):
            if n == int(n) and abs(n) < 1e15:
                return f"{int(n):,}"
            return f"{n:,.4f}".rstrip("0").rstrip(".")
        return f"{n:,}"

    def get_history(self) -> List[Dict]:
        """Get calculation history."""
        return list(self._history)
