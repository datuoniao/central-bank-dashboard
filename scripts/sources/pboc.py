#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pboc.py — 抓取中国人民银行「货币当局资产负债表」总资产 与「金融统计数据报告」M2。

数据源（均免 Key，实测可达）：
  资产负债表（列=月份矩阵，一次下载得整年）：
    入口  http://www.pbc.gov.cn/diaochatongjisi/116219/116319/<year>ntjsj/hbtjgl/index.html
    该页第 2 个附件组 = 货币当局资产负债表（htm / xls(x) / pdf）
    xlsx 内：第 6 行 = 表头（A 列 '项目', B..M 列 = 2026.01 ... 2026.12）
             第 18 行 = '总资产 Total Assets'，单位「亿元人民币」
  M2（月度文字报告，正则抽取）：
    http://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html  → 各期《金融统计数据报告》
    正文含「广义货币（M2）余额XXX万亿元，同比增长X%」

设计：
  - fetch_balance()  返回 { 'YYYY-MM': 总资产(亿元) }
  - fetch_m2()       返回 { 'YYYY-MM': M2(亿元) }
  - 年度页抓取失败时优雅跳过（旧年份页面结构一致，但附件序号可能变化 → 用「附件组标题」定位）
"""
import io
import re
import time
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
BASE = "http://www.pbc.gov.cn"
YEAR_INDEX = BASE + "/diaochatongjisi/116219/116319/{y}ntjsj/hbtjgl/index.html"
M2_INDEX = BASE + "/diaochatongjisi/116219/116225/index.html"

# 已知年份页 slug（规则页 2026 → '2026ntjsj'；更早年份为纯数字）
YEAR_SLUGS = {
    2026: "2026ntjsj",
    2025: "5570903",
    2024: "5225358",
    2023: "4780803",
    2022: "4458449",
    2021: "4184109",
    2020: "3959050",
    2019: "3750274",
    2018: "3471721",
    2017: "3245697",
    2016: "3013637",
    2015: "2161324",
}


def _get(url, timeout=40, retries=3, binary=False):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            return data if binary else data.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


# ---------------------------------------------------------------- 资产负债表
def _find_year_slug(year):
    """取该年份统计页 slug：优先内置表，否则从主索引页抓。"""
    if year in YEAR_SLUGS:
        return YEAR_SLUGS[year]
    html = _get(BASE + "/diaochatongjisi/116219/116319/index.html")
    m = re.search(rf'href="(/diaochatongjisi/116219/116319/([^"/]+))/index\.html"[^>]*>\s*{year}年统计数据', html)
    if m:
        return m.group(2)
    return None


def _pick_balance_xlsx(year_slug):
    """
    先在该年「统计页索引」里找「货币统计概览」子栏目链接（2026 年为 .../hbtjgl/，
    历史年份为纯数字 ID 目录），再进入该栏目页定位
    「货币当局资产负债表」附件组的 xls(x) 链接。

    注意：附件路径有两套 —— 新页 /diaochatongjisi/attachDir/...，
    旧页 /diaochatongjisi/fileDir/resource/cms/...，且旧页多为 .xls。
    两种都要认。
    """
    idx_url = BASE + f"/diaochatongjisi/116219/116319/{year_slug}/index.html"
    idx_html = _get(idx_url)
    m = re.search(r'href="(/diaochatongjisi/116219/116319/[^"]+)"[^>]*>\s*货币统计概览', idx_html)
    if not m:
        return None
    stat_url = BASE + m.group(1)

    html = _get(stat_url)
    idx = html.find("货币当局资产负债表")
    if idx < 0:
        return None
    tail = html[idx: idx + 4000]
    m = re.search(
        r'href="(/diaochatongjisi/(?:attachDir|fileDir)/[^"]+\.xlsx?)"',
        tail,
    )
    return BASE + m.group(1) if m else None


def _read_matrix(blob, is_xls):
    """
    把附件读成二维列表 rows（每行是 values 元组/列表）。
    .xlsx 用 openpyxl；.xls 用 xlrd。
    """
    if not is_xls:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(blob), data_only=True, read_only=True)
        ws = wb[wb.sheetnames[0]]
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        return rows

    import xlrd
    book = xlrd.open_workbook(file_contents=blob)
    sh = book.sheet_by_index(0)
    return [tuple(sh.row_values(r)) for r in range(sh.nrows)]


def fetch_balance(years=None):
    """
    返回 { 'YYYY-MM': 总资产(亿元人民币) }
    years: 要抓的年份列表；默认抓内置 YEAR_SLUGS 的全部年份。
    """
    if years is None:
        years = sorted(YEAR_SLUGS)

    out = {}
    for y in years:
        slug = _find_year_slug(y)
        if not slug:
            print(f"  [pboc] {y} 年 slug 未找到，跳过")
            continue
        try:
            xurl = _pick_balance_xlsx(slug)
            if not xurl:
                print(f"  [pboc] {y} 年资产负债表附件未找到，跳过")
                continue
            is_xls = xurl.lower().endswith(".xls") and not xurl.lower().endswith(".xlsx")
            blob = _get(xurl, binary=True)
            rows = _read_matrix(blob, is_xls)

            # 表头行：含 '项目' 的那一行
            hdr_i = None
            for i, r in enumerate(rows):
                if r and r[0] and "项目" in str(r[0]):
                    hdr_i = i
                    break
            if hdr_i is None:
                print(f"  [pboc] {y} 年表头未识别，跳过")
                continue
            hdr = rows[hdr_i]
            # 列 -> (year, month)
            colmap = {}
            for ci, v in enumerate(hdr):
                if ci == 0 or v is None:
                    continue
                s = str(v).strip()
                m = re.match(r"^(\d{4})[.\-/](\d{1,2})$", s)
                if m:
                    colmap[ci] = (int(m.group(1)), int(m.group(2)))

            # 总资产行
            tot = None
            for r in rows[hdr_i + 1:]:
                if r and r[0] and re.sub(r"\s+", "", str(r[0])).startswith("总资产"):
                    tot = r
                    break
            if tot is None:
                print(f"  [pboc] {y} 年总资产行未找到，跳过")
                continue

            for ci, (yy, mm) in colmap.items():
                val = tot[ci] if ci < len(tot) else None
                if isinstance(val, (int, float)):
                    out[f"{yy:04d}-{mm:02d}"] = float(val)
            got = sum(1 for (yy, _) in colmap.values() if yy == y)
            print(f"  [pboc] {y} 年资产负债表: {got} 个月")
        except Exception as e:  # noqa: BLE001
            print(f"  [pboc] {y} 年资产负债表抓取失败: {type(e).__name__} {e}")
    return out


# ---------------------------------------------------------------------- M2
def _cn_num_to_yi(s):
    """把 '356.81万亿' 这类转成 亿元。返回 float 或 None。"""
    s = s.strip()
    m = re.match(r"^([\d.]+)\s*万亿", s)
    if m:
        return float(m.group(1)) * 10000.0
    m = re.match(r"^([\d.]+)\s*亿", s)
    if m:
        return float(m.group(1))
    return None


def _stat_url_of(year_slug):
    """返回该年「货币统计概览」栏目页 URL（或 None）。"""
    try:
        idx_html = _get(BASE + f"/diaochatongjisi/116219/116319/{year_slug}/index.html")
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r'href="(/diaochatongjisi/116219/116319/[^"]+)"[^>]*>\s*货币统计概览', idx_html)
    return BASE + m.group(1) if m else None


def _pick_m2_xlsx(stat_url):
    """在货币统计概览页里定位「货币供应量 Money Supply」附件组的 xls(x)。"""
    try:
        html = _get(stat_url)
    except Exception:  # noqa: BLE001
        return None
    i = html.find("货币供应量")
    if i < 0:
        return None
    tail = html[i: i + 4000]
    m = re.search(r'href="(/diaochatongjisi/[^"]+\.xlsx?)"', tail)
    return BASE + m.group(1) if m else None


def fetch_m2_table(years=None):
    """
    从「货币供应量 Money Supply」表抓精确 M2（亿元）。
    布局：第 6 行 = 表头（'项目 Item' 在 A 列，月份从 D 列起），
          '货币和准货币（M2）' 行给出各月 M2。
    返回 { 'YYYY-MM': M2(亿元) }
    """
    if years is None:
        years = sorted(YEAR_SLUGS)
    out = {}
    for y in years:
        slug = _find_year_slug(y)
        if not slug:
            continue
        try:
            stat_url = _stat_url_of(slug)
            if not stat_url:
                continue
            xurl = _pick_m2_xlsx(stat_url)
            if not xurl:
                print(f"  [pboc] {y} 年货币供应量表未找到")
                continue
            is_xls = xurl.lower().endswith(".xls") and not xurl.lower().endswith(".xlsx")
            rows = _read_matrix(_get(xurl, binary=True), is_xls)

            hdr_i = None
            for i, r in enumerate(rows):
                if r and r[0] and "项目" in str(r[0]):
                    hdr_i = i
                    break
            if hdr_i is None:
                continue
            hdr = rows[hdr_i]
            colmap = {}
            for ci, v in enumerate(hdr):
                if v is None:
                    continue
                m = re.match(r"^(\d{4})[.\-/](\d{1,2})$", str(v).strip())
                if m:
                    colmap[ci] = (int(m.group(1)), int(m.group(2)))

            row = None
            for r in rows[hdr_i + 1:]:
                joined = " ".join(str(x) for x in r if x is not None)
                if "M2" in joined and ("准货币" in joined or "Money" in joined):
                    row = r
                    break
            if row is None:
                continue
            for ci, (yy, mm) in colmap.items():
                val = row[ci] if ci < len(row) else None
                if isinstance(val, (int, float)):
                    out[f"{yy:04d}-{mm:02d}"] = float(val)
            print(f"  [pboc] {y} 年货币供应量: {sum(1 for (yy,_) in colmap.values() if yy==y)} 个月")
        except Exception as e:  # noqa: BLE001
            print(f"  [pboc] {y} 年货币供应量失败: {type(e).__name__} {e}")
    return out


def fetch_m2(max_pages=36):
    """
    M2 抓取入口：优先用「货币供应量」表（精确），不足时用月度《金融统计数据报告》
    新闻稿（四舍五入到「万亿」，精度低）补最近几期。
    返回 { 'YYYY-MM': M2(亿元人民币) }
    """
    out = fetch_m2_table()
    # 新闻稿兜底：补表格尚未覆盖的最新月份
    try:
        html = _get(M2_INDEX)
        found = 0
        for href, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
            t = re.sub(r"<[^>]+>", "", txt).strip()
            m = re.match(r"^(\d{4})年(\d{1,2})月金融统计数据报告$", t)
            if not m:
                continue
            yy, mm = int(m.group(1)), int(m.group(2))
            key = f"{yy:04d}-{mm:02d}"
            if key in out:
                continue
            url = href if href.startswith("http") else BASE + href
            try:
                page = re.sub(r"\s+", "", re.sub(r"<[^>]+>", " ", _get(url)))
                mm2 = re.search(r"广义货币[（(]M2[）)]?余额([\d.]+(?:万亿|亿))", page)
                if mm2:
                    v = _cn_num_to_yi(mm2.group(1))
                    if v:
                        out[key] = v
                        found += 1
            except Exception:  # noqa: BLE001
                pass
            if found >= max_pages:
                break
            time.sleep(0.2)
    except Exception:  # noqa: BLE001
        pass
    return out


if __name__ == "__main__":
    b = fetch_balance()
    k = sorted(b)
    if k:
        print(f"balance: {len(b)} months, {k[0]} -> {k[-1]}, last={b[k[-1]]}")
    m = fetch_m2()
    k = sorted(m)
    if k:
        print(f"m2: {len(m)} months, {k[0]} -> {k[-1]}, last={m[k[-1]]}")
