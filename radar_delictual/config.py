from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EVIDENCE_DIR = DATA_DIR / "evidence"
PUBLIC_DIR = ROOT / "public"
TARGET_START_YEAR = 2020
# Último año comparable completo de Fiscalía; CEAD se sondea dinámicamente hasta el año corriente.
TARGET_END_YEAR = 2025
USER_AGENT = "RadarDelictualChile/0.4 (+OSINT; public-data research; source-audited)"
TIMEOUT_SECONDS = 45
for directory in (REFERENCE_DIR, RAW_DIR, PROCESSED_DIR, EVIDENCE_DIR, PUBLIC_DIR):
    directory.mkdir(parents=True, exist_ok=True)
