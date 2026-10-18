# Mamaearth Returns & Revenue Analysis

A reproducible, three-layer analytics project that checks whether order returns may be putting pressure on revenue. It keeps raw source data unchanged, computes cleaned findings in pandas, and passes those computed figures to a short business narrative.

## Repository structure

```text
.
├── README.md
├── requirements.txt
├── sql/
│   ├── schema.sql
│   ├── seed_data.sql
│   └── reports.sql
├── data/
│   ├── customers.csv
│   ├── products.csv
│   └── orders.csv
├── analysis/
│   ├── clean_and_eda.py
│   └── visualize.py
├── visualizations/
│   ├── return_rate_by_payment.png
│   └── monthly_revenue_trend.png
└── narrator/
    ├── findings.json
    ├── generate_narrative.py
    └── sample_output.txt
```

## Requirements

- Python 3.10 or newer
- SQLite 3
- Python packages listed in `requirements.txt`

Install the Python dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

The analysis and offline narrative fallback do not require a Gemini API key. The Gemini package is included for the optional online path.

## Run the project in order

### 1. Load SQLite and run the SQL reports

From the repository root, create and seed a local database:

```bash
sqlite3 mamaearth.db < sql/schema.sql
sqlite3 mamaearth.db < sql/seed_data.sql
```

Run the reports:

```bash
sqlite3 mamaearth.db < sql/reports.sql
```

The schema defines `customers`, `products`, and `orders` with primary and foreign keys. The seed script is generated from the supplied CSV data, preserves blank discount and rating values as SQL `NULL`, and can be rerun to reload the source rows.

The reports cover order totals, missing ratings, customers with no orders (verified independently with `LEFT JOIN` and `NOT IN`), city return rates, customer spend rankings, category revenue, name matching, acquisition sources, and loyalty tiers.

**Important:** `reports.sql` includes the required `ALTER TABLE customers ADD COLUMN loyalty_tier` exercise. Run it once per newly initialized database. If you want to rerun the reports from scratch, recreate the database using the two commands above first. The seed data is intentionally raw; do not manually edit the CSVs to remove duplicates or fill blanks.

### 2. Run the independent pandas cleaning and EDA pipeline

```bash
python analysis/clean_and_eda.py
python analysis/visualize.py
```

`clean_and_eda.py` reads the three CSV files directly, not the SQLite database. It prints the inspection, standardization, deduplication, imputation, revenue reconciliation, IQR outlier checks, payment return rates, city-tier segmentation, correlation results, and monthly revenue series.

The five duplicate submissions are detected using the natural order attributes rather than `order_id`. The two unusually high-quantity orders are flagged for analysis; they are not deleted from the cleaned dataset. The script writes `narrator/findings.json` from the computed results at the end of the run. This file is the hand-off between the pandas layer and the narrator.

`visualize.py` reads the generated findings JSON and recreates both PNGs. The monthly chart uses the outlier-corrected series.

### 3. Generate the SCR narrative

#### Offline mode — no API key or network required

```bash
python narrator/generate_narrative.py
```

If `GEMINI_API_KEY` is not set, the script uses a deterministic local template. It writes the resulting narrative to `narrator/sample_output.txt` and runs a numeric accuracy checker against that saved text. This path is available without a key and does not make a network request.

#### Optional Gemini mode

Google AI Studio provides a free Gemini API usage tier subject to its current quotas and terms. Create a key there and set it as an environment variable; do not commit the key to GitHub.

macOS/Linux:

```bash
export GEMINI_API_KEY="your_api_key_here"
python narrator/generate_narrative.py
```

Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="your_api_key_here"
python narrator/generate_narrative.py
```

The script uses `GEMINI_MODEL` if set; otherwise it defaults to `gemini-2.5-flash`. Temperature is locked to `0.0`, output length is explicit, and the request has a timeout. If the API call fails, the script falls back to the offline template. The generated sample is checked for all required figures before the run is considered successful.

For a submission that demonstrates the online path, run the script once with a valid free-tier key and commit the actual generated `narrator/sample_output.txt`. Never label offline output as a Gemini response. The committed sample in a keyless environment is the deterministic offline narrative.

## Data flow and reproducibility

1. **Raw CSVs → SQLite:** `sql/seed_data.sql` loads the same supplied rows used by the SQL reports.
2. **Raw CSVs → pandas:** `analysis/clean_and_eda.py` independently cleans the source data and computes the cleaned revenue, return rates, segment risk, and monthly series.
3. **Pandas findings → JSON:** the analysis script writes `narrator/findings.json`; the JSON is generated, not manually maintained.
4. **JSON → narrative and charts:** `generate_narrative.py` uses the findings JSON for the online prompt or offline template, and `visualize.py` uses the same verified findings for the two PNG charts.

The SQL layer intentionally reports the raw order records, while the pandas layer removes duplicate submissions and imputes missing values. The raw-to-cleaned revenue difference is reconciled against the value of the duplicate rows; the imputations do not alter order value.

## Key interpretation

The analysis identifies COD as the payment method with the highest return rate and COD orders in Tier-2 cities as the highest-risk segment. It also shows why the monthly revenue series should be interpreted after flagging unusually large quantities: the January peak is inflated by two bulk orders, while the outlier-corrected series peaks in March. These are associations and operational leads to investigate, not proof that payment method itself causes returns.

## Re-run from a clean state

To regenerate all outputs:

```bash
python analysis/clean_and_eda.py
python analysis/visualize.py
python narrator/generate_narrative.py
```

To re-run SQL from scratch, recreate the SQLite database using the commands in Step 1 before executing `reports.sql`.
