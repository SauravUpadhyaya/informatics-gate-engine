import random
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from . import config


@st.cache_data
def generate_mock_data(n: int = 200) -> pd.DataFrame:
    """Build a deterministic synthetic claims DataFrame (seed source for the DB).

    Models CMS SynPUF-style claims with DRG codes, billed/allowed/paid amounts,
    derived overpayment flags, randomly assigned FWA alerts, and synthetic PII.
    The seed is fixed so KPIs are stable across reruns.
    """
    random.seed(42)
    drg_map = {
        "470": "Major Joint Replacement",
        "291": "Heart Failure & Shock w/ MCC",
        "392": "Esophagitis, Gastroenteritis",
        "683": "Renal Failure w/ MCC",
        "194": "Simple Pneumonia w/ MCC",
        "765": "Cesarean Section w/ MCC",
        "101": "Seizures w/ MCC",
        "247": "Perc Cardiovasc w/ Drug Stent",
        "871": "Septicemia w/ MV >96 hrs",
        "378": "GI Hemorrhage w/ MCC",
    }
    fwa_types = [
        "Upcoding Suspected", "Duplicate Claim", "Unbundling Detected",
        "Billing Anomaly", "Identity Mismatch", None, None, None, None, None,
    ]
    statuses = ["Paid", "Denied", "Pending", "Adjusted", "Under Review"]
    payers = ["Medicare Advantage", "Medicaid MCO", "Commercial PPO", "Self-Insured Employer"]
    # Synthetic PII name pools (these fields are protected; see schema.PII_COLUMNS).
    first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
                   "David", "Barbara", "Maria", "Jose", "Wei", "Aisha", "Carlos", "Fatima"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
                  "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Lee"]
    streets = ["Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Elm St", "Pine Rd", "Lake Blvd", "Hill Ct"]

    rows = []
    for i in range(n):
        drg_code = random.choice(list(drg_map.keys()))
        billed = round(random.uniform(4000, 95000), 2)
        allowed = round(billed * random.uniform(0.45, 0.85), 2)
        paid = round(allowed * random.uniform(0.8, 1.05), 2)
        overpay = max(0, round(paid - allowed, 2))
        fwa = random.choice(fwa_types)
        dos = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 364))
        fn, ln = random.choice(first_names), random.choice(last_names)
        dob = datetime(1945, 1, 1) + timedelta(days=random.randint(0, 27000))
        rows.append({
            "ClaimID": f"CLM{100000 + i}",
            "MemberID": f"M{random.randint(10000, 99999)}",
            "ProviderNPI": f"NPI{random.randint(1000000000, 9999999999)}",
            "PlanType": random.choice(payers),
            "DRGCode": drg_code,
            "DRGDescription": drg_map[drg_code],
            "DateOfService": dos.strftime("%Y-%m-%d"),
            "ClaimStatus": random.choice(statuses),
            "BilledAmount": billed,
            "AllowedAmount": allowed,
            "PaidAmount": paid,
            "OverpaymentAmt": overpay,
            "OverpaymentFlag": overpay > 500,
            "FWAFlag": fwa is not None,
            "FWAType": fwa or "None",
            "DaysInHospital": random.randint(1, 14),
            "PrimaryDx": random.choice(["I50.9", "J18.9", "N18.6", "K92.1", "G40.909", "O82", "I21.3", "A41.9"]),
            # ── PII (direct identifiers) — protected; see schema.PII_COLUMNS ──
            "MemberName": f"{fn} {ln}",
            "SSN": f"{random.randint(100, 899)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}",
            "DateOfBirth": dob.strftime("%Y-%m-%d"),
            "Email": f"{fn.lower()}.{ln.lower()}{random.randint(1, 99)}@example.com",
            "Phone": f"({random.randint(200, 989)}) {random.randint(200, 989)}-{random.randint(1000, 9999)}",
            "StreetAddress": f"{random.randint(100, 9999)} {random.choice(streets)}",
        })
    return pd.DataFrame(rows)


@st.cache_resource(show_spinner=False)
def init_db() -> str:
    """Create and seed the SQLite claims table if it doesn't already exist.

    Idempotent and cached so seeding runs at most once per session. Returns the
    absolute path to the database file.
    """
    conn = sqlite3.connect(config.DB_PATH)
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (config.TABLE,)
        ).fetchone()
        if exists is None:
            generate_mock_data().to_sql(config.TABLE, conn, index=False)
            conn.commit()
        return str(config.DB_PATH)
    finally:
        conn.close()


@st.cache_data(show_spinner=False)
def load_claims() -> pd.DataFrame:
    """Load all claims from SQLite, restoring boolean flags (stored as 0/1)."""
    init_db()
    conn = sqlite3.connect(config.DB_PATH)
    try:
        data = pd.read_sql_query(f"SELECT * FROM {config.TABLE}", conn)
    finally:
        conn.close()
    for col in config.BOOL_COLS:
        data[col] = data[col].astype(bool)
    return data


def run_sql(sql: str) -> pd.DataFrame:
    """Execute a read-only SELECT against the claims DB and return the rows."""
    conn = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def compute_kpis(data: pd.DataFrame) -> dict:
    """Summary metrics for the dashboard cards over a (full or filtered) slice."""
    return {
        "total_claims": len(data),
        "total_paid": data["PaidAmount"].sum(),
        "total_overpayment": data[data["OverpaymentFlag"]]["OverpaymentAmt"].sum(),
        "fwa_count": int(data["FWAFlag"].sum()),
        "pending_count": int((data["ClaimStatus"] == "Pending").sum()),
        "denied_count": int((data["ClaimStatus"] == "Denied").sum()),
        "overpay_rate": data["OverpaymentFlag"].mean() * 100,
        "fwa_rate": data["FWAFlag"].mean() * 100,
    }