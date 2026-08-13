import argparse
import json

from radar_delictual.pipeline import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Radar Delictual Chile")
    parser.add_argument("--offline", action="store_true", help="No acceder a Internet; reutiliza el último dato generado.")
    args = parser.parse_args()
    print(json.dumps(run(offline=args.offline), ensure_ascii=False, indent=2))
