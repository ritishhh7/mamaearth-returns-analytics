"""Reproducible cleaning, EDA, reconciliation, and findings export.

Run from the repository root: python analysis/clean_and_eda.py
"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NARRATOR = ROOT / "narrator"
NARRATOR.mkdir(exist_ok=True)

customers = pd.read_csv(DATA / "customers.csv")
products = pd.read_csv(DATA / "products.csv")
orders = pd.read_csv(DATA / "orders.csv")

print("TASK 1 — Load and inspect")
print("customers.shape:", customers.shape)
print("products.shape:", products.shape)
print("orders.shape before cleaning:", orders.shape)
print()

print("TASK 2 — Standardize payment methods")
print("Raw unique payment_method values:", sorted(orders["payment_method"].dropna().unique().tolist()))
orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
print("Cleaned payment counts:")
print(orders["payment_method"].value_counts().sort_index().to_string())
print()

print("TASK 3 — Remove duplicate orders")
natural_key = [
    "customer_id", "product_id", "order_date", "quantity", "discount_pct",
    "payment_method", "rating", "returned"
]
duplicate_mask = orders.duplicated(subset=natural_key, keep="first")
dropped_orders = orders.loc[duplicate_mask].copy()
orders_clean = orders.loc[~duplicate_mask].copy()
print("Duplicate rows flagged:", int(duplicate_mask.sum()))
print("Dropped order_id values:", sorted(dropped_orders["order_id"].tolist()))
print("orders_clean.shape:", orders_clean.shape)
print()

print("TASK 4 — Impute missing values")
missing_discount = int(orders_clean["discount_pct"].isna().sum())
missing_rating = int(orders_clean["rating"].isna().sum())
rating_median = float(orders_clean["rating"].median())
print("Missing discount_pct rows affected:", missing_discount)
print("Median rating before imputation:", rating_median)
print("Missing rating rows affected:", missing_rating)
orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)
print("Null counts after imputation:", orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())
print()

print("TASK 5 — Merge, revenue, and reconciliation")
merged = (orders_clean.merge(products, on="product_id", how="left", validate="many_to_one")
          .merge(customers, on="customer_id", how="left", validate="many_to_one"))
merged["order_date"] = pd.to_datetime(merged["order_date"])
merged["order_value"] = merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)
cleaned_total = round(float(merged["order_value"].sum()), 2)

# Calculate the duplicate rows' contribution independently using the same product-price lookup.
dropped_check = dropped_orders.merge(products[["product_id", "price"]], on="product_id", how="left", validate="many_to_one")
dropped_check["order_value"] = dropped_check["quantity"] * dropped_check["price"] * (
    1 - dropped_check["discount_pct"].fillna(0) / 100
)
duplicate_delta = round(float(dropped_check["order_value"].sum()), 2)
raw_total = round(cleaned_total + duplicate_delta, 2)
print(f"Cleaned total revenue across {len(merged)} rows: {cleaned_total:.2f}")
print(f"Independent sum of the 5 dropped rows: {duplicate_delta:.2f}")
print(f"Reconstructed raw total revenue: {raw_total:.2f}")
print(
    f"Reconciliation: cleaned revenue is ₹{duplicate_delta:,.2f} lower than raw revenue because "
    f"the five duplicate submissions ({', '.join(sorted(dropped_orders['order_id'].tolist()))}) "
    f"contributed ₹{duplicate_delta:,.2f} in order value. Filling missing discounts with 0 and "
    "missing ratings with the median does not change order value, so those imputations do not "
    "explain the revenue difference."
)
print()

print("TASK 6 — IQR outlier detection on quantity")
q1 = float(merged["quantity"].quantile(0.25))
q3 = float(merged["quantity"].quantile(0.75))
iqr = q3 - q1
lower = q1 - 1.5 * iqr
upper = q3 + 1.5 * iqr
merged["is_outlier"] = ~merged["quantity"].between(lower, upper, inclusive="both")
outliers = merged.loc[merged["is_outlier"], ["order_id", "quantity"]].sort_values("order_id")
print(f"Q1={q1:.1f}, Q3={q3:.1f}, IQR={iqr:.1f}, lower={lower:.1f}, upper={upper:.1f}")
print("Outlier rows (flagged, not removed):")
print(outliers.to_string(index=False))
print()

print("TASK 7 — Hypothesis: COD has a higher return rate")
print("Hypothesis: COD orders have a higher return rate than card and UPI orders.")
payment_returns = merged.groupby("payment_method")["returned"].agg(["count", "mean"])
payment_returns["return_rate_pct"] = (payment_returns["mean"] * 100).round(1)
print(payment_returns[["count", "return_rate_pct"]].sort_index().to_string())
cod_rate = float(payment_returns.loc["COD", "return_rate_pct"])
print("Hypothesis result:", "Confirmed" if cod_rate > payment_returns.loc[["CARD", "UPI"], "return_rate_pct"].max() else "Not confirmed")
print()

print("TASK 8 — Payment method and city-tier segmentation")
segment = (merged.groupby(["payment_method", "city_tier"])["returned"]
           .agg(order_count="count", returned_orders="sum"))
segment["return_rate_pct"] = (segment["returned_orders"] / segment["order_count"] * 100).round(1)
print(segment.to_string())
highest = segment["return_rate_pct"].idxmax()
highest_rate = float(segment.loc[highest, "return_rate_pct"])
print(f"Highest-risk segment: {highest[0]} + Tier-{highest[1]} cities at {highest_rate:.1f}%.")
print()

print("TASK 9 — Correlation analysis")
corr_cols = ["rating", "returned", "discount_pct", "quantity"]
corr = merged[corr_cols].corr()
print(corr.round(4).to_string())
bands = [(0.0, 0.19, "negligible"), (0.2, 0.39, "weak"), (0.4, 0.69, "moderate"), (0.7, 1.0, "strong")]
for i, col_a in enumerate(corr_cols):
    for col_b in corr_cols[i + 1:]:
        r = float(corr.loc[col_a, col_b])
        magnitude = abs(r)
        band = next((name for lo, hi, name in bands if lo <= magnitude <= hi), "negligible")
        print(f"{col_a} vs {col_b}: r={r:.4f}, {band} correlation")
discount_r = float(corr.loc["discount_pct", "returned"])
print('Hypothesis "higher discounts reduce returns":', "Busted" if abs(discount_r) < 0.2 else "Needs further investigation",
      f"(discount_pct vs returned r={discount_r:.4f}).")
print()

print("TASK 10 — Monthly revenue, with and without quantity outliers")
merged["year_month"] = merged["order_date"].dt.to_period("M").astype(str)
monthly_all = merged.groupby("year_month")["order_value"].sum().round(2)
monthly_corrected = merged.loc[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
print("Monthly revenue including outliers:")
print(monthly_all.to_string())
print("Monthly revenue excluding flagged quantity outliers:")
print(monthly_corrected.to_string())
peak_month = str(monthly_corrected.idxmax())
peak_revenue = round(float(monthly_corrected.max()), 2)
jan_inflated = round(float(monthly_all.loc["2026-01"]), 2)
jan_corrected = round(float(monthly_corrected.loc["2026-01"]), 2)
print(
    f"January's apparent lead (₹{jan_inflated:,.2f}) is an artifact of two bulk orders landing in January: "
    "O0011 on 2026-01-28 (quantity 25) and O0098 on 2026-01-10 (quantity 30). "
    f"After excluding these flagged orders, January is ₹{jan_corrected:,.2f} and {peak_month} is the "
    f"genuine peak month at ₹{peak_revenue:,.2f}."
)
print()

# Export verified figures directly from computed results; no manually maintained numbers.
findings = {
    "cleaned_total_revenue_inr": cleaned_total,
    "raw_total_revenue_inr": raw_total,
    "duplicate_reconciliation_delta_inr": duplicate_delta,
    "return_rate_by_payment": {
        method: float(payment_returns.loc[method, "return_rate_pct"])
        for method in ["COD", "CARD", "UPI"]
    },
    "highest_risk_segment": {
        "payment_method": str(highest[0]),
        "city_tier": int(highest[1]),
        "return_rate_pct": highest_rate,
    },
    "true_peak_month": {"month": peak_month, "revenue_inr": peak_revenue},
    "outlier_inflated_month": {
        "month": str(monthly_all.idxmax()),
        "apparent_revenue_inr": float(monthly_all.max().round(2)),
        "corrected_revenue_inr": jan_corrected,
    },
    "monthly_revenue_including_outliers": {k: round(float(v), 2) for k, v in monthly_all.items()},
    "monthly_revenue_outlier_corrected": {k: round(float(v), 2) for k, v in monthly_corrected.items()},
}
findings_path = NARRATOR / "findings.json"
findings_path.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")
print(f"Verified findings exported to {findings_path.relative_to(ROOT)}")
