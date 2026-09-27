#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每月更新 data.json：
1. 从国家卫健委网站获取最新一期《全国法定传染病疫情概况》
2. 解析总发病数、总死亡数
3. 写入对应年份的 months 数组，并累计年度 infections / deaths
"""
import json, re, sys, urllib.request
from datetime import date
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "data.json"

# 国家卫健委疫情通报栏目（列表页）。若栏目调整，修改此处即可。
LIST_URL = "https://www.nhc.gov.cn/wjw/yqb/list_gzbd.shtml"

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="ignore")

def parse_report(html: str):
    """从通报正文提取 发病数 / 死亡数。通报典型表述：
    '报告发病XXXXXX例，死亡XXXX人'"""
    m = re.search(r"报告发病\s*([\d,，]+)\s*例", html)
    d = re.search(r"死亡\s*([\d,，]+)\s*人", html)
    if not m:
        return None, None
    num = lambda s: int(s.replace(",", "").replace("，", ""))
    return num(m.group(1)), num(d.group(1)) if d else 0

def main():
    today = date.today()
    # 卫健委一般在次月中旬公布上月数据
    year, month = (today.year, today.month - 1) or (today.year - 1, 12)
    ym = f"{year}-{month:02d}"

    try:
        list_html = fetch(LIST_URL)
        # 在列表页找到最新一期疫情概况的详情链接
        link = re.search(r'href="([^"]+)"[^>]*>[^<]*法定传染病疫情概况', list_html)
        if not link:
            print("未找到最新通报链接，跳过本次更新（网页结构可能已变化）")
            return
        url = link.group(1)
        if url.startswith("/"):
            url = "https://www.nhc.gov.cn" + url
        html = fetch(url)
        infections, deaths = parse_report(html)
    except Exception as e:
        print(f"抓取失败: {e}（不阻塞，下次重试）")
        sys.exit(0)

    if infections is None:
        print("未能从通报中解析出发病数，跳过")
        return

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    rec = next((y for y in data["years"] if y["year"] == year), None)
    if rec is None:
        rec = {"year": year, "infections": 0, "deaths": 0,
               "diseases": ["法定传染病（甲乙丙类合计）"], "hotspots": [],
               "months": [], "source": "国家卫健委月度通报", "example": False}
        data["years"].append(rec)
        data["years"].sort(key=lambda x: x["year"])

    # 幂等：同月不重复写入
    if not any(m["month"] == ym for m in rec["months"]):
        rec["months"].append({"month": ym, "infections": infections, "deaths": deaths})
        rec["months"].sort(key=lambda m: m["month"])
        rec["infections"] = sum(m["infections"] for m in rec["months"])
        rec["deaths"] = sum(m["deaths"] for m in rec["months"])
        data["updatedAt"] = today.isoformat()
        DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {ym}: 发病 {infections}, 死亡 {deaths}")
    else:
        print(f"{ym} 数据已存在，跳过")

if __name__ == "__main__":
    main()
