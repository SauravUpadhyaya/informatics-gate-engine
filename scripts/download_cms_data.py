import argparse
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# CMS DE-SynPUF Sample 1 Outpatient Claims (public direct link pattern)
SYNPUF_OUTPATIENT_URL = (
    "https://www.cms.gov/files/zip/"
    "de10-sample-1-2008-2010-outpatient-claims.zip"
)


def download_file(url: str, dest: Path) -> bool:
    print(f"Downloading {url} ...")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
            if response.status_code != 200:
                print(f"  Failed: HTTP {response.status_code}")
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
        print(f"  Saved to {dest}")
        return True
    except Exception as exc:
        print(f"  Error: {exc}")
        return False


def extract_zip(zip_path: Path, dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.endswith(".csv"):
                zf.extract(name, dest_dir)
                extracted.append(dest_dir / name)
    return extracted


def main():
    parser = argparse.ArgumentParser(description="Download CMS public datasets")
    parser.add_argument("--synpuf-only", action="store_true")
    args = parser.parse_args()

    zip_dest = RAW_DIR / "outpatient_claims_sample_1.zip"
    if download_file(SYNPUF_OUTPATIENT_URL, zip_dest):
        csvs = extract_zip(zip_dest, RAW_DIR / "synpuf")
        if csvs:
            print(f"Extracted {len(csvs)} CSV file(s)")
            for c in csvs:
                print(f"  {c}")
    else:
        print(
            "\nManual download: https://www.cms.gov/data-research/statistics-trends-and-reports/"
            "medicare-claims-synthetic-public-use-files/"
            "cms-2008-2010-data-entrepreneurs-synthetic-public-use-file-de-synpuf/de10-sample-1"
        )

    if not args.synpuf_only:
        print(
            "\nNCCI PTP edits must be downloaded manually from CMS (AMA license acceptance required):\n"
            "  https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/"
            "medicare-ncci-procedure-procedure-ptp-edits\n"
            "Place Hospital PTP CSV/XLSX files in data/raw/ncci/ then run:\n"
            "  curl -X POST 'http://localhost:8000/api/v1/ingest/ncci' -F 'file=@data/raw/ncci/hospital_ptp.csv'"
        )


if __name__ == "__main__":
    main()
