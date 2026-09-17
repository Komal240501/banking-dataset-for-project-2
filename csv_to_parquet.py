"""
Converts all bank-data CSV files to Parquet (snappy-compressed) so they fit
GitHub's file-size limits (25MB via web upload, 100MB hard cap via git push).
Parquet is typically 5-10x smaller than CSV for the same data.

Handles both plain .csv files and .gz-compressed CSVs (card_transaction,
transaction_list), and outputs everything into ./data as .parquet.

Requires: pip install pandas pyarrow
"""
import os
import gzip
import pandas as pd

SRC_DIR = "/mnt/user-data/uploads"
OUT_DIR = "/mnt/user-data/outputs/data"
MAX_MB_BEFORE_WARN = 25  # GitHub's web-upload limit

os.makedirs(OUT_DIR, exist_ok=True)

# name -> (filename in SRC_DIR, is_gzipped)
files = {
    "accounts": ("accounts.csv", False),
    "branches": ("branches.csv", False),
    "cards": ("cards.csv", False),
    "customers": ("customers.csv", False),
    "employees": ("employees.csv", False),
    "loan": ("loan.csv", False),
    "loan_payment": ("loan_payment.csv", False),
    "support_ticket": ("support_ticket.csv", False),
    "card_transaction": ("card_transaction_csv.gz", True),
    "transaction_list": ("transaction_list_csv.gz", True),
}

print(f"{'file':<20}{'rows':>10}{'csv/gz MB':>12}{'parquet MB':>12}   status")
print("-" * 70)

for name, (fname, gzipped) in files.items():
    src_path = os.path.join(SRC_DIR, fname)
    src_size_mb = os.path.getsize(src_path) / (1024 * 1024)

    opener = gzip.open if gzipped else open
    with opener(src_path, "rt") as f:
        df = pd.read_csv(f)

    # Brotli compresses the two large event-level tables noticeably better
    # than the default snappy codec (at the cost of slightly slower writes).
    compression = "brotli" if gzipped else "snappy"

    out_path = os.path.join(OUT_DIR, f"{name}.parquet")
    if compression == "brotli":
        df.to_parquet(out_path, index=False, compression="brotli", compression_level=11)
    else:
        df.to_parquet(out_path, index=False, compression=compression)
    out_size_mb = os.path.getsize(out_path) / (1024 * 1024)

    flag = "OK" if out_size_mb <= MAX_MB_BEFORE_WARN else "<-- still large"
    print(f"{name:<20}{len(df):>10}{src_size_mb:>12.1f}{out_size_mb:>12.2f}   {flag}")

print("\nDone. Files are in", OUT_DIR)
