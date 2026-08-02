import pandas as pd


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Return per-column statistics and type inconsistency flags."""
    profile = {}
    for col in df.columns:
        s = df[col]
        entry: dict = {
            "dtype": str(s.dtype),
            "count": int(s.count()),
            "missing": int(s.isna().sum()),
            "missing_pct": round(s.isna().mean() * 100, 2),
            "unique": int(s.nunique()),
        }

        if pd.api.types.is_numeric_dtype(s):
            entry.update(
                {
                    "min": round(float(s.min()), 4) if not s.isna().all() else None,
                    "max": round(float(s.max()), 4) if not s.isna().all() else None,
                    "mean": round(float(s.mean()), 4) if not s.isna().all() else None,
                    "median": (
                        round(float(s.median()), 4) if not s.isna().all() else None
                    ),
                    "std": round(float(s.std()), 4) if not s.isna().all() else None,
                    "p25": (
                        round(float(s.quantile(0.25)), 4)
                        if not s.isna().all()
                        else None
                    ),
                    "p75": (
                        round(float(s.quantile(0.75)), 4)
                        if not s.isna().all()
                        else None
                    ),
                }
            )
        else:
            non_null = s.dropna()
            entry["sample_values"] = non_null.unique()[:5].tolist()
            # Type inconsistency: mixed numeric and non-numeric strings
            if s.dtype == object:
                numeric_mask = pd.to_numeric(non_null, errors="coerce").notna()
                mixed = numeric_mask.any() and (~numeric_mask).any()
                entry["mixed_types"] = bool(mixed)

        profile[col] = entry
    return profile
