#!/usr/bin/env bash
# ccusage compact display for narrow tmux panes
npx ccusage daily --since "$(date -d '30 days ago' +%Y%m%d)" --json --offline --no-color 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data['daily']:
    print(f\"{r['date']}  \${r['totalCost']:.2f}  in:{r['inputTokens']:,}  out:{r['outputTokens']:,}\")
t = data.get('total', {})
if t:
    print(f'---')
    print(f\"Total     \${t.get('totalCost', 0):.2f}\")
"
