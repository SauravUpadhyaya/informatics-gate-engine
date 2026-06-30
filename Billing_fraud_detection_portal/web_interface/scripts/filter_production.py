#!/usr/bin/env python3
"""Filters the massive 475k CMS data file down to target interview demo rules."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_NCCI_PATH = ROOT / "data" / "raw" / "ncci" / "hospital_ptp.txt"
OUTPUT_PATH = ROOT / "data" / "sample" / "ncci_code_pairs_sample.csv"

# Target CPT codes present in your outpatient claims sample dataset
TARGET_CODES = {"99213", "36415", "80053", "85025", "71046", "71020", "99283", "99282", "93010", "93000", "45378", "43239", "29881", "27447"}

def main():
    if not RAW_NCCI_PATH.exists():
        print(f"Error: Could not find raw CMS file at {RAW_NCCI_PATH}")
        return

    print("Filtering live CMS text registry against active dataset codes...")
    filtered_pairs = []
    
    with open(RAW_NCCI_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for idx, line in enumerate(f):
            cleaned_line = line.strip()
            if idx < 3 or not cleaned_line or cleaned_line.startswith(("Column", "CPT", "All rights")):
                continue
            
            parts = [p.strip() for p in re.split(r'\t|\s{2,}', cleaned_line) if p.strip()]
            if len(parts) >= 2:
                col1 = parts[0].replace(".0", "")
                col2 = parts[1].replace(".0", "")
                
                # Only extract rules that actively apply to your simulated patient cohort
                if col1 in TARGET_CODES or col2 in TARGET_CODES:
                    modifier = parts[5] if len(parts) >= 6 else (parts[4] if len(parts) == 5 else "0")
                    if modifier in {"", " ", "nan", "*"}:
                        modifier = "0"
                    filtered_pairs.append({"Column 1": col1, "Column 2": col2, "Modifier Indicator": modifier})

    # Write these active rows directly over your sample config file
    import pandas as pd
    df = pd.DataFrame(filtered_pairs).drop_duplicates()
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Successfully processed live CMS file! Wrote {len(df)} active regulatory rules to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
