"""
NBS 数据平台 API 采集器
======================
通过 Playwright 管理 session cookie，调用 data.stats.gov.cn 的 JSON API。
"""
import json
from datetime import datetime
from typing import Dict, Optional

import pandas as pd

ESDATA_PATH = "/dg/website/publicrelease/web/external/stream/esData"
ROOT_ID = "fc982599aa684be7969d7b90b1bd0e84"
SYSTEM_YEAR = datetime.now().year

# ── 指标映射表 ──
INDICATOR_MAP = {
    "CPI_上年同月": {
        "cid": "5c7452825c7c4dcba391db5ca7f335c5",
        "iid": "53180dfb9c14411ba4b762307c85920c",
        "unit": "上年同月=100",
        "note": "减100得同比%",
    },
    "工业增加值_累计增速": {
        "cid": "3f2e14f0542348ed9fe02476eca3450b",
        "iid": "ef1b1765960d45a29b4d7c4ca91be916",
        "unit": "%",
    },
    "社零_同比增长": {
        "cid": "d0cb882c7f27443ab6b3ef9421901961",
        "iid": "aaac57d54d2e465d91bc9f3ea1a8618e",
        "unit": "%",
        "note": "当月同比",
    },
    "社零_累计增长": {
        "cid": "d0cb882c7f27443ab6b3ef9421901961",
        "iid": "e3ca151b53d347b78d1e179e5ebf1d33",
        "unit": "%",
        "note": "累计同比",
    },
    "PMI_制造业": {
        "cid": "93ffbb1aa85740d3aa2618371508b606",
        "iid": "a09aa989bdcf4cffa2021795722eb916",
        "unit": "%",
    },
    "PMI_非制造业": {
        "cid": "7a64a6e25aec4a8e9dde044ecd9e2cce",
        "iid": "88a150208f6e4a1db8babe41ae700f66",
        "unit": "%",
    },
    "城镇调查失业率": {
        "cid": "ee3b7046b390415b9b7745e3d16f6052",
        "iid": "3888eac6062945a79c8a27e5f13d4953",
        "unit": "%",
    },
    "房地产投资_累计增长": {
        "cid": "9206137ccf03460daa74b7799e0f3c31",
        "iid": "205e08cba8c2409980db58c98da91b6f",
        "unit": "%",
        "note": "累计同比",
    },
    # ── 年度数据 (code=3, dts=YYYYYY-YYYYYY) ──
    "GDP指数_上年": {
        "cid": "489888799f8d470786bc01a4057efc38",
        "iid": "93dd15c8a3a3400ea89f8dceec7ab2b3",
        "unit": "上年=100",
        "freq": "year",
        "note": "减100得增速%",
    },
    "CPI_上年_年度": {
        "cid": "e5f37eced5de4d4c815f7ac5f59fc6c2",
        "iid": "5e3053f110074dcdbcfa3c8428dd1367",
        "unit": "上年=100",
        "freq": "year",
    },
    "PPI_上年_年度": {
        "cid": "e5f37eced5de4d4c815f7ac5f59fc6c2",
        "iid": "a867836c8fdc4e2dbf06be1dc87fafc6",
        "unit": "上年=100",
        "freq": "year",
    },
    # ── 月度补充 ──
    "固投_累计增长": {
        "cid": "5129067b149d4ddfbec1ffc478d35bfb",
        "iid": "7e570cf8071c4734a7d78d9f0a70fbe1",
        "unit": "%",
        "note": "固定资产投资累计同比",
    },
    "商品房销售面积_累计增长": {
        "cid": "0ae633cdb85f4a8397650831b2b27e50",
        "iid": "50a37fbef1d04be68f15d82b711783bf",
        "unit": "%",
        "note": "新建商品房销售面积累计同比",
    },
    "房屋新开工面积_累计增长": {
        "cid": "cac0766314e045ea82f69886aabd31b0",
        "iid": "d0bfd7e4b56a4bb98cea7cfd141475d9",
        "unit": "%",
        "note": "房地产新开工施工面积累计同比",
    },
    "进出口总值_同比增长": {
        "cid": "7e11b47c828d4e4e925f1c5a98305558",
        "iid": "5143e29f77ee4d3489eaf46b901ba610",
        "unit": "%",
        "note": "进出口总值当月同比",
    },
}


class NBSSession:
    """管理 NBS API session（cookie + Playwright browser）"""

    def __init__(self):
        self._browser = None
        self._page = None

    def _ensure(self):
        if self._page is not None:
            return
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._page = self._browser.new_page()
        self._page.goto(
            "https://data.stats.gov.cn/dg/website/page.html#/pc/national/monthData",
            timeout=30000,
            wait_until="networkidle",
        )
        self._page.wait_for_timeout(3000)

    def close(self):
        if self._browser:
            self._browser.close()
        if hasattr(self, "_pw"):
            self._pw.stop()
        self._page = None
        self._browser = None

    def fetch(self, name: str, start_year: int = None, end_year: int = None) -> pd.DataFrame:
        """拉取单个指标"""
        self._ensure()

        if name not in INDICATOR_MAP:
            return pd.DataFrame(columns=["date", "indicator", "value", "unit", "source"])

        cfg = INDICATOR_MAP[name]
        sy = start_year or SYSTEM_YEAR - 3
        ey = end_year or SYSTEM_YEAR
        is_year = cfg.get("freq") == "year"
        dts = f"{sy}YY-{ey}YY" if is_year else f"{sy}01MM-{ey}12MM"

        payload = {
            "cid": cfg["cid"],
            "indicatorIds": [cfg["iid"]],
            "daCatalogId": "",
            "das": [{"text": "全国", "value": "000000000000"}],
            "showType": "1",
            "dts": [dts],
            "rootId": ROOT_ID,
        }

        result = self._page.evaluate(
            """async (p) => {
            const resp = await fetch('/dg/website/publicrelease/web/external/stream/esData', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(p)
            });
            const data = await resp.json();
            return (data.data || []).map(d => ({
                code: d.code,
                values: (d.values || []).map(v => ({value: v.value}))
            }));
        }""",
            payload,
        )

        rows = []
        is_index = "上年=100" in cfg.get("unit", "") or "上年同月" in cfg.get("unit", "")
        for month_block in result:
            code = month_block.get("code", "")
            # 年度: "2024YY" → "2024"; 月度: "202605MM" → "2026-05"
            if is_year:
                if not code.endswith("YY"):
                    continue
                date_str = code[:4]
            else:
                if not code.endswith("MM"):
                    continue
                date_str = code[:4] + "-" + code[4:6]
            for v in month_block.get("values", []):
                raw = v.get("value", "")
                if raw == "" or raw is None:
                    continue
                try:
                    val = float(raw)
                except ValueError:
                    continue
                if is_index:
                    val = round(val - 100.0, 1)  # 上年=100 → 同比%
                rows.append({
                    "date": pd.Timestamp(date_str),
                    "indicator": name,
                    "value": val,
                    "unit": "%" if is_index else cfg["unit"],
                    "source": "data.stats.gov.cn",
                })

        if not rows:
            return pd.DataFrame(columns=["date", "indicator", "value", "unit", "source"])
        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


# ── 全局 session ──
_session: Optional[NBSSession] = None


def fetch_nbs(name: str, years_back: int = 3) -> pd.DataFrame:
    """便捷入口：拉取单个 NBS 指标（复用 session）"""
    global _session
    if _session is None:
        _session = NBSSession()
    return _session.fetch(name, start_year=SYSTEM_YEAR - years_back)


def fetch_all_nbs(years_back: int = 3, verbose: bool = True) -> Dict[str, pd.DataFrame]:
    """批量拉取全部 NBS 指标"""
    global _session
    if _session is None:
        _session = NBSSession()

    results = {}
    for name in INDICATOR_MAP:
        if verbose:
            print(f"  NBS/{name}...", end=" ", flush=True)
        df = _session.fetch(name, start_year=SYSTEM_YEAR - years_back)
        if len(df) > 0:
            results[name] = df
            if verbose:
                print(f"✅ {len(df)}行")
        else:
            if verbose:
                print("❌")
    return results


def close_session():
    global _session
    if _session:
        _session.close()
        _session = None


# ── CLI ──
if __name__ == "__main__":
    print(f"NBS API 采集器 ({len(INDICATOR_MAP)} 指标)\n")
    data = fetch_all_nbs(years_back=3)
    for name, df in data.items():
        latest = df.iloc[-1]
        print(f"  {name:20s}  {latest['date'].strftime('%Y-%m')} = {latest['value']:8.2f}")
    close_session()
