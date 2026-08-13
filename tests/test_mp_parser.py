from pathlib import Path
import pytest
from radar_delictual.collectors import parse_mp_workbook


def test_parser_2025_fixture_si_existe():
    p = Path("data/raw/ministerio_publico_2025.xlsx")
    if not p.exists():
        pytest.skip("workbook no precargado")
    rows = parse_mp_workbook(p, 2025)
    assert rows
    assert any(r["crime_category"] == "DELITOS LEY DE DROGAS" for r in rows)
