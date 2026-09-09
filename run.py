import argparse
import json

from radar_delictual.geographic_score_runtime import materialize_geographic_score
from radar_delictual.geographic_score_v11_runtime import materialize_geographic_score_v11_candidate
from radar_delictual.pipeline import run
from scripts.build_territory_interop import main as build_territory_interop

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Radar Delictual Chile")
    parser.add_argument("--offline", action="store_true", help="No acceder a Internet; reutiliza el último dato generado.")
    args = parser.parse_args()
    result = run(offline=args.offline)
    result["cead_geographic_score"] = materialize_geographic_score()
    result["cead_geographic_score_candidate"] = materialize_geographic_score_v11_candidate(offline=args.offline)
    build_territory_interop()
    print(json.dumps(result, ensure_ascii=False, indent=2))
