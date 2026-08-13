from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import PUBLIC_DIR


def _esc(x): return html.escape(str(x if x is not None else ""))
def _fmt(n): return f"{int(n):,}".replace(",",".") if n is not None else "—"


def build_dashboard(metrics:list[dict],risks:list[dict],source_status:list[dict],output:Path|None=None,events:list[dict]|None=None,region_priority:list[dict]|None=None,commune_priority:list[dict]|None=None,legal:dict|None=None,cead_catalog:dict|None=None,publications:list[dict]|None=None,integration:list[dict]|None=None,homicide_context:dict|None=None,cead_metrics:list[dict]|None=None,cead_manifest:dict|None=None,current_activity:list[dict]|None=None,predicate_features:list[dict]|None=None)->Path:
    output=output or PUBLIC_DIR/"index.html"; events=events or []; region_priority=region_priority or []; commune_priority=commune_priority or []; cead_catalog=cead_catalog or {}; integration=integration or []; homicide_context=homicide_context or {}; cead_metrics=cead_metrics or []; cead_manifest=cead_manifest or {}; current_activity=current_activity or []; predicate_features=predicate_features or []
    probe=cead_manifest.get("primary_probe",{}); bridge=cead_manifest.get("bridge_snapshot",{}); cov=cead_manifest.get("coverage",{})
    primary="Disponible" if probe.get("ok") else f"Bloqueado {probe.get('http_status','')}".strip()
    backbone=cead_manifest.get("active_backbone","sin dato")
    cards=[
        ("CEAD primario",primary,"POST oficial sondeado en cada corrida"),
        ("Backbone activo",backbone,"precedencia: directo → réplica → control BCN"),
        ("Cobertura comunal",_fmt(cov.get("communes")),f"años {', '.join(map(str,cov.get('years',[])))}"),
        ("Frescura CEAD",bridge.get("max_date") or probe.get("latest_nonzero_period") or "—",f"{_fmt(cov.get('records'))} registros anuales normalizados")
    ]
    card_html="".join(f'<div class="card"><div class="kicker">{_esc(a)}</div><div class="value">{_esc(b)}</div><div class="sub">{_esc(c)}</div></div>' for a,b,c in cards)

    activity_rows="".join(
        f'<tr><td>{i}</td><td>{_esc(r.get("commune_name"))}</td><td>{_esc(r.get("region_name"))}</td><td class="num strong">{_fmt(r.get("cases_policiales"))}</td><td class="num">{_fmt(r.get("previous_cases_policiales"))}</td><td class="num">{"—" if r.get("yoy_pct") is None else f"{r["yoy_pct"]:+.1f}%"}</td><td>{_esc(r.get("source_tier"))}</td></tr>'
        for i,r in enumerate(current_activity[:35],1)
    ) or '<tr><td colspan="7">Sin actividad CEAD utilizable.</td></tr>'

    region_rows="".join(f'<tr><td>{i}</td><td>{_esc(r.get("region_name"))}</td><td class="num strong">{r.get("pressure_score",0):.1f}</td><td>{_esc(r.get("pressure_level"))}</td></tr>' for i,r in enumerate(region_priority,1)) or '<tr><td colspan="4">Sin datos.</td></tr>'

    mapping_rows=""
    for key,m in (cead_catalog.get("aml_mapping") or {}).items():
        if key=="default": continue
        mapping_rows+=f'<tr><td>{_esc(key)}</td><td>{_esc(m.get("class"))}</td><td>{"Sí" if m.get("score_eligible") else "No"}</td><td class="num">{float(m.get("weight",0)):.1f}</td><td>{_esc(m.get("basis"))}</td></tr>'

    route_rows=[
        ("1 · CEAD directo", "OK" if probe.get("ok") else "BLOQUEADO", probe.get("endpoint"), f"HTTP {probe.get('http_status','—')} · {probe.get('blocking_message') or 'respuesta válida'}"),
        ("2 · Réplica de extracción directa", "OK" if bridge.get("ok") else "FALLA", bridge.get("repo"), f"máx. {bridge.get('max_date','—')} · blob {str(bridge.get('upstream_blob_sha') or '')[:12]} · SHA256 {str(bridge.get('content_sha256') or '')[:12]}"),
        ("3 · BCN/SIIT control", "CONTROL", "BCN/SIIT → SPD/CEAD", f"{_fmt(cov.get('bcn_control_records'))} registros de control secundario"),
        ("4 · Cuarentena", "NO SCORE", "reglas de calidad", "duplicados, cobertura insuficiente o esquema inesperado no ingresan al maestro")
    ]
    routes_html="".join(f'<tr><td>{_esc(a)}</td><td><span class="pill">{_esc(b)}</span></td><td>{_esc(c)}</td><td>{_esc(d)}</td></tr>' for a,b,c,d in route_rows)

    health_rows="".join(f'<tr><td>{_esc(s.get("source_id",""))}</td><td><span class="health {"ok" if s.get("ok") else "bad"}">{"OK" if s.get("ok") else "FALLA"}</span></td><td>{_esc(s.get("note") or s.get("blocking_message") or s.get("error","")[:140])}</td></tr>' for s in source_status[-22:] if isinstance(s,dict))
    generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    payload={"version":"0.4.0","cead_update_manifest":cead_manifest,"cead_current_predicate_activity":current_activity,"cead_predicate_features":predicate_features,"region_mp_proxy":region_priority,"cead_catalog_art27":cead_catalog,"homicide_context":homicide_context,"source_status":source_status,"integration":integration}
    (PUBLIC_DIR/"data.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")

    doc=f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Radar Delictual v0.4</title><style>
:root{{--bg:#0d1015;--panel:#171b22;--line:#2a313b;--text:#f4f5f7;--muted:#9da6b1;--accent:#f28c28;--accent2:#ffb361;--good:#58c68b;--bad:#ef6b66}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Inter,system-ui,-apple-system,Segoe UI,sans-serif}}.wrap{{max-width:1500px;margin:auto;padding:26px}}header{{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-bottom:18px}}h1{{margin:0;font-size:32px;letter-spacing:-.8px}}h2{{font-size:16px;margin:0 0 12px}}.tag{{color:var(--accent);font-weight:850;text-transform:uppercase;letter-spacing:.13em;font-size:11px}}.desc{{color:var(--muted);max-width:930px;margin:6px 0 0}}.status{{text-align:right;color:var(--muted);font-size:12px}}.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.two{{display:grid;grid-template-columns:1.15fr .85fr;gap:14px;margin-top:14px}}.card,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:15px}}.card{{padding:17px}}.panel{{padding:17px;overflow:auto}}.kicker{{color:var(--muted);font-size:11px;text-transform:uppercase;min-height:28px}}.value{{font-size:25px;font-weight:850;overflow-wrap:anywhere}}.sub{{color:var(--muted);font-size:11px}}table{{width:100%;border-collapse:collapse;white-space:nowrap}}th,td{{padding:8px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--muted);font-size:10px;text-transform:uppercase}}.num{{text-align:right;font-variant-numeric:tabular-nums}}.strong{{font-weight:800;color:var(--accent2)}}.pill{{font-size:10px;padding:4px 7px;border-radius:20px;border:1px solid var(--line)}}.note{{margin-top:14px;padding:13px 15px;border-left:3px solid var(--accent);background:#14181e;color:#c8cdd3;border-radius:8px}}.health{{font-size:10px;font-weight:800}}.health.ok{{color:var(--good)}}.health.bad{{color:var(--bad)}}footer{{color:var(--muted);font-size:11px;margin-top:18px}}@media(max-width:980px){{.grid4{{grid-template-columns:1fr 1fr}}.two{{grid-template-columns:1fr}}header{{display:block}}.status{{text-align:left;margin-top:9px}}}}@media(max-width:560px){{.grid4{{grid-template-columns:1fr}}.wrap{{padding:14px}}}}
</style></head><body><div class="wrap"><header><div><div class="tag">OSINT · AML · CEAD · v0.4</div><h1>Radar Delictual</h1><p class="desc">La v0.4 convierte CEAD en un backbone actualizable: sonda el endpoint primario, valida una réplica de extracción directa como puente cuando el servidor bloquea GitHub Actions y mantiene BCN/SIIT únicamente como control secundario. Cada registro conserva procedencia y prioridad de fuente.</p></div><div class="status">Homicidios en core AML: <b>0</b><br>Features art. 27: <b>{_fmt(len(predicate_features))}</b><br>Actualizado {generated}</div></header>
<div class="grid4">{card_html}</div>
<section class="panel" style="margin-top:14px"><h2>Ruta de adquisición CEAD</h2><table><thead><tr><th>Prioridad</th><th>Estado</th><th>Origen</th><th>Control</th></tr></thead><tbody>{routes_html}</tbody></table><div class="note"><b>Regla de precedencia:</b> un registro obtenido directamente del POST CEAD desplaza a la réplica para la misma comuna, año y categoría. La réplica desplaza al control secundario BCN. Los datos en cuarentena nunca alimentan el maestro ni el scoring.</div></section>
<section class="panel" style="margin-top:14px"><h2>Actividad comunal CEAD reciente · familia de drogas vinculada al artículo 27</h2><table><thead><tr><th>#</th><th>Comuna</th><th>Región</th><th>Casos {_esc(current_activity[0]['year'] if current_activity else '')}</th><th>Año previo</th><th>Var.</th><th>Fuente</th></tr></thead><tbody>{activity_rows}</tbody></table><div class="note">Unidad: <b>casos policiales</b>. Este ranking es volumen observado y no se presenta como riesgo LA/FT ni tasa poblacional. Su utilidad es dejar una feature territorial trazable para cruces posteriores.</div></section>
<div class="two"><section class="panel"><h2>Homologación CEAD ↔ artículo 27</h2><table><thead><tr><th>Nivel</th><th>Clase</th><th>Pondera</th><th>Peso</th><th>Fundamento</th></tr></thead><tbody>{mapping_rows}</tbody></table></section><section class="panel"><h2>Proxy regional Fiscalía · sin homicidios</h2><table><thead><tr><th>#</th><th>Región</th><th>Score</th><th>Nivel</th></tr></thead><tbody>{region_rows}</tbody></table><div class="note">Capa separada: delitos ingresados a SAF. Homicidios no participan de los componentes AML.</div></section></div>
<section class="panel" style="margin-top:14px"><h2>Salud y trazabilidad de fuentes</h2><table><thead><tr><th>Fuente</th><th>Estado</th><th>Detalle</th></tr></thead><tbody>{health_rows}</tbody></table></section>
<div class="note"><b>Interpretación:</b> la presencia territorial de un delito base no acredita lavado de activos ni vincula a residentes, empresas o sectores. La v0.4 prioriza adquisición, calidad, trazabilidad y actualización futura antes que ampliar scores.</div><footer>Radar Delictual v0.4 · CEAD primary-first · mirror bridge verificado · control BCN/SIIT · homicidios fuera del core AML.</footer></div></body></html>'''
    output.write_text(doc,encoding="utf-8"); return output
