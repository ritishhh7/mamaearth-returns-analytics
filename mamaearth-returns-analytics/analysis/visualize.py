"""Create the two required figures from generated, verified findings.

Run after `python analysis/clean_and_eda.py`:
    python analysis/visualize.py
"""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
findings_path = ROOT / "narrator" / "findings.json"
if not findings_path.exists():
    raise FileNotFoundError("Run `python analysis/clean_and_eda.py` first to generate narrator/findings.json.")
findings = json.loads(findings_path.read_text(encoding="utf-8"))
out_dir = ROOT / "visualizations"
out_dir.mkdir(exist_ok=True)

rates = findings["return_rate_by_payment"]
methods = sorted(rates, key=lambda method: rates[method], reverse=True)
values = [rates[method] for method in methods]

fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(methods, values)
ax.set_ylabel("Return rate (%)")
ax.set_xlabel("Payment method")
ax.set_ylim(0, max(values) * 1.2)
ax.set_title(f"COD Returns at {rates['COD']:.1f}% — {rates['COD'] / rates['CARD']:.1f}x Card")
for bar, value in zip(bars, values):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.7,
            f"{value:.1f}%", ha="center", va="bottom")
fig.tight_layout()
fig.savefig(out_dir / "return_rate_by_payment.png", dpi=160, bbox_inches="tight")
plt.close(fig)

monthly = findings["monthly_revenue_outlier_corrected"]
months = list(monthly.keys())
revenues = list(monthly.values())
peak = findings["true_peak_month"]["month"]
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(months, revenues, marker="o")
ax.set_xlabel("Month")
ax.set_ylabel("Revenue (INR)")
ax.set_title(f"Outlier-Corrected Monthly Revenue — Peak: {peak}")
ax.tick_params(axis="x", rotation=30)
ax.grid(True, axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(out_dir / "monthly_revenue_trend.png", dpi=160, bbox_inches="tight")
plt.close(fig)

print(f"Saved {out_dir / 'return_rate_by_payment.png'}")
print(f"Saved {out_dir / 'monthly_revenue_trend.png'}")
