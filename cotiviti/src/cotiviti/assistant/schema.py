COLUMN_DOCS = {
    "ClaimID": "Unique identifier for the claim.",
    "MemberID": "Unique identifier for the patient/member on the claim.",
    "ProviderNPI": "National Provider Identifier (NPI) of the billing provider.",
    "PlanType": "Insurance plan type: Medicare Advantage, Medicaid MCO, Commercial PPO, or Self-Insured Employer.",
    "DRGCode": "Diagnosis Related Group (DRG) code for the inpatient stay.",
    "DRGDescription": "Human-readable description of the DRG code.",
    "DateOfService": "Date the service was provided, format YYYY-MM-DD.",
    "ClaimStatus": "Claim state: Paid, Denied, Pending, Adjusted, or Under Review.",
    "BilledAmount": "Dollar amount the provider billed.",
    "AllowedAmount": "Contractually allowed dollar amount for the claim.",
    "PaidAmount": "Dollar amount actually paid on the claim.",
    "OverpaymentAmt": "Dollar amount overpaid (paid above the allowed amount).",
    "OverpaymentFlag": "Whether the claim was overpaid by more than $500 (1 = yes, 0 = no).",
    "FWAFlag": "Whether the claim was flagged for Fraud, Waste, or Abuse (1 = yes, 0 = no).",
    "FWAType": "Type of FWA alert: Upcoding Suspected, Duplicate Claim, Unbundling Detected, Billing Anomaly, Identity Mismatch, or None.",
    "DaysInHospital": "Length of inpatient stay in days.",
    "PrimaryDx": "Primary diagnosis code (ICD-10) for the claim.",
}


PII_COLUMNS = {"MemberName", "SSN", "DateOfBirth", "Email", "Phone", "StreetAddress"}

assert PII_COLUMNS.isdisjoint(COLUMN_DOCS), "PII columns must not be queryable"