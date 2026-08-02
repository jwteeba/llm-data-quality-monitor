from dataclasses import dataclass


@dataclass
class Rule:
    name: str
    check: str  # "missing_pct" | "duplicate_rows" | "outlier_count"
    column: str | None  # None for dataset-level checks
    operator: str  # ">" | ">=" | "<" | "<="
    threshold: float


def evaluate_rules(rules: list[Rule], anomalies: dict, row_count: int) -> list[dict]:
    """Evaluate each rule against anomaly results. Returns list of violations."""
    violations = []
    ops = {
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
    }

    for rule in rules:
        op = ops.get(rule.operator)
        if op is None:
            continue

        if rule.check == "missing_pct":
            missing = anomalies.get("missing_values", {})
            value = (missing.get(rule.column, 0) / row_count * 100) if row_count else 0
        elif rule.check == "duplicate_rows":
            value = anomalies.get("duplicate_rows", 0)
        elif rule.check == "outlier_count":
            value = anomalies.get("outliers", {}).get(rule.column, 0)
        else:
            continue

        if op(value, rule.threshold):
            violations.append(
                {
                    "rule": rule.name,
                    "check": rule.check,
                    "column": rule.column or "dataset",
                    "value": round(value, 2),
                    "operator": rule.operator,
                    "threshold": rule.threshold,
                }
            )

    return violations
