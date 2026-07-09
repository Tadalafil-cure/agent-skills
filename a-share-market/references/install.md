# Middleware 安装与验证

## 依赖安装

```bash
# venv (execute_code 环境)
uv pip install pandas akshare baostock requests --python ~/.hermes/hermes-agent/venv/bin/python3
```

## Middleware 安装

源码位置：
- Market: `/home/admin/A-share-market-middleware/`
- Finance: `/home/admin/a-share-finance-middleware/`

```bash
# 安装 market middleware
uv pip install -e /home/admin/A-share-market-middleware --python ~/.hermes/hermes-agent/venv/bin/python3

# 安装 finance middleware（依赖 market）
uv pip install -e /home/admin/a-share-finance-middleware --python ~/.hermes/hermes-agent/venv/bin/python3
```

## 常见陷阱

### root-owned egg-info 导致安装失败

症状：`error: Cannot update time stamp of directory 'a_share_market_middleware.egg-info'`

原因：源码目录（从 root 迁入）的 egg-info 目录属主为 root。

修复：
```bash
sudo chown -R admin:admin /home/admin/A-share-market-middleware
sudo chown -R admin:admin /home/admin/a-share-finance-middleware
```

### Baostock 直接调用超时

`baostock.login()` 直接调用可能超时，但中间层包装后正常——中间层有 login/logout 管理和重试逻辑。测试 bs 源应通过中间层函数（如 `get_financial_abstract`），不裸调 baostock。

## 全量验证

```bash
~/.hermes/hermes-agent/venv/bin/python3 -c "
from a_share_market_middleware.stock.realtime import get_realtime_quote
from a_share_market_middleware.stock.kline import get_daily_kline
from a_share_market_middleware.stock.flow import get_individual_fund_flow
from a_share_market_middleware.sector.board import get_board_spot
from a_share_market_middleware.sector.concept import get_concept_spot
from a_share_market_middleware.overall.index_quotes import get_index_quotes
from a_share_market_middleware.overall.market import get_market_breadth

tests = [
    ('realtime', get_realtime_quote('600519')),
    ('daily_kline', get_daily_kline('600519')),
    ('fund_flow', get_individual_fund_flow('300136')),
    ('board_spot', get_board_spot('industry')),
    ('concept_spot', get_concept_spot()),
    ('index_quotes', get_index_quotes()),
    ('breadth', get_market_breadth()),
]
for name, r in tests:
    print(f'{name}: {\"OK\" if r.get(\"success\") else \"FAIL\"} src={r.get(\"source\",\"?\")}')
"
```

注意：`execute_code` 有 5 分钟超时，跑全量 15+ 函数会超时。验证请用 `terminal()` 分批跑。
