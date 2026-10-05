#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_all.py — 抓取全部公开数据源（免 Key），产出 data/raw_latest.json。

数据源与序列：
  美国（FRED）：
    WALCL      Fed 总资产（百万美元，周频 → 取月末）
    M2SL       美国 M2（十亿美元，月频）
    DEXCHUS    人民币/美元（日频 → 月均）
    DEXJPUS    日元/美元（日频 → 月均）
    DEXUSEU    美元/欧元（日频 → 月均，需取倒数得 EURUSD）
  欧元区（ECB Data Portal）：
    M2 存量（百万欧元，月频）
  中国（PBOC 官网）：
    货币当局资产负债表 总资产（亿元） / 货币供应量 M2（亿元）
  商品（World Bank Pink Sheet）：
    Brent 原油 / Gold / Copper（月频）

输出 raw_latest.json 结构：
{
  "fetched_at": "...",
  "cn": {"levels": {"2026-08": 498567.28}},     # 亿元
  "us": {"levels": {...}},                       # 百万美元
  "ea": {"levels": {...}},                       # 百万欧元
  "jp": {"levels": {...}},                       # 日元（FRED JPNASSETS 为亿日元，需 ×1e8）
  "m2": {"cn": {...}, "us": {...}, "ea": {...}, "jp": {...}},
  "fx": {"usdcny": {...}, "usdjpy": {...}, "eurusd": {...}},
  "prices": {"brent": {...}, "gold": {...}, "copper": {...}}
}
"""
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

from sources import fred, ecb_sdw, worldbank, pboc  # noqa: E402

# BOJ 总资产：FRED 无月频长序列（JPNASSETS 为 2016+ 且单位亿日元），
# 故日本资产负债表历史来自 Excel 底座，这里只在可用时补最新。
JP_SERIES = "JPNASSETS"   # 亿日元，月频，2016-01 起


def log(msg):
    print(f"  [fetch] {msg}")


def main():
    out = {"fetched_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    errors = []

    # ---------- 汇率（FRED）----------
    fx = out.setdefault("fx", {})
    try:
        usdcny = fred.monthly_avg(fred.fetch_series("DEXCHUS"))
        fx["usdcny"] = {m: round(v, 6) for m, v in usdcny.items()}
        log(f"USDCNY {len(usdcny)} months, last={max(usdcny)} {usdcny[max(usdcny)]:.4f}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"DEXCHUS: {e}")

    try:
        usdjpy = fred.monthly_avg(fred.fetch_series("DEXJPUS"))
        fx["usdjpy"] = {m: round(v, 6) for m, v in usdjpy.items()}
        log(f"USDJPY {len(usdjpy)} months, last={max(usdjpy)} {usdjpy[max(usdjpy)]:.4f}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"DEXJPUS: {e}")

    try:
        # DEXUSEU = 美元/欧元 (USD per EUR)，即 EURUSD 直接值
        eurusd = fred.monthly_avg(fred.fetch_series("DEXUSEU"))
        fx["eurusd"] = {m: round(v, 6) for m, v in eurusd.items()}
        log(f"EURUSD {len(eurusd)} months, last={max(eurusd)} {eurusd[max(eurusd)]:.4f}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"DEXUSEU: {e}")

    # ---------- 美国 ----------
    out["us"] = {"levels": {}}
    try:
        walcl = fred.to_month_end(fred.fetch_series("WALCL"))  # 百万美元
        out["us"]["levels"] = {m: round(v, 3) for m, v in walcl.items()}
        log(f"US WALCL {len(walcl)} months, last={max(walcl)} {walcl[max(walcl)]:.0f}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"WALCL: {e}")

    out.setdefault("m2", {})
    out["m2"]["us"] = {"levels": {}}
    try:
        m2sl = fred.to_month_end(fred.fetch_series("M2SL"))   # 十亿美元
        out["m2"]["us"]["levels"] = {m: round(v, 2) for m, v in m2sl.items()}
        log(f"US M2SL {len(m2sl)} months, last={max(m2sl)} {m2sl[max(m2sl)]:.1f}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"M2SL: {e}")

    # ---------- 欧元区 M2（ECB）----------
    out["m2"]["ea"] = {"levels": {}}
    try:
        # ECB: 欧元区 M2 存量，BSI 数据流
        ea_m2 = ecb_sdw.to_month_end(
            ecb_sdw.fetch_dataflow("BSI", "M.U2.Y.V.M20.X.1.U2.2300.Z01.E")
        )
        out["m2"]["ea"]["levels"] = {m: round(v, 2) for m, v in ea_m2.items()}
        log(f"EA M2 {len(ea_m2)} months, last={max(ea_m2)} {ea_m2[max(ea_m2)]:.0f}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"EA M2: {e}")

    # 欧元区央行资产：FRED ECBASSETSW（百万欧元，周末值 → 取月末），
    # 实测与 Excel 的欧元区列完全一致（2026-08 = 5915343）。
    out["ea"] = {"levels": {}}
    try:
        ea_assets = fred.to_month_end(fred.fetch_series("ECBASSETSW"))
        out["ea"]["levels"] = {m: round(v, 2) for m, v in ea_assets.items()}
        log(f"EA assets {len(ea_assets)} months, last={max(ea_assets)} {ea_assets[max(ea_assets)]:.0f}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"ECBASSETSW: {e}")

    # ---------- 中国（PBOC）----------
    out["cn"] = {"levels": {}}
    out["m2"]["cn"] = {"levels": {}}
    try:
        cn_bal = pboc.fetch_balance()
        out["cn"]["levels"] = {m: round(v, 2) for m, v in cn_bal.items()}
        log(f"CN balance {len(cn_bal)} months, last={max(cn_bal)} {cn_bal[max(cn_bal)]:.2f}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"PBOC balance: {e}")
    try:
        cn_m2 = pboc.fetch_m2()
        out["m2"]["cn"]["levels"] = {m: round(v, 2) for m, v in cn_m2.items()}
        log(f"CN M2 {len(cn_m2)} months, last={max(cn_m2)} {cn_m2[max(cn_m2)]:.2f}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"PBOC M2: {e}")

    # ---------- 日本 ----------
    out["jp"] = {"levels": {}}
    out["m2"]["jp"] = {"levels": {}}
    try:
        jp_assets = fred.to_month_end(fred.fetch_series(JP_SERIES))  # 亿日元
        # normalize_balance 期望「日元」→ ×1e8
        out["jp"]["levels"] = {m: round(v * 1e8, 0) for m, v in jp_assets.items()}
        log(f"JP assets {len(jp_assets)} months, last={max(jp_assets)} {jp_assets[max(jp_assets)]:.0f} 亿日元")
    except Exception as e:  # noqa: BLE001
        log(f"JP assets 跳过（沿用历史底座）: {type(e).__name__}")
    # 日本 M2：Excel 底座已有；FRED 无干净月频长序列，保持留空由底座覆盖
    out["m2"]["jp"]["levels"] = {}

    # ---------- 商品价格（World Bank）----------
    out["prices"] = {}
    try:
        ps = worldbank.fetch_pink_sheet()
        out["prices"] = ps
        log(f"prices gold={len(ps['gold'])} copper={len(ps['copper'])} brent={len(ps['brent'])}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"WorldBank: {e}")

    # ---------- 落盘 ----------
    os.makedirs(DATA, exist_ok=True)
    op = os.path.join(DATA, "raw_latest.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log(f"written {op} ({os.path.getsize(op)} bytes)")
    if errors:
        log("部分源失败：" + "; ".join(errors))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
