from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .config import PUBLIC_DIR

FOCUS = ["DELITOS LEY DE DROGAS", "DELITOS ECONÓMICOS Y TRIBUTARIOS", "DELITOS FUNCIONARIOS", "HOMICIDIOS"]


def _fmt(n):
    return f"{int(n):,}".replace(",", ".")


def build_dashboard(metrics: list[dict], risks: list[dict], source_status: list[dict], output: Path | None = None, events: list[dict] | None = None) -> Path:
    output = output or PUBLIC_DIR / "index.html"
    events = events or []
    years = sorted({int(r["year"]) for r in metrics})
    latest = max(years) if years else None
    latest_risks = sorted([r for r in risks if r["year"] == latest], key=lambda x: x["pressure_score"], reverse=True) if latest else []
    nat = defaultdict(int)
    for r in metrics:
        if r.get("territory_level") == "national" and r.get("crime_category") in FOCUS:
            nat[(r["year"], r["crime_category"])] = r["value"]
    cards = "".join(f'<div class="card"><div class="kicker">{html.escape(cat.replace("DELITOS ", ""))}</div><div class="value">{_fmt(nat.get((latest,cat),0)) if latest else "—"}</div><div class="sub">delitos ingresados · {latest or "s/d"}</div></div>' for cat in FOCUS)
    max_score = max([r["pressure_score"] for r in latest_risks] or [1])
    rank_rows = "".join(f'<tr><td>{i}</td><td>{html.escape(r["region_name"])}</td><td><div class="bar"><span style="width:{100*r["pressure_score"]/max_score:.1f}%"></span></div></td><td class="num">{r["pressure_score"]:.1f}</td><td><span class="pill {r["pressure_level"]}">{r["pressure_level"].replace("_"," ")}</span></td></tr>' for i,r in enumerate(latest_risks,1)) or '<tr><td colspan="5">Sin datos generados aún.</td></tr>'
    trend_rows = ""
    for year in years:
        vals = "".join(f"<td class='num'>{_fmt(nat.get((year,cat),0))}</td>" for cat in FOCUS)
        trend_rows += f"<tr><td>{year}</td>{vals}</tr>"
    ok = sum(1 for s in source_status if isinstance(s,dict) and s.get("ok"))
    fail = sum(1 for s in source_status if isinstance(s,dict) and s.get("ok") is False)
    def event_key(e): return (e.get("published_date") or "", e.get("retrieved_at") or "")
    recent_events = sorted(events, key=event_key, reverse=True)[:8]
    event_rows = "".join(f'<tr><td>{html.escape(e.get("published_date") or "s/f")}</td><td><a href="{html.escape(e.get("url",""))}" target="_blank" rel="noopener">{html.escape(e.get("title",""))}</a></td><td>{html.escape(", ".join(e.get("matched_keywords",[])[:3]))}</td></tr>' for e in recent_events) or '<tr><td colspan="3">Sin publicaciones monitorizadas aún.</td></tr>'
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data_payload = {"latest_year":latest,"risk":latest_risks,"source_status":source_status,"recent_events":recent_events}
    (PUBLIC_DIR / "data.json").write_text(json.dumps(data_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    doc = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Radar Delictual · Chile</title><style>
:root{{--bg:#0f1115;--panel:#171a20;--line:#2a2e36;--text:#f1f3f5;--muted:#9ca3ad;--accent:#f28c28;--accent2:#ffb86b}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Inter,system-ui,-apple-system,Segoe UI,sans-serif}}.wrap{{max-width:1280px;margin:auto;padding:28px}}header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:20px}}h1{{margin:0;font-size:30px;letter-spacing:-.6px}}.tag{{color:var(--accent);font-weight:800;text-transform:uppercase;letter-spacing:.13em;font-size:11px}}.desc{{color:var(--muted);max-width:760px;margin:7px 0 0}}.status{{text-align:right;color:var(--muted);font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.card,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:16px}}.card{{padding:18px}}.kicker{{color:var(--muted);font-size:11px;text-transform:uppercase;min-height:32px}}.value{{font-size:28px;font-weight:800;margin-top:3px}}.sub{{color:var(--muted);font-size:11px}}.two{{display:grid;grid-template-columns:1.3fr .9fr;gap:14px;margin-top:14px}}.panel{{padding:18px}}h2{{font-size:16px;margin:0 0 14px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px 8px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--muted);font-size:11px;text-transform:uppercase}}.num{{text-align:right;font-variant-numeric:tabular-nums}}.bar{{height:8px;background:#262a31;border-radius:20px;overflow:hidden;min-width:90px}}.bar span{{display:block;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:20px}}.pill{{font-size:10px;padding:4px 7px;border-radius:20px;border:1px solid var(--line)}}.muy_alta{{border-color:#ff7a55}}.alta{{border-color:#e9a14a}}.media{{border-color:#b9a36b}}.note{{margin-top:14px;padding:14px 16px;border-left:3px solid var(--accent);background:#16181d;color:#c7cbd1;border-radius:8px}}.sources{{display:flex;gap:9px;flex-wrap:wrap;margin-top:12px}}.source{{padding:8px 10px;background:#121419;border:1px solid var(--line);border-radius:9px;color:var(--muted);font-size:11px}}footer{{color:var(--muted);font-size:11px;margin-top:18px}}a{{color:var(--accent2)}}@media(max-width:850px){{.grid{{grid-template-columns:1fr 1fr}}.two{{grid-template-columns:1fr}}header{{display:block}}.status{{text-align:left;margin-top:10px}}}}@media(max-width:520px){{.grid{{grid-template-columns:1fr}}.wrap{{padding:16px}}}}
</style></head><body><div class="wrap"><header><div><div class="tag">OSINT · AML · Chile</div><h1>Radar Delictual</h1><p class="desc">Señales territoriales y criminales trazables para análisis de riesgo LA/FT. Histórico objetivo 2020 a la fecha, con separación estricta entre estadísticas policiales, Fiscalía y proxies analíticos.</p></div><div class="status">Último período comparable: <b>{latest or 's/d'}</b><br>Fuentes OK: {ok} · fallidas: {fail}<br>{generated}</div></header><div class="grid">{cards}</div><div class="two"><section class="panel"><h2>Presión delictual AML (proxy) · regiones · {latest or 's/d'}</h2><table><thead><tr><th>#</th><th>Región</th><th>Índice relativo</th><th>Score</th><th>Nivel</th></tr></thead><tbody>{rank_rows}</tbody></table></section><section class="panel"><h2>Serie nacional · Ministerio Público</h2><table><thead><tr><th>Año</th><th class="num">Drogas</th><th class="num">Econ./trib.</th><th class="num">Funcionarios</th><th class="num">Homicidios*</th></tr></thead><tbody>{trend_rows}</tbody></table><div class="note"><b>*No confundir:</b> esta columna corresponde a delitos ingresados en SAF. La cifra oficial de víctimas de homicidio consumado debe provenir del informe interinstitucional.</div></section></div><section class="panel" style="margin-top:14px"><h2>Señales OSINT oficiales recientes</h2><table><thead><tr><th>Fecha</th><th>Publicación</th><th>Fenómenos detectados</th></tr></thead><tbody>{event_rows}</tbody></table></section><section class="panel" style="margin-top:14px"><h2>Arquitectura de fuentes</h2><div class="sources"><span class="source">CEAD · policía · comuna/región · casos/tasas</span><span class="source">Fiscalía · SAF · delitos ingresados</span><span class="source">UCOD · crimen organizado</span><span class="source">Homicidios · informe interinstitucional</span><span class="source">Carabineros / PDI · procedimientos</span><span class="source">Aduanas · contrabando</span><span class="source">SENDA · contexto drogas</span><span class="source">Ley 19.913 · mapeo legal versionado</span></div></section><div class="note"><b>Interpretación:</b> el score prioriza territorios para análisis; no expresa probabilidad de lavado de activos, no atribuye delitos a personas o empresas y no reemplaza corroboración en la fuente original.</div><footer>Radar Delictual v0.1 · datos públicos y abiertos · evidencia, método y fecha de extracción preservados.</footer></div></body></html>'''
    output.write_text(doc, encoding="utf-8")
    return output
