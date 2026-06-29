"""Load CMS DE-SynPUF claims and NCCI code pair tables into the database."""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from app.models import ClaimLine, NCCIPair

# 45 dynamic wide layout column arrays matching CMS standard guidelines
HCPCS_COLUMNS = [f"HCPCS_CD_{i}" for i in range(1, 46)]
DX_COLUMNS = [f"ICD9_DGNS_CD_{i}" for i in range(1, 11)]
PROC_COLUMNS = [f"ICD9_PRCDR_CD_{i}" for i in range(1, 7)]

def _parse_date(value) -> datetime.date | None:
    if pd.isna(value) or value == "" or value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None

def _normalize_code(value) -> str | None:
    if pd.isna(value) or value == "" or value is None:
        return None
    # Strip any floating-point representations introduced by pandas parser engines
    code = str(value).strip().upper().replace(".0", "")
    return code or None

def _collect_codes(row: pd.Series, columns: list[str]) -> list[str]:
    codes: list[str] = []
    for col in columns:
        if col in row.index:
            code = _normalize_code(row[col])
            if code and code not in codes:
                codes.append(code)
    return codes

def load_claims_csv(db: Session, csv_path: Path, limit: int | None = None) -> dict:
    """Ingest outpatient or inpatient-style CMS claim CSV into claim_lines."""
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    if limit:
        df = df.head(limit)
        
    records: list[ClaimLine] = []
    
    for _, row in df.iterrows():
        service_date = _parse_date(row.get("CLM_FROM_DT")) or _parse_date(row.get("CLM_THRU_DT"))
        if not service_date:
            continue
            
        dx_codes = _collect_codes(row, DX_COLUMNS)
        proc_codes = _collect_codes(row, PROC_COLUMNS)
        
        # DOMAIN LOGIC EXTRACTION MATRIX:
        # Line up procedure slots and capture corresponding column modifiers dynamically
        valid_hcpcs_list = []
        slot_mappings = []  # List of dicts: {"code": X, "modifier": Y}
        
        for i in range(1, 46):
            code_col = f"HCPCS_CD_{i}"
            mod_col = f"HCPCS_MDFR_CD_{i}"
            
            if code_col in row.index:
                code_val = _normalize_code(row[code_col])
                if code_val:
                    valid_hcpcs_list.append(code_val)
                    # Pull modifier from matching spatial horizontal column slot
                    mod_val = _normalize_code(row[mod_col]) if mod_col in row.index else None
                    slot_mappings.append({"code": code_val, "modifier": mod_val})
                    
        # Fallback to ICD-9 procedure matrices if HCPCS blocks are completely missing
        if not valid_hcpcs_list and proc_codes:
            valid_hcpcs_list = proc_codes
            slot_mappings = [{"code": c, "modifier": None} for c in proc_codes]
            
        if not valid_hcpcs_list:
            continue
            
        drg = _normalize_code(row.get("CLM_DRG_CD"))
        primary_dx = dx_codes[0] if dx_codes else None
        payment = float(row.get("CLM_PMT_AMT") or 0)
        
        # Instantiate transactional record line items
        for idx, mapping in enumerate(slot_mappings):
            # Allocate financial cost to primary slot item to safeguard aggregation thresholds
            line_payment = payment if idx == 0 else 0.0
            
            records.append(
                ClaimLine(
                    desynpuf_id=str(row.get("DESYNPUF_ID", "")).strip(),
                    clm_id=str(row.get("CLM_ID", "")).strip(),
                    segment=int(float(row.get("SEGMENT") or idx + 1)),
                    service_date=service_date,
                    clm_from_dt=_parse_date(row.get("CLM_FROM_DT")),
                    clm_thru_dt=_parse_date(row.get("CLM_THRU_DT")),
                    prvdr_num=_normalize_code(row.get("PRVDR_NUM")),
                    clm_pmt_amt=line_payment,
                    primary_dx=primary_dx,
                    drg_cd=drg,
                    hcpcs_cd=mapping["code"],
                    hcpc_mdfr_cd_1=mapping["modifier"],  # <-- Essential mapping bridge closed
                    dx_codes_json=json.dumps(dx_codes),
                    proc_codes_json=json.dumps(proc_codes),
                    all_hcpcs_json=json.dumps(valid_hcpcs_list),
                )
            )
            
    db.query(ClaimLine).delete()
    db.bulk_save_objects(records)
    db.commit()
    return {"claims_loaded": len(records), "unique_claims": df["CLM_ID"].nunique()}

def _detect_ncci_columns(df: pd.DataFrame) -> tuple[str, str]:
    normalized = {re.sub(r"[^a-z0-9]", "", col.lower()): col for col in df.columns}
    col_a_candidates = [
        "column1", "columnone", "comprehensivecode", "procedurecodea", "cptcode1", "hcpcscode1",
    ]
    col_b_candidates = [
        "column2", "columntwo", "componentcode", "procedurecodeb", "cptcode2", "hcpcscode2",
    ]
    col_a = next((normalized[c] for c in col_a_candidates if c in normalized), None)
    col_b = next((normalized[c] for c in col_b_candidates if c in normalized), None)
    
    if col_a and col_b:
        return col_a, col_b
        
    code_cols = [c for c in df.columns if re.search(r"(column|code|cpt|hcpcs)", c, re.I)]
    if len(code_cols) >= 2:
        return code_cols[0], code_cols[1]
        
    raise ValueError("Could not detect NCCI column pair fields. Expected Column 1 / Column 2 style headers.")

def load_ncci_file(db: Session, file_path: Path) -> dict:
    """
    Loads raw CMS NCCI PTP registries positionally.
    Utilizes regular expression split patterns to process variable multi-space columns.
    """
    import re
    suffix = file_path.suffix.lower()
    raw_rows = []

    if suffix in {".xlsx", ".xls"}:
        # 1. HARDENED EXCEL POSITIONING ROUTINE
        df = pd.read_excel(file_path, skiprows=4, header=None, dtype=str)
        for _, row in df.iterrows():
            if len(row) >= 2:
                code_a = str(row.iloc[0]).strip()
                code_b = str(row.iloc[1]).strip()
                modifier = str(row.iloc[5]).strip() if len(row) >= 6 else "0"
                raw_rows.append((code_a, code_b, modifier))
    else:
        # 2. BULLETPROOF FLAT TEXT REGEX STREAMING ROUTINE
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                cleaned_line = line.strip()
                
                # Instantly bypass disclaimers, text noise, or headers seen in your dump
                if not cleaned_line or cleaned_line.startswith(("Column", "CPT", "All rights", "*")):
                    continue
                
                # FIX: Split columns using a regular expression that treats tabs OR any number of spaces as a delimiter
                parts = [p.strip() for p in re.split(r'\t|\s{2,}', cleaned_line) if p.strip()]
                
                # DATA BOUNDS GUARD: Skip lines that don't have at least Column 1 and Column 2
                if len(parts) < 2:
                    continue
                    
                code_a = str(parts[0]).strip()
                code_b = str(parts[1]).strip()
                
                # Target the Modifier column index safely based on available tokens
                modifier = "0"
                if len(parts) >= 6:
                    modifier = str(parts[5]).strip()
                elif len(parts) == 5:
                    modifier = str(parts[4]).strip()
                elif len(parts) == 4:
                    modifier = str(parts[3]).strip()
                    
                raw_rows.append((code_a, code_b, modifier))

    # Clear old compliance configurations atomically to prep for data refresh
    db.query(NCCIPair).delete()
    db.commit()

    # Deduplicate and process high-speed transactional batch insertions
    records: list[NCCIPair] = []
    seen: set[tuple[str, str]] = set()
    total_loaded = 0
    
    for code_a, code_b, modifier in raw_rows:
        norm_a = _normalize_code(code_a)
        norm_b = _normalize_code(code_b)
        
        if not norm_a or not norm_b:
            continue
            
        key = (norm_a, norm_b)
        if key in seen:
            continue
        seen.add(key)
        
        # Guard against blank spaces or string 'nan' / '*' character states coming from cells
        clean_modifier = str(modifier).strip()
        if clean_modifier in {"", " ", "nan", "None", "NULL", "*"}:
            clean_modifier = "0"
            
        records.append(
            NCCIPair(
                procedure_code_a=norm_a,
                procedure_code_b=norm_b,
                modifier_indicator=clean_modifier,
            )
        )
        
        # 10,000-row micro-batching threshold to support massive CMS files easily on local databases
        if len(records) >= 10000:
            db.bulk_save_objects(records)
            db.commit()
            total_loaded += len(records)
            records = []  # Clear the memory array buffer chunk
            
    # Flush any remaining database records out of the stream pipeline
    if records:
        db.bulk_save_objects(records)
        db.commit()
        total_loaded += len(records)
        
    return {"ncci_pairs_loaded": total_loaded}
