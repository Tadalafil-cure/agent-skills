"""
高善文方法论 · D 步数据中间层 (v1.0)
========================================
三组指标（实体/货币金融/房地产），按需拉取。
双源驱动：akshare 货币端 + NBS API 实体端 + SAFE 汇率端。

用法:
    from macro_data import D_fetch
    data = D_fetch('实体')       # 只拉实体端
    data = D_fetch('货币金融')    # 只拉货币金融端
    data = D_fetch('房地产')      # 只拉房地产端
    data = D_fetch()              # 全量
"""

import re
import sys
import urllib.request
import urllib.parse
import ssl
from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd

_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

SYSTEM_YEAR = datetime.now().year
YEARS_BACK = 3
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MacroDataMiddleware/1.0)"}
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ── 工具函数 ─────────────────────────────────────────────

def _year_range():
    return range(SYSTEM_YEAR - YEARS_BACK, SYSTEM_YEAR + 1)

EMPTY_DF = pd.DataFrame(columns=["date", "indicator", "value", "unit", "source"])


# ═══════════════════════════════════════════════════════════
#  货币金融端 — akshare
# ═══════════════════════════════════════════════════════════

def fetch_m2_yoy() -> pd.DataFrame:
    import akshare as ak
    df = ak.macro_china_money_supply()
    col = "货币和准货币(M2)-同比增长"
    df = df[["月份", col]].dropna(subset=[col]).copy()
    df["月份"] = df["月份"].str.extract(r"(\d{4})年(\d{2})月").apply(lambda r: f"{r[0]}-{r[1]}", axis=1)
    df["date"] = pd.to_datetime(df["月份"])
    return pd.DataFrame({
        "date": df["date"], "indicator": "M2同比增速", "value": df[col],
        "unit": "%", "source": "akshare/macro_china_money_supply",
    })

def fetch_m1_yoy() -> pd.DataFrame:
    import akshare as ak
    df = ak.macro_china_money_supply()
    col = "货币(M1)-同比增长"
    df = df[["月份", col]].dropna(subset=[col]).copy()
    df["月份"] = df["月份"].str.extract(r"(\d{4})年(\d{2})月").apply(lambda r: f"{r[0]}-{r[1]}", axis=1)
    df["date"] = pd.to_datetime(df["月份"])
    return pd.DataFrame({
        "date": df["date"], "indicator": "M1同比增速", "value": df[col],
        "unit": "%", "source": "akshare/macro_china_money_supply",
    })

def fetch_social_financing() -> pd.DataFrame:
    import akshare as ak
    df = ak.macro_china_shrzgm()
    df = df[["月份", "社会融资规模增量"]].dropna().copy()
    df["date"] = pd.to_datetime(df["月份"].astype(str).str[:4] + "-" + df["月份"].astype(str).str[4:6] + "-01")
    return pd.DataFrame({
        "date": df["date"], "indicator": "社会融资规模增量", "value": df["社会融资规模增量"],
        "unit": "亿元", "source": "akshare/macro_china_shrzgm",
    })

def fetch_lpr() -> pd.DataFrame:
    import akshare as ak
    df = ak.macro_china_lpr()
    result = []
    for _, row in df.iterrows():
        d = pd.to_datetime(row["TRADE_DATE"])
        for tenor, col in [("1Y", "LPR1Y"), ("5Y", "LPR5Y")]:
            v = row.get(col)
            if pd.notna(v):
                result.append({"date": d, "indicator": f"LPR_{tenor}", "value": float(v),
                               "unit": "%", "source": "akshare/macro_china_lpr"})
    return pd.DataFrame(result) if result else EMPTY_DF.copy()

def fetch_shibor_on() -> pd.DataFrame:
    import akshare as ak
    df = ak.macro_china_shibor_all()
    col = "O/N-定价"
    df = df[["日期", col]].dropna(subset=[col]).copy()
    return pd.DataFrame({
        "date": pd.to_datetime(df["日期"]), "indicator": "SHIBOR_隔夜", "value": df[col].astype(float),
        "unit": "%", "source": "akshare/macro_china_shibor_all",
    })

def fetch_fx_reserves() -> pd.DataFrame:
    import akshare as ak
    df = ak.macro_china_fx_gold()
    col = "国家外汇储备-数值"
    df = df[["月份", col]].dropna(subset=[col]).copy()
    df["月份"] = df["月份"].astype(str).str.extract(r"(\d{4})年(\d{2})月").apply(lambda r: f"{r[0]}-{r[1]}", axis=1)
    return pd.DataFrame({
        "date": pd.to_datetime(df["月份"]), "indicator": "外汇储备", "value": df[col].astype(float),
        "unit": "亿美元", "source": "akshare/macro_china_fx_gold",
    })

def fetch_usdcny() -> pd.DataFrame:
    """美元/人民币 中间价 · SAFE 外管局"""
    rows = []
    for year in _year_range():
        start = f"{year}-01-01"
        end = f"{year}-12-31" if year < SYSTEM_YEAR else datetime.now().strftime("%Y-%m-%d")
        data = urllib.parse.urlencode({"startDate": start, "endDate": end, "queryYN": "true"}).encode()
        try:
            req = urllib.request.Request(
                "http://m.safe.gov.cn/AppStructured/hlw/RMBQuery.do", data=data,
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"},
            )
            html = urllib.request.urlopen(req, timeout=15, context=SSL_CTX).read().decode("utf-8", errors="ignore")
            trs = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
            for tr in trs:
                tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL)
                cells = [re.sub(r"<[^>]+>", "", c).strip() for c in tds]
                if len(cells) >= 2 and re.match(r"\d{4}-\d{2}-\d{2}", cells[0]):
                    try:
                        rows.append({"date": pd.Timestamp(cells[0]), "indicator": "USDCNY",
                                     "value": float(cells[1]) / 100.0, "unit": "元/美元", "source": "safe.gov.cn"})
                    except ValueError:
                        pass
        except Exception:
            continue
    if rows:
        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return EMPTY_DF.copy()


# ═══════════════════════════════════════════════════════════
#  实体端 — NBS API (Playwright → data.stats.gov.cn)
# ═══════════════════════════════════════════════════════════

def _nbs_fetch(name: str, years_back: int = YEARS_BACK) -> pd.DataFrame:
    """调用 NBS API，失败时重置 session 重试一次"""
    try:
        from nbs_api import fetch_nbs
        return fetch_nbs(name, years_back=years_back)
    except Exception:
        try:
            from nbs_api import close_session, fetch_nbs
            close_session()
            return fetch_nbs(name, years_back=years_back)
        except Exception:
            return EMPTY_DF.copy()

def fetch_cpi_yoy() -> pd.DataFrame:
    """CPI 同比 (%) · 源: akshare macro_china_cpi (全国-同比增长)"""
    import akshare as ak
    df = ak.macro_china_cpi()
    df = df[["月份", "全国-同比增长"]].dropna(subset=["全国-同比增长"]).copy()
    df["月份"] = df["月份"].str.extract(r"(\d{4})年(\d{2})月份").apply(lambda r: f"{r[0]}-{r[1]}", axis=1)
    df["date"] = pd.to_datetime(df["月份"])
    return pd.DataFrame({
        "date": df["date"], "indicator": "CPI同比", "value": df["全国-同比增长"],
        "unit": "%", "source": "akshare/macro_china_cpi",
    })

def fetch_ppi_yoy() -> pd.DataFrame:
    """PPI 同比 (%) · 源: akshare macro_china_ppi (当月同比增长)"""
    import akshare as ak
    df = ak.macro_china_ppi()
    df = df[["月份", "当月同比增长"]].dropna(subset=["当月同比增长"]).copy()
    df["月份"] = df["月份"].str.extract(r"(\d{4})年(\d{2})月份").apply(lambda r: f"{r[0]}-{r[1]}", axis=1)
    df["date"] = pd.to_datetime(df["月份"])
    return pd.DataFrame({
        "date": df["date"], "indicator": "PPI同比", "value": df["当月同比增长"],
        "unit": "%", "source": "akshare/macro_china_ppi",
    })

def fetch_official_pmi() -> pd.DataFrame:
    df = _nbs_fetch("PMI_制造业")
    if len(df) > 0:
        df["indicator"] = "制造业PMI"
    return df

def fetch_nonmanufacturing_pmi() -> pd.DataFrame:
    df = _nbs_fetch("PMI_非制造业")
    if len(df) > 0:
        df["indicator"] = "非制造业PMI"
    return df

def fetch_industrial_production_yoy() -> pd.DataFrame:
    df = _nbs_fetch("工业增加值_累计增速")
    if len(df) > 0:
        df["indicator"] = "工业增加值同比"
    return df

def fetch_retail_sales_yoy() -> pd.DataFrame:
    df = _nbs_fetch("社零_累计增长")
    if len(df) > 0:
        df["indicator"] = "社零同比"
    return df

def fetch_fixed_investment_yoy() -> pd.DataFrame:
    df = _nbs_fetch("固投_累计增长")
    if len(df) > 0:
        df["indicator"] = "固投同比"
    return df

def fetch_unemployment_rate() -> pd.DataFrame:
    df = _nbs_fetch("城镇调查失业率")
    if len(df) > 0:
        df["indicator"] = "城镇调查失业率"
    return df

def fetch_trade_balance() -> pd.DataFrame:
    df = _nbs_fetch("进出口总值_同比增长")
    if len(df) > 0:
        df["indicator"] = "进出口同比"
    return df

def fetch_new_housing_sales() -> pd.DataFrame:
    df = _nbs_fetch("商品房销售面积_累计增长")
    if len(df) > 0:
        df["indicator"] = "商品房销售面积同比"
    return df

def fetch_housing_starts() -> pd.DataFrame:
    df = _nbs_fetch("房屋新开工面积_累计增长")
    if len(df) > 0:
        df["indicator"] = "房屋新开工面积同比"
    return df

def fetch_realestate_invest_yoy() -> pd.DataFrame:
    df = _nbs_fetch("房地产投资_累计增长")
    if len(df) > 0:
        df["indicator"] = "房地产投资同比"
    return df


# ═══════════════════════════════════════════════════════════
#  资产价格 / 补充
# ═══════════════════════════════════════════════════════════

def fetch_house_price_index(city: str = "全国") -> pd.DataFrame:
    """70城新建商品住宅价格指数 (同比/环比)"""
    import akshare as ak
    df = ak.macro_china_new_house_price()
    df["date"] = pd.to_datetime(df["日期"])
    if city != "全国":
        df = df[df["城市"] == city]
    result = []
    for _, row in df.iterrows():
        for suffix, col in [("同比", "新建商品住宅价格指数-同比"),
                            ("环比", "新建商品住宅价格指数-环比")]:
            v = row.get(col)
            if pd.notna(v):
                result.append({"date": row["date"], "indicator": f"70城新房价格_{suffix}",
                               "value": float(v), "unit": "%", "source": "akshare/macro_china_new_house_price"})
    return pd.DataFrame(result) if result else EMPTY_DF.copy()

def fetch_caixin_pmi() -> pd.DataFrame:
    """财新制造业/服务业/综合 PMI"""
    import akshare as ak
    frames = []
    configs = [
        (ak.index_pmi_man_cx, "PMI_财新制造业"),
        (ak.index_pmi_ser_cx, "PMI_财新服务业"),
        (ak.index_pmi_com_cx, "PMI_财新综合"),
    ]
    for fn, name in configs:
        try:
            df = fn()
            col = [c for c in df.columns if "PMI" in c and c != "变化值"][0]
            df["date"] = pd.to_datetime(df["日期"])
            frames.append(pd.DataFrame({
                "date": df["date"], "indicator": name, "value": df[col].astype(float),
                "unit": "指数", "source": f"akshare/{fn.__name__}",
            }))
        except Exception:
            pass
    if frames:
        return pd.concat(frames, ignore_index=True)
    return EMPTY_DF.copy()

def fetch_dr007() -> pd.DataFrame:
    """DR007 · 中国货币网当日加权利率 (历史序列待接 Wind/Bloomberg)"""
    try:
        # 先释放 NBS 的 Playwright，避免 browser 冲突
        try:
            from nbs_api import _session, close_session
            if _session is not None:
                close_session()
        except Exception:
            pass
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://www.chinamoney.com.cn/chinese/mtdexdaily/?tab=2",
                      timeout=20000, wait_until="networkidle")
            page.wait_for_timeout(3000)
            result = page.evaluate("""() => {
                const rows = document.querySelectorAll('tr');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td[data-name]');
                    for (const cell of cells) {
                        if (cell.getAttribute('data-value') === 'DR007') {
                            const rateCell = row.querySelector('td[data-name="wghtdAvgRepoRate"]');
                            if (rateCell) {
                                return {
                                    rate: rateCell.querySelector('.cell-value')?.textContent?.trim()
                                };
                            }
                        }
                    }
                }
                return null;
            }""")
            browser.close()
            if result and result.get("rate"):
                return pd.DataFrame([{
                    "date": pd.Timestamp.now().normalize(),
                    "indicator": "DR007",
                    "value": float(result["rate"]),
                    "unit": "%",
                    "source": "chinamoney.com.cn",
                }])
        finally:
            p.stop()
    except Exception:
        pass
    return EMPTY_DF.copy()


def fetch_gdp_yoy() -> pd.DataFrame:
    """GDP 同比增速 (%) · 源: NBS API (上年=100，减100得增速)"""
    df = _nbs_fetch("GDP指数_上年", years_back=8)
    if len(df) > 0:
        df["indicator"] = "GDP同比增速"
    return df


# ═══════════════════════════════════════════════════════════
#  指标注册表（高博三组分类）
# ═══════════════════════════════════════════════════════════

INDICATOR_GROUPS: Dict[str, Dict[str, callable]] = {
    "实体": {
        "CPI同比":            fetch_cpi_yoy,
        "PPI同比":            fetch_ppi_yoy,
        "GDP同比增速":        fetch_gdp_yoy,
        "工业增加值同比":     fetch_industrial_production_yoy,
        "社零同比":           fetch_retail_sales_yoy,
        "固投同比":           fetch_fixed_investment_yoy,
        "制造业PMI":          fetch_official_pmi,
        "非制造业PMI":        fetch_nonmanufacturing_pmi,
        "财新PMI":            fetch_caixin_pmi,
        "城镇调查失业率":     fetch_unemployment_rate,
        "进出口同比":         fetch_trade_balance,
    },
    "货币金融": {
        "DR007":              fetch_dr007,         # 先拉，在 NBS session 还开着时用独立 Playwright
        "M2同比增速":         fetch_m2_yoy,
        "M1同比增速":         fetch_m1_yoy,
        "社会融资规模增量":   fetch_social_financing,
        "LPR":                fetch_lpr,
        "SHIBOR隔夜":         fetch_shibor_on,
        "外汇储备":           fetch_fx_reserves,
        "美元人民币汇率":     fetch_usdcny,
    },
    "房地产": {
        "70城新房价格":       fetch_house_price_index,
        "商品房销售面积同比": fetch_new_housing_sales,
        "房屋新开工面积同比": fetch_housing_starts,
        "房地产投资同比":     fetch_realestate_invest_yoy,
    },
}

# 全量注册表
INDICATOR_REGISTRY: Dict[str, callable] = {}
for g in INDICATOR_GROUPS.values():
    INDICATOR_REGISTRY.update(g)


# ═══════════════════════════════════════════════════════════
#  D_fetch — 统一入口
# ═══════════════════════════════════════════════════════════

def D_fetch(group: str = None, years_back: int = YEARS_BACK, verbose: bool = True) -> Dict[str, pd.DataFrame]:
    """拉取宏观数据。group: '实体'/'货币金融'/'房地产'/None(全量)"""
    registry = INDICATOR_GROUPS.get(group) if group else INDICATOR_REGISTRY
    if registry is None:
        print(f"未知分组: {group}，可选: {list(INDICATOR_GROUPS.keys())}")
        return {}

    start_date = pd.Timestamp(f"{SYSTEM_YEAR - years_back}-01-01")
    end_date = pd.Timestamp.now()

    results = {}
    total = len(registry)
    success_count = 0
    nbs_call_count = 0

    for i, (name, fn) in enumerate(registry.items(), 1):
        # NBS session 管理：每 4 次调用重置
        is_nbs = name in {"GDP同比增速", "工业增加值同比", "社零同比", "固投同比",
                          "制造业PMI", "非制造业PMI", "城镇调查失业率", "进出口同比",
                          "商品房销售面积同比", "房屋新开工面积同比", "房地产投资同比"}
        if is_nbs:
            if nbs_call_count >= 4:
                try:
                    from nbs_api import close_session; close_session()
                except Exception:
                    pass
                nbs_call_count = 0
            nbs_call_count += 1

        if verbose:
            print(f"[{i}/{total}] 拉取 {name}...", end=" ")
        try:
            df = fn()
            if df is not None and len(df) > 0:
                if "date" in df.columns:
                    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
                    df = df.sort_values("date", ascending=False).reset_index(drop=True)
                results[name] = df
                success_count += 1
                if verbose:
                    print(f"✅ {len(df)} 行")
            else:
                if verbose:
                    print("⚠️ 无数据")
        except Exception as e:
            if verbose:
                print(f"❌ {type(e).__name__}: {e}")
            results[name] = EMPTY_DF.copy()

    try:
        from nbs_api import close_session; close_session()
    except Exception:
        pass

    if verbose:
        print(f"\n{group or '全量'}: {success_count}/{total} 指标成功")
    return results


def D_summary(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """将 D_fetch 结果合并为总表"""
    frames = [df for df in data.values() if df is not None and len(df) > 0]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(["date", "indicator"])


# ── CLI ──
if __name__ == "__main__":
    import sys
    group = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"高善文方法论 · 数据中间层 v1.0")
    print(f"时间范围: {SYSTEM_YEAR - YEARS_BACK} - {SYSTEM_YEAR}")
    data = D_fetch(group=group, verbose=True)
    print("\n── 数据样例 ──")
    for name, df in data.items():
        if len(df) > 0:
            latest = df.iloc[-1]
            print(f"  {name}: 最新 {latest['date'].strftime('%Y-%m') if hasattr(latest['date'], 'strftime') else latest['date']} = {latest['value']}")
