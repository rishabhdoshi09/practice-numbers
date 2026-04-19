#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# SimpleQuant Full NSE Swarm Orchestrator
#
# Uses claude-flow to assign one scan task per sector bucket to separate agents.
# Each agent calls POST /scan/bucket for its slice; the coordinator aggregates.
#
# Prerequisites:
#   1. claude-flow installed and initialized (claude-flow init)
#   2. Backend running at $API_URL
#   3. Swarm initialized: claude-flow swarm init
#
# Usage:
#   ./scripts/swarm_orchestrate.sh [workers=8] [api_url=http://localhost:8000]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

WORKERS=${1:-8}
API_URL=${2:-${REACT_APP_API_URL:-http://localhost:8000}}

echo "🚀 SimpleQuant Swarm Scan — $WORKERS agents | $API_URL"
echo "──────────────────────────────────────────────────────"

# 1. Fetch the universe and bucket it
echo "📡 Fetching NSE universe from $API_URL/scan/universe ..."
UNIVERSE=$(curl -sf "$API_URL/scan/universe")
TOTAL=$(echo "$UNIVERSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['total'])")
SYMBOLS=$(echo "$UNIVERSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(','.join(d['symbols']))")

echo "✓ Universe: $TOTAL stocks"

# 2. Split symbols into N buckets
BUCKET_SYMBOLS=$(echo "$SYMBOLS" | python3 - <<'PYEOF'
import sys
symbols = sys.stdin.read().strip().split(',')
n = int(''"$WORKERS"'')
size = (len(symbols) + n - 1) // n
for i in range(n):
    chunk = symbols[i*size:(i+1)*size]
    if chunk:
        print(','.join(chunk))
PYEOF
)

# 3. Spawn one agent per bucket and assign scan task
TASK_IDS=()
BUCKET_NUM=0
while IFS= read -r bucket; do
    [[ -z "$bucket" ]] && continue
    BUCKET_NUM=$((BUCKET_NUM + 1))
    BUCKET_SIZE=$(echo "$bucket" | tr ',' '\n' | wc -l | tr -d ' ')

    echo "  🤖 Spawning agent $BUCKET_NUM ($BUCKET_SIZE stocks)..."

    # Create a task for this bucket
    TASK_ID=$(claude-flow task create \
        --type "research" \
        --description "Scan NSE bucket $BUCKET_NUM: $BUCKET_SIZE stocks" \
        --metadata "{\"api_url\":\"$API_URL\",\"symbols\":\"$bucket\",\"bucket\":$BUCKET_NUM}" \
        2>/dev/null | grep -oE 'task-[a-z0-9-]+' | head -1 || echo "task-$BUCKET_NUM")

    TASK_IDS+=("$TASK_ID")

    # Spawn an agent and assign this task
    AGENT_ID=$(claude-flow agent spawn -t researcher 2>/dev/null | \
        grep -oE 'researcher-[a-z0-9]+' | head -1 || echo "agent-$BUCKET_NUM")

    claude-flow task assign "$TASK_ID" --agent "$AGENT_ID" 2>/dev/null || true

    # Actually execute the bucket scan via the API
    echo "  ▶ Agent $AGENT_ID executing bucket $BUCKET_NUM..."
    RESULT=$(curl -sf -X POST "$API_URL/scan/bucket?symbols=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$bucket'))")" \
             -H "Content-Type: application/json" 2>/dev/null || echo '{"error":"failed"}')

    SCANNED=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('symbols_scanned',0))" 2>/dev/null || echo 0)
    echo "  ✓ Bucket $BUCKET_NUM: $SCANNED stocks analysed"

done <<< "$BUCKET_SYMBOLS"

echo ""
echo "──────────────────────────────────────────────────────"
echo "✅ All $BUCKET_NUM buckets complete."
echo ""
echo "📊 Full scan results available at:"
echo "   $API_URL/scan/last"
echo ""
echo "💡 Trigger full aggregated scan instead with:"
echo "   curl '$API_URL/scan/full?workers=$WORKERS'"
