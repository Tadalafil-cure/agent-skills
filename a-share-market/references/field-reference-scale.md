# get_scale_comparison() — 行业规模对比（v1.0.2 重写）

- data 类型：`list[dict]` — 同行列表，按总市值降序
- data[0] 字段：`代码` `简称` `总市值` `总市值排名` `流通市值` `流通市值排名` `营业收入` `营业收入排名` `净利润` `净利润排名`
- meta：`rows` `cols` `columns` `board`（行业名，如"白酒Ⅱ"/"通信设备"/"电池"）`report_type`（报告期，如"2026年一季报"）
- source: `em-datacenter-scale`（直调 EM datacenter API）
- pageSize: 500（确保大行业不截断）

## symbol_to_board() 返回结构

```python
{
    "success": True,
    "symbol": "300394",
    "board": "通信设备",    # ← 顶层，不是 data.board
    "source": "申万行业",
    "peers": [...],         # 同行成分股（可选）
    "peers_count": 86,
}
```

⚠️ `symbol_to_board` 返回顶层字段（board/peers），没有 data 包装层。
