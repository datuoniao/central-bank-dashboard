#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_excel.py — 一次性把原 Excel《货币与商品价格对照.xlsx》的历史数据迁移为看板用的 JSON。

原 Excel 结构（已逐格 + 公式解析确认）：

Sheet「资产负债表」(sheet1)：
  数据自第 4 行起。
  A=日期(Excel序列号)  B=中国货币当局总资产(亿元)  C=美国所有联储银行总资产(百万美元)
  D=欧洲央行资产总额(百万欧元)  E=日本央行资产总额(亿日元)
  G=USDCNY  H=USDJPY  I=EURUSD
  统一口径（与原表 K/L/M/N 公式一致，单位=亿美元）：
    中国 = B / USDCNY
    美国 = C / 100
    欧元 = D * EURUSD / 100
    日本 = E / USDJPY / 100000
    G4   = 四者之和

Sheet「价格整理」(sheet2)：
  数据自第 3 行起。
  A=日期  B=布伦特原油(美元/桶)  C=COMEX黄金(美元/盎司)  D=LME铜(美元/吨)

Sheet「M2」(sheet3)：
  数据自第 3 行起。
  A=日期  B=中国M2  C=美国M2  D=欧元区M2  E=日本M2
  G=USDCNY  H=USDJPY  I=EURUSD
  统一口径（与原表 K/L/M/N 公式一致，单位=亿美元）：
    中国 = B / USDCNY
    美国 = C * 10
    欧元 = D * EURUSD / 100
    日本 = E / USDJPY
    注：原表口径混合，这里保留"亿美元"以与 Excel 对齐。
"""
import json
import os
import re
import zipfile
from datetime import date, timedelta

EXCEL = r"C:/Users/Administrator/Desktop/货币与商品价格对照.xlsx"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
EPOCH = date(1899, 12, 30)


def serial_to_date(serial):
    return EPOCH + timedelta(days=int(float(serial)))


def to_ym(d):
    return d.strftime("%Y-%m")


class Sheet:
    """极简 xlsx 读取器：仅用标准库，无需第三方依赖。"""

    def __init__(self, zipf, sheet_path, shared):
        self.shared = shared
        xml = zipf.read(sheet_path).decode("utf-8")
        self.rows = {}
        for rm in re.finditer(r'<row[^>]*r="(\d+)"[^>]*>(.*?)</row>', xml, re.S):
            rn = int(rm.group(1))
            cells = {}
            for cm in re.finditer(
                r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', rm.group(2), re.S
            ):
                col, attrs, inner = cm.group(1), cm.group(3) or "", cm.group(4) or ""
                tm = re.search(r't="([^"]+)"', attrs)
                vm = re.search(r"<v>(.*?)</v>", inner, re.S)
                val = vm.group(1) if vm else None
                if val is None:
                    continue
                if tm and tm.group(1) == "s":
                    try:
                        val = shared[int(val)]
                    except (ValueError, IndexError):
                        pass
                cells[col] = val
            self.rows[rn] = cells

    def num(self, col, row):
        v = self.rows.get(row, {}).get(col)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except ValueError:
            return None


def main():
    z = zipfile.ZipFile(EXCEL)
    shared = re.findall(
        r"<t[^>]*>(.*?)</t>", z.read("xl/sharedStrings.xml").decode("utf-8"), re.S
    )
    bal = Sheet(z, "xl/worksheets/sheet1.xml", shared)
    pri = Sheet(z, "xl/worksheets/sheet2.xml", shared)
    m2s = Sheet(z, "xl/worksheets/sheet3.xml", shared)

    # ---------- 资产负债表（亿美元统一口径） ----------
    balance = []
    for rn in range(4, 400):
        d = bal.num("A", rn)
        if d is None:
            continue
        try:
            dt = serial_to_date(d)
        except (ValueError, OverflowError):
            continue
        cn, us, ea, jp = bal.num("B", rn), bal.num("C", rn), bal.num("D", rn), bal.num("E", rn)
        usdcny, usdjpy, eurusd = bal.num("G", rn), bal.num("H", rn), bal.num("I", rn)
        if all(v is None for v in (cn, us, ea, jp)):
            continue

        def usd_bn(prefix):  # 原表列前缀
            return None

        row = {
            "date": dt.strftime("%Y-%m-%d"),
            "month": to_ym(dt),
            "raw": {"cn": cn, "us": us, "ea": ea, "jp": jp},
            "fx": {"usdcny": usdcny, "usdjpy": usdjpy, "eurusd": eurusd},
        }
        # 统一折算为「亿美元」（与 Excel K/L/M/N 公式完全一致）
        row["cn_usd100m"] = (cn / usdcny) if (cn is not None and usdcny) else None
        row["us_usd100m"] = (us / 100.0) if us is not None else None
        row["ea_usd100m"] = (ea * eurusd / 100.0) if (ea is not None and eurusd) else None
        row["jp_usd100m"] = (jp / usdjpy / 100000.0) if (jp is not None and usdjpy) else None
        parts = [row[k] for k in ("cn_usd100m", "us_usd100m", "ea_usd100m", "jp_usd100m")]
        row["g4_usd100m"] = sum(p for p in parts if p is not None) if any(
            p is not None for p in parts
        ) else None
        balance.append(row)

    # ---------- 价格整理 ----------
    prices = []
    for rn in range(3, 400):
        d = pri.num("A", rn)
        if d is None:
            continue
        try:
            dt = serial_to_date(d)
        except (ValueError, OverflowError):
            continue
        row = {
            "date": dt.strftime("%Y-%m-%d"),
            "month": to_ym(dt),
            "brent": pri.num("B", rn),
            "gold": pri.num("C", rn),
            "copper": pri.num("D", rn),
        }
        if all(row[k] is None for k in ("brent", "gold", "copper")):
            continue
        prices.append(row)

    # ---------- M2 ----------
    m2 = []
    for rn in range(3, 400):
        d = m2s.num("A", rn)
        if d is None:
            continue
        try:
            dt = serial_to_date(d)
        except (ValueError, OverflowError):
            continue
        cn, us, ea, jp = m2s.num("B", rn), m2s.num("C", rn), m2s.num("D", rn), m2s.num("E", rn)
        usdcny, usdjpy, eurusd = m2s.num("G", rn), m2s.num("H", rn), m2s.num("I", rn)
        if all(v is None for v in (cn, us, ea, jp)):
            continue
        row = {
            "date": dt.strftime("%Y-%m-%d"),
            "month": to_ym(dt),
            "raw": {"cn": cn, "us": us, "ea": ea, "jp": jp},
            "fx": {"usdcny": usdcny, "usdjpy": usdjpy, "eurusd": eurusd},
        }
        # 与原表 M2 的 K/L/M/N 公式一致
        row["cn_usd100m"] = (cn / usdcny) if (cn is not None and usdcny) else None
        row["us_usd100m"] = (us * 10.0) if us is not None else None
        row["ea_usd100m"] = (ea * eurusd / 100.0) if (ea is not None and eurusd) else None
        row["jp_usd100m"] = (jp / usdjpy) if (jp is not None and usdjpy) else None
        parts = [row[k] for k in ("cn_usd100m", "us_usd100m", "ea_usd100m", "jp_usd100m")]
        row["g4_usd100m"] = sum(p for p in parts if p is not None) if any(
            p is not None for p in parts
        ) else None
        m2.append(row)

    payload = {
        "meta": {
            "source": "原 Excel《货币与商品价格对照.xlsx》迁移 (Wind 导出)",
            "unit_note": "资产负债表与 M2 均折算为「亿美元」(100 million USD)，口径与原 Excel 的 K/L/M/N 公式一致",
            "balance_range": [balance[0]["month"], balance[-1]["month"]] if balance else None,
            "prices_range": [prices[0]["month"], prices[-1]["month"]] if prices else None,
            "m2_range": [m2[0]["month"], m2[-1]["month"]] if m2 else None,
        },
        "balance": balance,
        "prices": prices,
        "m2": m2,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.abspath(os.path.join(OUT_DIR, "excel_history.json"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("资产负债表:", len(balance), "行", payload["meta"]["balance_range"])
    print("价格:", len(prices), "行", payload["meta"]["prices_range"])
    print("M2:", len(m2), "行", payload["meta"]["m2_range"])
    print("写出:", out)


if __name__ == "__main__":
    main()
