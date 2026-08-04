import pandas as pd


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Generate per-column summary statistics and type anomaly flags for a DataFrame.

    Computes standard distribution metrics for numeric non-boolean columns
    (min, max, mean, median, std, p25, p75) and sample value profiles for
    non-numeric or boolean columns. Detects mixed-type string/numeric data
    within object-dtype columns.

    Args:
        df: The pandas DataFrame to profile.

    Returns:
        A dictionary mapping each column name to a nested dictionary of statistics:
            - dtype (str): Data type string of the column.
            - count (int): Number of non-null values.
            - missing (int): Count of missing/NaN values.
            - missing_pct (float): Percentage of missing values rounded to 2 decimals.
            - unique (int): Count of distinct values.
            - min, max, mean, median, std, p25, p75 (float | None): Standard summary
              statistics (numeric columns only, excluding boolean).
            - sample_values (list): Up to 5 unique non-null values (non-numeric columns).
            - mixed_types (bool): Indicates if an object column contains both numeric
              and non-numeric parseable strings.
    """
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

        # Ensure numeric check excludes boolean columns
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
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
                mixed = numeric_mask.any() and not numeric_mask.all()
                entry["mixed_types"] = bool(mixed)

        profile[col] = entry
    return profile
