#!/bin/bash
# factor_signal_update.sh — 个股因子信号池批量更新（no_agent cron 脚本）
# factor_quality.py 自己写 JSON 到 data/stocks/{code}.json
# 本脚本只负责循环调用 + 校验

SKILL_DIR="/home/admin/agent-skills/factor-quality"
STOCKS_DIR="$SKILL_DIR/data/stocks"

STOCKS=("002709" "300136" "002885" "300750" "601899" "300274")
NAMES=("天赐材料" "信维通信" "京泉华" "宁德时代" "紫金矿业" "阳光电源")

SUCCESS=0
FAIL=0

echo "=== 个股因子信号池更新 — $(date +%Y%m%d_%H%M%S) ==="

for i in "${!STOCKS[@]}"; do
    CODE="${STOCKS[$i]}"
    NAME="${NAMES[$i]}"
    OUTFILE="$STOCKS_DIR/${CODE}.json"
    LOGFILE="$STOCKS_DIR/${CODE}.log"
    
    echo -n "[$((i+1))/${#STOCKS[@]}] $NAME ($CODE) "
    
    cd "$SKILL_DIR" && python3 factor_quality.py --stock "$CODE" --force > "$LOGFILE" 2>&1
    EXIT=$?
    
    if [ $EXIT -eq 0 ] && [ -s "$OUTFILE" ] && python3 -c "import json; json.load(open('$OUTFILE'))" 2>/dev/null; then
        echo "✅ $(wc -c < "$OUTFILE") bytes"
        SUCCESS=$((SUCCESS + 1))
    else
        echo "❌ exit=$EXIT"
        tail -3 "$LOGFILE" 2>/dev/null
        FAIL=$((FAIL + 1))
    fi
    
    sleep $((1 + RANDOM % 2))
done

echo "=== $SUCCESS 成功 / $FAIL 失败 ==="
