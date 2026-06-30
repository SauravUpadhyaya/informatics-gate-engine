from pathlib import Path

from pydantic_settings import BaseSettings


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Pre-Adjudication Compliance Engine"
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'compliance.db'}"
    data_dir: Path = PROJECT_ROOT / "data"
    sample_claims_path: Path = data_dir / "sample" / "outpatient_claims_sample.csv"
    sample_ncci_path: Path = data_dir / "sample" / "ncci_code_pairs_sample.csv"
    upcoding_zscore_threshold: float = 2.5
    upcoding_min_group_size: int = 5

    class Config:
        env_prefix = "PAE_"


settings = Settings()
