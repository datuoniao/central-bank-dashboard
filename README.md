# G4 央行资产负债表 · M2 · 大宗商品 联动看板

中美欧日四大央行（G4）**资产负债表规模**、**广义货币 M2** 与**大宗商品价格**（黄金 / 铜 / Brent 原油）的月度对照看板。逻辑沿袭原 Excel《货币与商品价格对照.xlsx》，但改为**网页看板 + 每月自动更新**。

---

## 看板内容（精选核心图组）

| 分区 | 图表 |
|---|---|
| 最新读数 | G4 央行总资产 / 四国资产 / G4 M2 / 黄金 / 铜 / 布伦特的当月值与同比 |
| 一、央行资产负债表 | ① G4 总资产合计 ② 四国资产分列 ③ 同比增速 ④ 结构占比（堆叠）⑤ 美/欧/日分列 ⑥ **G4 扩表 ↔ 商品 相关性** |
| 二、广义货币 M2 | G4 M2 合计 + 同比；四经济体 M2 分列 |
| 三、大宗商品 | 价格指数（起点=100）；黄金 vs G4 扩表；铜 vs 中国扩表；**自由对照：商品 × 央行（可交互）**；**全部商品 × 央行 相关系数矩阵**；口径说明 |

### 交互式对照（新增）

**「自由对照：商品 × 央行」** 让你任选商品与央行，查看同比联动：

- 可选**商品**：黄金 / 铜 / Brent 原油
- 可选**央行**：G4 合计 / 中国 / 美国 / 欧元区 / 日本
- 共 15 种组合，切换即时重绘，并显示该组合的**同期皮尔逊相关系数 r**
- **「相关系数矩阵」** 用 15 格热力图总览全部组合，**点击任意单元格即可切换到对应图表**（红=正相关，绿=负相关）
- 支持 URL 深链分享，例如 `index.html#price=copper&bal=cn` 直接打开「铜 × 中国」

---

## 前端依赖加载（重要）

ECharts 采用**「本地内置 + 多 CDN 兜底」**策略，避免单一 CDN 不可达导致 `echarts is not defined`：

1. 首选本地 `assets/vendor/echarts.min.js`（已随仓库提交，最稳、离线可用）
2. 回退顺序：bootcdn → jsdelivr → unpkg → cdnjs
3. 只有本地文件缺失且全部 CDN 不可用时，才会降级为「仅显示 KPI 与相关系数表」并给出明确提示（不再出现 `echarts is not defined` 的空白页）

---

## 单位口径（与原 Excel 完全一致，单位 = **亿美元 / 100 million USD**）

**资产负债表**

| 经济体 | 原始值 | 换算 |
|---|---|---|
| 中国 | 亿元 | `÷ USDCNY` |
| 美国 | 百万美元 | `÷ 100` |
| 欧元区 | 百万欧元 | `× EURUSD ÷ 100` |
| 日本 | 日元 | `÷ USDJPY ÷ 1e8` |
| G4 合计 | — | 四国简单加总 |

**M2**

| 经济体 | 原始值 | 换算 |
|---|---|---|
| 中国 | 亿元 | `÷ USDCNY` |
| 美国 | 十亿美元 | `× 10` |
| 欧元区 | 百万欧元 | `× EURUSD ÷ 100` |
| 日本 | 亿日元 | `÷ USDJPY` |

> 汇率一律取**当月均值**（原 Excel 即为此口径）。

---

## 数据源（全部免 Key，可在 GitHub Actions 运行）

| 源 | 内容 | 端点 |
|---|---|---|
| **中国人民银行** | 货币当局资产负债表总资产、货币供应量 M2 | `pbc.gov.cn/diaochatongjisi`（年度统计页附件 `.xls/.xlsx`） |
| **FRED** | 美国 WALCL / M2SL、欧洲央行 ECBASSETSW、日本银行 JPNASSETS、汇率 DEXCHUS / DEXJPUS / DEXUSEU | `fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>` |
| **World Bank Pink Sheet** | Brent 原油 / 黄金 / 铜 月度价 | `CMO-Historical-Data-Monthly.xlsx` |
| iFinD（可选兜底） | 本地会话补数 | 见 `scripts/fetch_ifind_manual.py` |

---

## 目录结构

```
central-bank-dashboard/
├─ index.html                  # 看板首页
├─ assets/
│   ├─ app.js                  # ECharts 渲染（12 张图 + KPI + 可交互对照 + 相关系数矩阵）
│   └─ vendor/echarts.min.js   # 本地内置 ECharts（CDN 兜底的第一优先）
│   └─ style.css               # 明/暗双主题样式
├─ data/
│   ├─ excel_history.json      # 历史底座（由原 Excel 迁移，2003 起）
│   ├─ raw_latest.json         # 每月抓取的公开源原始数据
│   ├─ raw_ifind.json          # 可选：本地 iFinD 兜底
│   └─ dashboard.json          # 前端直接消费的成品数据
├─ scripts/
│   ├─ migrate_excel.py        # 原 Excel → excel_history.json（一次性）
│   ├─ sources/
│   │   ├─ fred.py             # FRED 抓取
│   │   ├─ ecb_sdw.py          # ECB Data Portal 抓取
│   │   ├─ worldbank.py        # World Bank Pink Sheet 抓取
│   │   └─ pboc.py             # 中国人民银行抓取
│   ├─ fetch_all.py            # 抓取入口（产出 raw_latest.json）
│   ├─ transform.py            # 合并 / 归一 / 派生（产出 dashboard.json）
│   └─ fetch_ifind_manual.py   # 本地 iFinD 兜底
├─ .github/workflows/update.yml# 每月 5 日自动更新
└─ requirements.txt
```

---

## 本地运行

```bash
# 1) 依赖
pip install -r requirements.txt

# 2) （首次）把原 Excel 迁成历史底座
python scripts/migrate_excel.py

# 3) 抓取公开源 → 原始数据
python scripts/fetch_all.py

# 4) 合并归一 → 成品数据
python scripts/transform.py

# 5) 本地预览（必须用 http 服务，直接双击 index.html 会因 CORS 取不到 json）
python -m http.server 8000
# 浏览器打开 http://localhost:8000
```

---

## 自动更新（GitHub Actions）

`.github/workflows/update.yml` 已配置：

- **触发**：每月 5 日 09:00 UTC（北京时间 17:00）；也支持在 Actions 页手动 `Run workflow`。
- **流程**：`fetch_all.py` → `transform.py` → 提交 `data/*.json` 回仓库 → （可选）部署 GitHub Pages。
- **权限**：需要仓库 `Settings → Actions → General → Workflow permissions` 选 **Read and write**。

## 部署到 GitHub Pages

1. 建仓库并把本目录推上去。
2. `Settings → Pages → Build and deployment → Source` 选 **Deploy from a branch**，分支 `main`、目录 `/ (root)`。
3. 访问 `https://<用户名>.github.io/<仓库名>/` 即可。

> 若希望 Action 每次更新后自动重新发布，可解开 `update.yml` 末尾注释，改用 `Source = GitHub Actions`。

---

## 口径与已知限制

- **日本央行总资产**：FRED `JPNASSETS` 为「亿日元」，脚本已 `× 1e8` 转成日元后再按 `÷ USDJPY ÷ 1e8` 折算；与中国/美国/欧元区口径一致。
- **报价延迟**：PBOC 资产负债表通常滞后 1–2 个月（例：2026-09 月份数据为空占位属正常）；World Bank Pink Sheet 更新较慢（约滞后数月），黄金/铜/原油的最新月份由 FRED 与 Excel 底座兜底。
- **M2 精确度**：优先取 PBOC「货币供应量」表（精确），新闻稿口径（四舍五入到万亿）仅在表格未覆盖时兜底。
- 本看板仅供研究参考，不构成任何投资建议。
