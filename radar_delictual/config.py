from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EVIDENCE_DIR = DATA_DIR / "evidence"
PUBLIC_DIR = ROOT / "public"

TARGET_START_YEAR = 2020
TARGET_END_YEAR = 2025  # 2026 se incorpora vía fuentes incrementales/boletines cuando exista período comparable.
USER_AGENT = "RadarDelictualChile/0.1 (+OSINT; public-data research)"
TIMEOUT_SECONDS = 45

for directory in (RAW_DIR, PROCESSED_DIR, EVIDENCE_DIR, PUBLIC_DIR):
    directory.mkdir(parents=True, exist_ok=True)
