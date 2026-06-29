#!/usr/bin/env python3
"""Programmatically generates exactly 200 sandbox claims to populate the Cotiviti Dashboard."""
import random
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # 🛠️ Navigation fix: goes from scripts/ up to HEALTH_PROJECT/
OUTPUT_PATH = ROOT / "data" / "sample" / "outpatient_claims_sample.csv"


UNBUNDLED_PAIRS = [("99214", "36415"), ("99213", "36415"), ("80053", "36415"), ("45378", "43239")]
UPCODING_CODES = ["99283", "99282", "93010", "93000", "29881", "27447"]

def generate_data():
    print("Generating exactly 200 production-level sandbox claims...")
    
    # 68-field layout structure mapping to your CMS DE-SynPUF relational database schema
    header = ["DESYNPUF_ID", "CLM_ID", "SEGMENT", "CLM_FROM_DT", "CLM_THRU_DT", "PRVDR_NUM", "CLM_PMT_AMT", "PRIMARY_DX", "HCPCS_CD", "HCPCS_MDFR_CD_1"]
    header += [f"EXTRA_COL_{i}" for i in range(58)]
    
    rows = []
    
    # 1. Programmatically inject 80 rows of Unbundling exceptions (40 cases x 2 rows each)
    for i in range(1, 41):
        pat_id = f"PAT_UNB_{i:03d}"
        clm_id = f"CLM_UNB_{1000 + i}"
        code_a, code_b = random.choice(UNBUNDLED_PAIRS)
        provider = f"PRV{random.choice(['005', '020', '040'])}"
        
        row_a = [pat_id, clm_id, "1", "20260601", "20260601", provider, "150.00", "4659", code_a, ""] + [""] * 58
        row_b = [pat_id, clm_id, "1", "20260601", "20260601", provider, "45.00", "4659", code_b, ""] + [""] * 58
        rows.extend([row_a, row_b])
        
    # 2. Programmatically inject 120 rows of Upcoding complexity variations to bring the total to 200
    for i in range(1, 121):
        pat_id = f"PAT_UPC_{i:03d}"
        clm_id = f"CLM_UPC_{2000 + i}"
        code = random.choice(UPCODING_CODES)
        provider = f"PRV{random.choice(['005', '020', '040'])}"
        payment = str(round(random.uniform(1200.00, 4800.00), 2))
        
        row_upc = [pat_id, clm_id, "1", "20260601", "20260601", provider, payment, "7865", code, ""] + [""] * 58
        rows.append(row_upc)

    # Write out exactly 200 records down to the staging directory path
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
        
    print(f"Successfully generated high-volume dataset! Wrote {len(rows)} lines to {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_data()
