# -*- coding: utf-8 -*-
"""
fetch_data.py — 定时抓取权威数据源，生成 data.json
设计原则:为人群服务，为强国奋斗。
"""
import json, datetime, sys, traceback
import requests, pandas as pd

UA = {"User-Agent": "gid-live-bot/1.0 (public health dashboard)"}
OUT = "data.json"

def get(url, timeout=20):
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r

def try_urls(urls):
    """依次尝试多个候选URL，返回第一个成功的DataFrame"""
    errs = []
    for u in urls:
        try:
            return pd.read_csv(u), u
        except Exception as e:
            errs.append(f"{u} -> {e}")
    raise RuntimeError(" | ".join(errs))

def world_row(df):
    for col in ("Entity", "Country", "location", "Location"):
        if col in df.columns:
            m = df[df[col].astype(str).str.contains("World|世界", case=False, na=False)]
            if len(m):
                return m.iloc[-1]
    return df.iloc[-1]

def num(x):
    try:
        return float(x)
    except Exception:
        return None

kpi, sources, errors = [], {}, []

# ---------- 猴痘 mpox（OWID，已开放CORS，每日更新） ----------
try:
    df, src = try_urls([
        "https://ourworldindata.org/grapher/monkeypox.csv?useColumnShortNames=true",
        "https://ourworldindata.org/grapher/monkeypox-confirmed-cases.csv?useColumnShortNames=true",
    ])
    row = world_row(df)
    cases_col = next((c for c in df.columns if "case" in c.lower()), None)
    dead_col  = next((c for c in df.columns if "death" in c.lower() or "fatal" in c.lower()), None)
    cases = num(row.get(cases_col)) if cases_col else None
    dead  = num(row.get(dead_col)) if dead_col else None
    kpi.append({"title": "猴痘（全球累计）",
                "value": f"{int(cases):,}" if cases else "—",
                "note": f"确诊累计 · 死亡 {int(dead):,}（OWID/各国上报，每日更新）" if dead else "OWID 每日更新"})
    sources["mpox"] = {"ok": True, "src": src, "cases": cases, "deaths": dead}
except Exception as e:
    errors.append("mpox: " + str(e)[:200])

# ---------- 新冠 COVID-19（OWID，每日更新） ----------
try:
    df, src = try_urls([
        "https://ourworldindata.org/grapher/covid-cases-deaths.csv?useColumnShortNames=true",
    ])
    row = world_row(df)
    ccol = next((c for c in df.columns if "case" in c.lower()), None)
    dcol = next((c for c in df.columns if "death" in c.lower()), None)
    kpi.append({"title": "新冠（全球累计）",
                "value": f"{int(num(row.get(ccol))):,}" if ccol and num(row.get(ccol)) else "—",
                "note": f"累计确诊 · 死亡 {int(num(row.get(dcol))):,}" if dcol and num(row.get(dcol)) else "OWID 每日更新"})
    sources["covid"] = {"ok": True, "src": src}
except Exception as e:
    errors.append("covid: " + str(e)[:200])

# ---------- 疟疾（WHO GHO OData，每年更新；失败时保留旧值） ----------
try:
    url = "https://ghoapi.azureedge.net/api/MALARIA_EST_DEATHS?$top=1&$format=json"
    j = get(url).json()
    val = j["value"][0].get("NumericValue") if j.get("value") else None
    if val:
        kpi.append({"title": "疟疾（全球年死亡，WHO）",
                    "value": f"{int(float(val)):,}",
                    "note": "WHO GHO 年度估计 · 病例约2.82亿（2025报告）"})
        sources["malaria"] = {"ok": True, "src": url, "deaths": float(val)}
except Exception as e:
    errors.append("malaria: " + str(e)[:200])

# ---------- 中国CDC（周报网页表格） ----------
CDC_URL = "http://weekly.chinacdc.cn/en/article/doi/10.46234/ccdcw2026.155"  # 按最新一期替换
try:
    tables = pd.read_html(CDC_URL)
    hit = None
    for t in tables:
        s = t.to_string()
        if "Influenza" in s or "流感" in s:
            hit = t
            break
    if hit is not None:
        sources["china_cdc"] = {"ok": True, "src": CDC_URL, "note": "表格已抓取"}
        kpi.append({"title": "中国法定传染病（最新月报）",
                    "value": "已同步",
                    "note": f"来源：China CDC Weekly，抓取于 {datetime.datetime.now():%Y-%m-%d}"})
except Exception as e:
    errors.append("china_cdc: " + str(e)[:200])

# ---------- 合并写入 ----------
old = {}
try:
    old = json.load(open(OUT, encoding="utf-8"))
except Exception:
    pass
data = {
    "asof": datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds"),
    "kpi": kpi if kpi else old.get("kpi", []),
    "sources": {**old.get("sources", {}), **sources},
    "errors": errors,
}
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"[OK] data.json 写入 {len(data['kpi'])} 项 KPI; 失败源 {len(errors)} 个")
for e in errors:
    print("  [WARN]", e)
sys.exit(0)
