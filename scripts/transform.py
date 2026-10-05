#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transform.py — 把各源抓到的原始数据「合并 / 归一 / 派生」，产出前端直接消费的 dashboard.json。

输入（均在 data/ 下）：
  excel_history.json   由 migrate_excel.py 生成的历史底座（2003 起）
  raw_latest.json      由 fetch_all.py 抓取的最新数据（public 源）
  raw_ifind.json       （可选）本地 iFinD 兜底数据

输出：
  data/dashboard.json  统一结构，含：
    meta        —— 生成时间、数据截止月、单位说明、来源清单
    balance     —— 四央行总资产（亿美元）+ G4 合计，含 yoy/mom
    m2          —— 四经济体 M2（亿美元），含 yoy/mom
    prices      —— Brent / Gold / Copper，含 yoy/mom
    fx          —— USDCNY / USDJPY / EURUSD
    correlations—— 关键相关性（如 G4 同比 vs 金价同比）

单位口径（与原 Excel 完全一致，单位 = 亿美元 / 100 million USD）：
  中国总资产  亿元        / USDCNY                = 亿美元   (原 K = B/G)
  美国总资产  million USD / 100                   = 亿美元   (原 L = C/100)
  欧元区总资产 million EUR * EURUSD / 100          = 亿美元   (原 M = D*I/100)
  日本总资产  亿日元       / USDJPY / 100          = 亿美元   (原 N = E/H/100000)
  ——注意日本：亿日元 / (日元每美元) = 亿美元；再除以 100 变… 原表 N=E/H/100000
    E 单位是「亿日元」，E/H = 亿美元，/100000 得到… 见下方 _jp_note 的实测校验。

M2 口径（原 M2 sheet K/L/M/N）：
  中国 M2 亿元 / USDCNY        = 亿美元  (K = B/G)
  美国 M2 (billion USD) * 10   = 亿美元  (L = C*10)  ← 原表 US M2 单位是 十亿美元
  欧元区 M2 million EUR * EURUSD / 100 = 亿美元 (M = D*I/100)
  日本 M2 亿日元 / USDJPY      = 亿美元  (N = E/H)
"""
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "data"))

GROUPS = ["cn", "us", "ea", "jp"]
GROUP_NAMES = {"cn": "中国", "us": "美国", "ea": "欧元区", "jp": "日本"}


# --------------------------------------------------------------- 工具函数
def month_add(ym, n):
    """'2026-08' + n 个月 -> 'YYYY-MM'"""
    y, m = int(ym[:4]), int(ym[5:7])
    t = (y * 12 + (m - 1)) + n
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def yoy(series, ym):
    prev = series.get(month_add(ym, -12))
    cur = series.get(ym)
    if prev in (None, 0) or cur is None:
        return None
    return round((cur / prev - 1.0) * 100.0, 2)


def mom(series, ym):
    prev = series.get(month_add(ym, -1))
    cur = series.get(ym)
    if prev in (None, 0) or cur is None:
        return None
    return round((cur / prev - 1.0) * 100.0, 2)


def diff_pct(series, ym, n):
    """相比 n 个月前的百分比变化（用于 3M 等）"""
    prev = series.get(month_add(ym, -n))
    cur = series.get(ym)
    if prev in (None, 0) or cur is None:
        return None
    return round((cur / prev - 1.0) * 100.0, 2)


# --------------------------------------------------------------- 组装合并
def build_prices(hist_prices, wb_prices):
    """合并价格：Excel 历史为底，World Bank 覆盖（黄金/铜/布伦特）。"""
    brent, gold, copper = {}, {}, {}
    for r in hist_prices:
        m = r["month"]
        if r.get("brent") is not None:
            brent[m] = r["brent"]
        if r.get("gold") is not None:
            gold[m] = r["gold"]
        if r.get("copper") is not None:
            copper[m] = r["copper"]
    # 外部源覆盖（更权威/更新）
    for k, dst in (("brent", brent), ("gold", gold), ("copper", copper)):
        for m, v in (wb_prices.get(k) or {}).items():
            if v is not None:
                dst[m] = v
    return {"brent": brent, "gold": gold, "copper": copper}


def build_balance(hist_balance, raw):
    """
    hist_balance: excel_history.balance 列表
    raw: {'cn': {...}, 'us': {...}, 'ea': {...}, 'jp': {...}, 'fx': {...}}
    返回统一后的 { 'cn': {ym: 亿美元}, ... , 'g4': {...} }
    """
    out = {g: {} for g in GROUPS}
    fx = {k: dict(v) for k, v in (raw.get("fx") or {}).items()}
    fx.setdefault("usdcny", {})
    fx.setdefault("usdjpy", {})
    fx.setdefault("eurusd", {})

    # 1) 历史底座直接取已归一的值 + 汇率
    for r in hist_balance:
        m = r["month"]
        f = r.get("fx") or {}
        for k, mk in (("usdcny", "usdcny"), ("usdjpy", "usdjpy"), ("eurusd", "eurusd")):
            if f.get(k) is not None and m not in fx[mk]:
                fx[mk][m] = f[k]
        for g, key in (("cn", "cn_usd100m"), ("us", "us_usd100m"),
                       ("ea", "ea_usd100m"), ("jp", "jp_usd100m")):
            v = r.get(key)
            if v is not None:
                out[g][m] = v

    # 2) 外部最新原始值（本地单位）→ 归一覆盖
    for g in GROUPS:
        src = raw.get(g) or {}
        levels = src.get("levels") or {}   # {ym: 本币原值}
        for m, v in levels.items():
            if v is None:
                continue
            conv = normalize_balance(g, v, m, fx)
            if conv is not None:
                out[g][m] = conv

    # 3) 外部汇率覆盖
    for mk in ("usdcny", "usdjpy", "eurusd"):
        for m, v in (raw.get("fx", {}).get(mk) or {}).items():
            if v:
                fx[mk][m] = v

    return out, fx


def normalize_balance(g, value, ym, fx):
    """
    把某国本币总资产折成亿美元（口径同原 Excel balance sheet 的 K/L/M/N）。
    要求传入的 value 单位：
      cn = 亿元人民币      us = 百万美元(million USD)
      ea = 百万欧元(million EUR)   jp = 日元(yen, 全部单位)
    """
    if g == "cn":
        r = fx["usdcny"].get(ym)
        return value / r if r else None            # 亿元 / (CNY/USD)
    if g == "us":
        return value / 100.0                        # million USD / 100
    if g == "ea":
        e = fx["eurusd"].get(ym)
        return value * e / 100.0 if e else None     # million EUR * (USD/EUR) / 100
    if g == "jp":
        r = fx["usdjpy"].get(ym)
        # 日元 / (JPY/USD) = 美元；再 /1e8 = 亿美元  → 等价于 日元/JPY/USD/1e8
        return value / r / 1e8 if r else None
    return None


def build_m2(hist_m2, raw):
    out = {g: {} for g in GROUPS}
    for r in hist_m2:
        m = r["month"]
        for g, key in (("cn", "cn_usd100m"), ("us", "us_usd100m"),
                       ("ea", "ea_usd100m"), ("jp", "jp_usd100m")):
            v = r.get(key)
            if v is not None:
                out[g][m] = v
    for g in GROUPS:
        src = (raw.get("m2") or {}).get(g) or {}
        levels = src.get("levels") or {}
        for m, v in levels.items():
            if v is None:
                continue
            conv = normalize_m2(g, v, m, raw.get("fx") or {})
            if conv is not None:
                out[g][m] = conv
    return out


def normalize_m2(g, value, ym, fx):
    """
    把某经济体 M2 本币值折成亿美元（口径同原 M2 sheet K/L/M/N）。
    要求传入的 value 单位：
      cn = 亿元人民币   us = 十亿美元(billion USD)
      ea = 百万欧元     jp = 亿日元
    """
    if g == "cn":
        r = (fx.get("usdcny") or {}).get(ym)
        return value / r if r else None            # 亿元 / (CNY/USD)
    if g == "us":
        return value * 10.0                         # billion USD * 10 = 亿美元
    if g == "ea":
        e = (fx.get("eurusd") or {}).get(ym)
        return value * e / 100.0 if e else None     # million EUR * EURUSD / 100
    if g == "jp":
        r = (fx.get("usdjpy") or {}).get(ym)
        return value / r if r else None             # 亿日元 / (JPY/USD) = 亿美元
    return None


# --------------------------------------------------------------- 派生 + 输出
def series_block(levels):
    """把 {ym: 值} 变成带 yoy/mom/3m 的排序列表。"""
    months = sorted(levels)
    rows = []
    for m in months:
        rows.append({
            "m": m,
            "v": round(levels[m], 2) if levels[m] is not None else None,
            "yoy": yoy(levels, m),
            "mom": mom(levels, m),
            "c3m": diff_pct(levels, m, 3),
        })
    return rows


def correlation(a_levels, b_levels, use_yoy=True, min_n=24):
    """
    计算 a/b 两条序列的同比（默认）皮尔逊相关系数。
    只取两者都有值的月份。
    """
    keys = sorted(set(a_levels) & set(b_levels))
    xs, ys = [], []
    for m in keys:
        if use_yoy:
            xa, xb = yoy(a_levels, m), yoy(b_levels, m)
        else:
            xa, xb = a_levels.get(m), b_levels.get(m)
        if xa is None or xb is None:
            continue
        xs.append(xa)
        ys.append(xb)
    n = len(xs)
    if n < min_n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return {"r": round(cov / (vx ** 0.5 * vy ** 0.5), 3), "n": n}


def main():
    hist = json.load(open(os.path.join(DATA, "excel_history.json"), encoding="utf-8"))
    raw = {}
    rp = os.path.join(DATA, "raw_latest.json")
    if os.path.exists(rp):
        raw = json.load(open(rp, encoding="utf-8"))
    ip = os.path.join(DATA, "raw_ifind.json")
    if os.path.exists(ip):
        try:
            iraw = json.load(open(ip, encoding="utf-8"))
            # iFinD 兜底：合并到 raw（仅补空缺）
            for sec in ("cn", "us", "ea", "jp"):
                if sec in iraw:
                    tgt = raw.setdefault(sec, {}).setdefault("levels", {})
                    for m, v in (iraw[sec] or {}).items():
                        tgt.setdefault(m, v)
            for mk in ("usdcny", "usdjpy", "eurusd"):
                if mk in iraw:
                    tgt = raw.setdefault("fx", {}).setdefault(mk, {})
                    for m, v in (iraw[mk] or {}).items():
                        tgt.setdefault(m, v)
        except Exception as e:  # noqa: BLE001
            print("iFinD 兜底读取失败:", e)

    wb_prices = raw.get("prices") or {}
    prices = build_prices(hist["prices"], wb_prices)
    balance, fx = build_balance(hist["balance"], raw)
    m2 = build_m2(hist["m2"], raw)

    # G4 合计（仅在有全部四国时计算；否则给出现有之和并标注）
    for ym_set in (balance["cn"], balance["us"], balance["ea"], balance["jp"]):
        pass
    all_m = set(balance["cn"]) | set(balance["us"]) | set(balance["ea"]) | set(balance["jp"])
    g4 = {}
    for m in all_m:
        vals = [balance[g].get(m) for g in GROUPS]
        if all(v is not None for v in vals):
            g4[m] = sum(vals)
    balance["g4"] = g4

    # 价格合并（prices 已直接可序列化；补上 yoy）
    price_blocks = {k: series_block(v) for k, v in prices.items()}

    # ------------- 统一时间窗 -------------
    # 各源历史长度不一（US M2 自 1959、WB 价格自 1960），为让图表可比，
    # 输出时统一裁剪到「共同可用窗口」，同时把裁剪前的完整窗口写入 meta.range。
    def _full_span(blocks):
        ms = [r["m"] for blk in blocks.values() for r in blk]
        return (min(ms), max(ms)) if ms else (None, None)

    balance_span = _full_span({g: series_block(balance[g]) for g in GROUPS + ["g4"]})
    m2_span = _full_span({g: series_block(m2[g]) for g in GROUPS})
    price_span = _full_span(price_blocks)

    # 默认展示窗口：以四国 M2 的共同起点为准（2005-01），价格同样裁到该窗口
    default_start = "2005-01"

    def _clip(blocks, start):
        out = {}
        for k, blk in blocks.items():
            out[k] = [r for r in blk if r["m"] >= start]
        return out

    balance_blocks = _clip({g: series_block(balance[g]) for g in GROUPS + ["g4"]}, default_start)
    m2_blocks = _clip({g: series_block(m2[g]) for g in GROUPS}, default_start)
    price_blocks = _clip(price_blocks, default_start)

    # 相关性一律基于裁剪后的共同窗口，避免上游超长历史（如 1960 起的价格）稀释系数
    bal_c = {g: {r["m"]: r["v"] for r in balance_blocks[g]} for g in GROUPS + ["g4"]}
    pri_c = {k: {r["m"]: r["v"] for r in price_blocks[k]} for k in price_blocks}
    m2_c = {g: {r["m"]: r["v"] for r in m2_blocks[g]} for g in GROUPS}

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "unit": "亿美元 (100 million USD)",
            "unit_note": "口径与原 Excel 一致：中/日按当月汇率折美元；美国 /100；欧元区 ×EURUSD/100",
            "default_start": default_start,
            "range": {
                "balance_full": list(balance_span),
                "m2_full": list(m2_span),
                "price_full": list(price_span),
            },
            "latest_balance": max(g4) if g4 else None,
            "latest_m2": max(set().union(*[set(m2[g]) for g in GROUPS])) if any(m2[g] for g in GROUPS) else None,
            "latest_price": max(set().union(*[set(prices[k]) for k in prices])) if any(prices.values()) else None,
            "sources": [
                "PBOC 中国人民银行（货币当局资产负债表 / 货币供应量）",
                "FRED（美国 Fed 总资产 WALCL、M2SL、欧洲央行 ECBASSETSW、日本银行 JPNASSETS、汇率 DEXCHUS/DEXJPUS/DEXUSEU）",
                "World Bank Pink Sheet（Brent 原油 / 黄金 / 铜）",
            ],
        },
        "balance": balance_blocks,
        "m2": m2_blocks,
        "prices": price_blocks,
        "fx": _clip({k: series_block(v) for k, v in fx.items()}, default_start),
        "correlations": {
            "g4_yoy_vs_gold_yoy": correlation(bal_c["g4"], pri_c["gold"]),
            "g4_yoy_vs_copper_yoy": correlation(bal_c["g4"], pri_c["copper"]),
            "g4_yoy_vs_brent_yoy": correlation(bal_c["g4"], pri_c["brent"]),
            "us_yoy_vs_gold_yoy": correlation(bal_c["us"], pri_c["gold"]),
            "cn_yoy_vs_copper_yoy": correlation(bal_c["cn"], pri_c["copper"]),
            "m2_g4_yoy_vs_gold_yoy": correlation(
                {m: (m2_c["cn"].get(m, 0) + m2_c["us"].get(m, 0) +
                     m2_c["ea"].get(m, 0) + m2_c["jp"].get(m, 0))
                 for m in (set(m2_c["cn"]) & set(m2_c["us"]) & set(m2_c["ea"]) & set(m2_c["jp"]))},
                pri_c["gold"]),
        },
    }

    op = os.path.join(DATA, "dashboard.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    # 控制台摘要
    mb = len(payload["balance"]["g4"])
    print(f"[transform] window: {default_start} -> {payload['meta']['latest_balance']} "
          f"(full: balance{balance_span} m2{m2_span} price{price_span})")
    print(f"[transform] balance g4 {mb} months -> {payload['meta']['latest_balance']}")
    print(f"[transform] m2 cn {len(payload['m2']['cn'])} / us {len(payload['m2']['us'])} "
          f"/ ea {len(payload['m2']['ea'])} / jp {len(payload['m2']['jp'])}")
    print(f"[transform] prices brent {len(prices['brent'])} gold {len(prices['gold'])} copper {len(prices['copper'])}")
    print(f"[transform] corr g4~gold {payload['correlations']['g4_yoy_vs_gold_yoy']}")
    print(f"[transform] corr g4~copper {payload['correlations']['g4_yoy_vs_copper_yoy']}")
    print(f"[transform] written {op} ({os.path.getsize(op)} bytes)")


if __name__ == "__main__":
    main()
