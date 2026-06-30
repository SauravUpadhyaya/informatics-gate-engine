#!/usr/bin/env python3
"""Generate DE-SynPUF-style sample claims and NCCI pairs for demo/testing."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "data" / "sample"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

# Realistic NCCI PTP pairs (subset of CMS Hospital/Practitioner edits)
NCCI_PAIRS = [
    {"Column 1": "99213", "Column 2": "36415", "Modifier Indicator": "1"},
    {"Column 1": "99214", "Column 2": "36415", "Modifier Indicator": "1"},
    {"Column 1": "80053", "Column 2": "36415", "Modifier Indicator": "1"},
    {"Column 1": "85025", "Column 2": "36415", "Modifier Indicator": "1"},
    {"Column 1": "71046", "Column 2": "71020", "Modifier Indicator": "1"},
    {"Column 1": "99283", "Column 2": "99282", "Modifier Indicator": "1"},
    {"Column 1": "93010", "Column 2": "93000", "Modifier Indicator": "1"},
    {"Column 1": "45378", "Column 2": "43239", "Modifier Indicator": "0"},
    {"Column 1": "29881", "Column 2": "27447", "Modifier Indicator": "1"},
    {"Column 1": "99215", "Column 2": "99214", "Modifier Indicator": "1"},
    {"Column 1": "71260", "Column 2": "71250", "Modifier Indicator": "1"},
    {"Column 1": "93458", "Column 2": "92928", "Modifier Indicator": "0"},
]

CLAIMS = [
    # Clean claims - minor respiratory
    {"DESYNPUF_ID": "PAT001", "CLM_ID": "CLM1001", "SEGMENT": 1, "CLM_FROM_DT": "20090115", "CLM_THRU_DT": "20090115", "PRVDR_NUM": "PRV001", "CLM_PMT_AMT": 85.0, "ICD9_DGNS_CD_1": "4659", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT001", "CLM_ID": "CLM1002", "SEGMENT": 1, "CLM_FROM_DT": "20090220", "CLM_THRU_DT": "20090220", "PRVDR_NUM": "PRV001", "CLM_PMT_AMT": 72.0, "ICD9_DGNS_CD_1": "4619", "HCPCS_CD_1": "99212", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT002", "CLM_ID": "CLM1003", "SEGMENT": 1, "CLM_FROM_DT": "20090310", "CLM_THRU_DT": "20090310", "PRVDR_NUM": "PRV002", "CLM_PMT_AMT": 90.0, "ICD9_DGNS_CD_1": "460", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT003", "CLM_ID": "CLM1004", "SEGMENT": 1, "CLM_FROM_DT": "20090405", "CLM_THRU_DT": "20090405", "PRVDR_NUM": "PRV003", "CLM_PMT_AMT": 68.0, "ICD9_DGNS_CD_1": "462", "HCPCS_CD_1": "99212", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT004", "CLM_ID": "CLM1005", "SEGMENT": 1, "CLM_FROM_DT": "20090512", "CLM_THRU_DT": "20090512", "PRVDR_NUM": "PRV001", "CLM_PMT_AMT": 95.0, "ICD9_DGNS_CD_1": "4650", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT005", "CLM_ID": "CLM1006", "SEGMENT": 1, "CLM_FROM_DT": "20090601", "CLM_THRU_DT": "20090601", "PRVDR_NUM": "PRV004", "CLM_PMT_AMT": 78.0, "ICD9_DGNS_CD_1": "460", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT006", "CLM_ID": "CLM1007", "SEGMENT": 1, "CLM_FROM_DT": "20090718", "CLM_THRU_DT": "20090718", "PRVDR_NUM": "PRV002", "CLM_PMT_AMT": 82.0, "ICD9_DGNS_CD_1": "4610", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    # UNBUNDLING: 99213 + 36415 same day (NCCI violation)
    {"DESYNPUF_ID": "PAT010", "CLM_ID": "CLM2001", "SEGMENT": 1, "CLM_FROM_DT": "20090801", "CLM_THRU_DT": "20090801", "PRVDR_NUM": "PRV005", "CLM_PMT_AMT": 110.0, "ICD9_DGNS_CD_1": "4659", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "36415", "HCPCS_CD_3": ""},
    # UNBUNDLING: 80053 + 36415 same day
    {"DESYNPUF_ID": "PAT011", "CLM_ID": "CLM2002", "SEGMENT": 1, "CLM_FROM_DT": "20090815", "CLM_THRU_DT": "20090815", "PRVDR_NUM": "PRV006", "CLM_PMT_AMT": 145.0, "ICD9_DGNS_CD_1": "25000", "HCPCS_CD_1": "80053", "HCPCS_CD_2": "36415", "HCPCS_CD_3": "99213"},
    # UNBUNDLING: 71046 + 71020 same day (chest x-ray unbundling)
    {"DESYNPUF_ID": "PAT012", "CLM_ID": "CLM2003", "SEGMENT": 1, "CLM_FROM_DT": "20090901", "CLM_THRU_DT": "20090901", "PRVDR_NUM": "PRV007", "CLM_PMT_AMT": 320.0, "ICD9_DGNS_CD_1": "486", "HCPCS_CD_1": "71046", "HCPCS_CD_2": "71020", "HCPCS_CD_3": "99214"},
    # UPCODING: minor URI dx but high-complexity cardiac cath
    {"DESYNPUF_ID": "PAT020", "CLM_ID": "CLM3001", "SEGMENT": 1, "CLM_FROM_DT": "20091010", "CLM_THRU_DT": "20091010", "PRVDR_NUM": "PRV008", "CLM_PMT_AMT": 4200.0, "ICD9_DGNS_CD_1": "4659", "HCPCS_CD_1": "93458", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    # UPCODING: acute pharyngitis with knee arthroscopy
    {"DESYNPUF_ID": "PAT021", "CLM_ID": "CLM3002", "SEGMENT": 1, "CLM_FROM_DT": "20091022", "CLM_THRU_DT": "20091022", "PRVDR_NUM": "PRV009", "CLM_PMT_AMT": 3800.0, "ICD9_DGNS_CD_1": "462", "HCPCS_CD_1": "29881", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    # More baseline respiratory claims for statistical power
    {"DESYNPUF_ID": "PAT022", "CLM_ID": "CLM3003", "SEGMENT": 1, "CLM_FROM_DT": "20091101", "CLM_THRU_DT": "20091101", "PRVDR_NUM": "PRV001", "CLM_PMT_AMT": 88.0, "ICD9_DGNS_CD_1": "4659", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT023", "CLM_ID": "CLM3004", "SEGMENT": 1, "CLM_FROM_DT": "20091105", "CLM_THRU_DT": "20091105", "PRVDR_NUM": "PRV002", "CLM_PMT_AMT": 75.0, "ICD9_DGNS_CD_1": "460", "HCPCS_CD_1": "99212", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT024", "CLM_ID": "CLM3005", "SEGMENT": 1, "CLM_FROM_DT": "20091110", "CLM_THRU_DT": "20091110", "PRVDR_NUM": "PRV003", "CLM_PMT_AMT": 92.0, "ICD9_DGNS_CD_1": "4619", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT025", "CLM_ID": "CLM3006", "SEGMENT": 1, "CLM_FROM_DT": "20091115", "CLM_THRU_DT": "20091115", "PRVDR_NUM": "PRV004", "CLM_PMT_AMT": 80.0, "ICD9_DGNS_CD_1": "462", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT026", "CLM_ID": "CLM3007", "SEGMENT": 1, "CLM_FROM_DT": "20091120", "CLM_THRU_DT": "20091120", "PRVDR_NUM": "PRV005", "CLM_PMT_AMT": 86.0, "ICD9_DGNS_CD_1": "4650", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    # Hypertension baseline claims
    {"DESYNPUF_ID": "PAT030", "CLM_ID": "CLM4001", "SEGMENT": 1, "CLM_FROM_DT": "20091201", "CLM_THRU_DT": "20091201", "PRVDR_NUM": "PRV010", "CLM_PMT_AMT": 120.0, "ICD9_DGNS_CD_1": "4019", "HCPCS_CD_1": "99214", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT031", "CLM_ID": "CLM4002", "SEGMENT": 1, "CLM_FROM_DT": "20091205", "CLM_THRU_DT": "20091205", "PRVDR_NUM": "PRV010", "CLM_PMT_AMT": 115.0, "ICD9_DGNS_CD_1": "4011", "HCPCS_CD_1": "99214", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT032", "CLM_ID": "CLM4003", "SEGMENT": 1, "CLM_FROM_DT": "20091210", "CLM_THRU_DT": "20091210", "PRVDR_NUM": "PRV011", "CLM_PMT_AMT": 130.0, "ICD9_DGNS_CD_1": "4019", "HCPCS_CD_1": "99214", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT033", "CLM_ID": "CLM4004", "SEGMENT": 1, "CLM_FROM_DT": "20091215", "CLM_THRU_DT": "20091215", "PRVDR_NUM": "PRV011", "CLM_PMT_AMT": 125.0, "ICD9_DGNS_CD_1": "4010", "HCPCS_CD_1": "99214", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT034", "CLM_ID": "CLM4005", "SEGMENT": 1, "CLM_FROM_DT": "20091220", "CLM_THRU_DT": "20091220", "PRVDR_NUM": "PRV012", "CLM_PMT_AMT": 118.0, "ICD9_DGNS_CD_1": "4019", "HCPCS_CD_1": "99213", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    {"DESYNPUF_ID": "PAT035", "CLM_ID": "CLM4006", "SEGMENT": 1, "CLM_FROM_DT": "20091225", "CLM_THRU_DT": "20091225", "PRVDR_NUM": "PRV012", "CLM_PMT_AMT": 122.0, "ICD9_DGNS_CD_1": "4011", "HCPCS_CD_1": "99214", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    # UPCODING: hypertension dx with cardiac cath
    {"DESYNPUF_ID": "PAT040", "CLM_ID": "CLM5001", "SEGMENT": 1, "CLM_FROM_DT": "20100105", "CLM_THRU_DT": "20100105", "PRVDR_NUM": "PRV013", "CLM_PMT_AMT": 5100.0, "ICD9_DGNS_CD_1": "4019", "HCPCS_CD_1": "93458", "HCPCS_CD_2": "", "HCPCS_CD_3": ""},
    # UNBUNDLING: 99283 + 99282 ER level unbundling
    {"DESYNPUF_ID": "PAT041", "CLM_ID": "CLM5002", "SEGMENT": 1, "CLM_FROM_DT": "20100110", "CLM_THRU_DT": "20100110", "PRVDR_NUM": "PRV014", "CLM_PMT_AMT": 450.0, "ICD9_DGNS_CD_1": "78900", "HCPCS_CD_1": "99283", "HCPCS_CD_2": "99282", "HCPCS_CD_3": "93000"},
    # Clean diabetes follow-up
    {"DESYNPUF_ID": "PAT050", "CLM_ID": "CLM6001", "SEGMENT": 1, "CLM_FROM_DT": "20100201", "CLM_THRU_DT": "20100201", "PRVDR_NUM": "PRV015", "CLM_PMT_AMT": 140.0, "ICD9_DGNS_CD_1": "25000", "HCPCS_CD_1": "99214", "HCPCS_CD_2": "80053", "HCPCS_CD_3": ""},
]


def main():
    claims_df = pd.DataFrame(CLAIMS)
    for i in range(4, 46):
        col = f"HCPCS_CD_{i}"
        if col not in claims_df.columns:
            claims_df[col] = ""
    for i in range(2, 11):
        col = f"ICD9_DGNS_CD_{i}"
        if col not in claims_df.columns:
            claims_df[col] = ""
    for i in range(1, 7):
        col = f"ICD9_PRCDR_CD_{i}"
        if col not in claims_df.columns:
            claims_df[col] = ""

    ncci_df = pd.DataFrame(NCCI_PAIRS)

    claims_path = SAMPLE_DIR / "outpatient_claims_sample.csv"
    ncci_path = SAMPLE_DIR / "ncci_code_pairs_sample.csv"

    claims_df.to_csv(claims_path, index=False)
    ncci_df.to_csv(ncci_path, index=False)

    print(f"Wrote {len(claims_df)} claims -> {claims_path}")
    print(f"Wrote {len(ncci_df)} NCCI pairs -> {ncci_path}")


if __name__ == "__main__":
    main()
