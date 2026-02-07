<div align="center">

# multi-agent-shogun

**Command your AI army like a feudal warlord.**

Run 12 Claude Code agents across 3 tmux sessions — orchestrated through a feudal hierarchy with zero coordination overhead.

[![GitHub Stars](https://img.shields.io/github/stars/yohey-w/multi-agent-shogun?style=social)](https://github.com/yohey-w/multi-agent-shogun)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Built_for-Claude_Code-blueviolet)](https://code.claude.com)
[![Shell](https://img.shields.io/badge/Shell%2FBash-100%25-green)]()

[English](README.md) | [日本語](README_ja.md)

</div>

<p align="center">
  <img src="assets/screenshots/tmux_multiagent_9panes.png" alt="multi-agent-shogun: 9 panes running in parallel" width="800">
</p>

<p align="center"><i>Shogun system: 2 Karo managing 8 workers + 1 auditor across 3 tmux sessions.</i></p>

---

Give a single command. The **Shogun** (general) delegates to two **Karo** — **Roju** (external projects) and **Midaidokoro** (internal system) — who distribute work across **8 Ashigaru and Heyago workers**. Communication flows through an **SQLite database** and tmux `send-keys`, meaning **zero extra API calls** for agent coordination.

<!-- TODO: add demo.gif — record with asciinema or vhs -->

## Why Shogun?

Most multi-agent frameworks burn API tokens on coordination. Shogun doesn't.

| | Claude Code `Task` tool | LangGraph | CrewAI | **multi-agent-shogun** |
|---|---|---|---|---|
| **Architecture** | Subagents inside one process | Graph-based state machine | Role-based agents | Feudal hierarchy via tmux |
| **Parallelism** | Sequential (one at a time) | Parallel nodes (v0.2+) | Limited | **11 independent agents** |
| **Coordination cost** | API calls per Task | API + infra (Postgres/Redis) | API + CrewAI platform | **Zero** (SQLite DB + tmux) |
| **Observability** | Claude logs only | LangSmith integration | OpenTelemetry | **Live tmux panes** + dashboard |
| **Skill discovery** | None | None | None | **Bottom-up auto-proposal** |
| **Setup** | Built into Claude Code | Heavy (infra required) | pip install | Shell scripts |

### What makes this different

**Zero coordination overhead** — Agents communicate through an SQLite database (Botsunichiroku) and tmux send-keys. The only API calls are for actual work, not orchestration. Run 11 agents and pay only for 11 agents' work.

**Full transparency** — Every agent runs in a visible tmux pane. Every instruction, report, and decision is a plain YAML file you can read, diff, and version-control. No black boxes.

**Battle-tested hierarchy** — The Shogun → Karo → Ashigaru chain of command prevents conflicts by design: clear ownership, dedicated files per agent, event-driven communication, no polling.

---

## Bottom-Up Skill Discovery

This is the feature no other framework has.

As Ashigaru execute tasks, they **automatically identify reusable patterns** and propose them as skill candidates. The Karo aggregates these proposals in `dashboard.md`, and you — the Lord — decide what gets promoted to a permanent skill.

```
Ashigaru finishes a task
    ↓
Notices: "I've done this pattern 3 times across different projects"
    ↓
Reports in YAML:  skill_candidate:
                     found: true
                     name: "api-endpoint-scaffold"
                     reason: "Same REST scaffold pattern used in 3 projects"
    ↓
Appears in dashboard.md → You approve → Skill created in .claude/skills/
    ↓
Any agent can now invoke /api-endpoint-scaffold
    ↓
Ohariko (お針子) audits text deliverables before finalization
```

Skills grow organically from real work — not from a predefined template library. Your skill set becomes a reflection of **your** workflow.

---

## Architecture

```
        You (上様 / The Lord)
             │
             ▼  Give orders
      ┌─────────────┐     ┌──────────────┐
      │   SHOGUN    │ ←───│   OHARIKO    │  Auditor + pre-assigner
      │    (将軍)    │     │  (お針子)     │  Direct line to Shogun
      └──────┬──────┘     └──────────────┘
             │ DB + send-keys
       ┌─────┴──────┐
       │            │
┌──────▼──────┐ ┌──────▼──────┐
│    ROJU     │ │ MIDAIDOKORO │
│   (老中)    │ │  (御台所)    │
│ External PJ │ │ Internal sys│
└──────┬──────┘ └──────┬──────┘
       │               │
  ┌─┬─┬┴┬─┐      ┌─┬─┬┘
  │1│2│3│4│5│      │1│2│3│
  └─┴─┴─┴─┴─┘      └─┴─┴─┘
   ASHIGARU          HEYAGO
  (足軽 1-5)        (部屋子 1-3)
```

- 3 sessions: `shogun` (1 pane), `multiagent` (6 panes), `ooku` (5 panes)
- Roju manages external projects with Ashigaru 1-5
- Midaidokoro manages internal system with Heyago 1-3
- Ohariko audits deliverables and pre-assigns idle workers

**Communication protocol:**
- **Downward** (orders): Register subtask in Botsunichiroku DB → wake target with `tmux send-keys`
- **Upward** (reports): Register report in Botsunichiroku DB → wake manager with `send-keys`
- **Audit**: Ohariko reviews text deliverables → reports directly to Shogun
- **Polling**: Forbidden. Event-driven only. Your API bill stays predictable.

**Context persistence (4 layers):**

| Layer | What | Survives |
|-------|------|----------|
| Memory MCP | Preferences, rules, cross-project knowledge | Everything |
| Project files | `config/projects.yaml`, `context/*.md` | Everything |
| Botsunichiroku DB | Commands, subtasks, reports (SQLite) | Everything |
| Session | `CLAUDE.md`, instructions | `/clear` wipes it |

After `/clear`, an agent recovers in **~5,000 tokens** by reading Memory MCP + its assigned subtasks from the DB. No expensive re-prompting.

---

## Battle Formations

Agents can be deployed in different **formations** (陣形 / *jindate*) depending on the task:

| Formation | Shogun | Karo (x2) | Ashigaru 1-4 | Ashigaru 5 | Heyago 1-3 | Ohariko |
|-----------|--------|-----------|-------------|-----------|-----------|---------|
| **Normal** (default) | Opus | Opus Thinking | Sonnet Thinking | Opus Thinking | Opus Thinking | Sonnet Thinking |
| **Battle** (`-k` flag) | Opus | Opus Thinking | Opus Thinking | Opus Thinking | Opus Thinking | Sonnet Thinking |

```bash
./shutsujin_departure.sh          # Normal formation (3 sessions: shogun + multiagent + ooku)
./shutsujin_departure.sh -k       # Battle formation (all Opus Thinking for Ashigaru)
```

The Karo can also promote individual Ashigaru mid-session with `/model opus` when a specific task demands it, or demote Opus workers to Sonnet for cost-efficient tasks.

---

## Quick Start

### Windows (WSL2)

```bash
# 1. Clone
git clone https://github.com/yohey-w/multi-agent-shogun.git C:\tools\multi-agent-shogun

# 2. Run installer (right-click → Run as Administrator)
#    → install.bat handles WSL2 + Ubuntu setup automatically

# 3. In Ubuntu terminal:
cd /mnt/c/tools/multi-agent-shogun
./first_setup.sh          # One-time: installs tmux, Node.js, Claude Code CLI
./shutsujin_departure.sh  # Deploy your army
```

### Linux / macOS

```bash
# 1. Clone
git clone https://github.com/yohey-w/multi-agent-shogun.git ~/multi-agent-shogun
cd ~/multi-agent-shogun && chmod +x *.sh

# 2. Setup + Deploy
./first_setup.sh          # One-time: installs dependencies
./shutsujin_departure.sh  # Deploy your army
```

### Daily startup

```bash
cd /path/to/multi-agent-shogun
./shutsujin_departure.sh
tmux attach-session -t shogun      # Connect and give orders
# tmux attach-session -t multiagent  # Watch Ashigaru work
# tmux attach-session -t ooku        # Watch Heyago + Ohariko
```

<details>
<summary><b>Convenient aliases</b> (added by first_setup.sh)</summary>

```bash
alias csst='cd /mnt/c/tools/multi-agent-shogun && ./shutsujin_departure.sh'
alias css='tmux attach-session -t shogun'
alias csm='tmux attach-session -t multiagent'
alias cso='tmux attach-session -t ooku'
```

</details>

### 📱 Mobile Access (Command from anywhere)

Control your AI army from your phone — bed, café, or bathroom.

**Requirements:**
- [Tailscale](https://tailscale.com/) (free) — creates a secure tunnel to your WSL
- [Termux](https://termux.dev/) (free) — terminal app for Android
- SSH — already installed

**Setup:**

1. Install Tailscale on both WSL and your phone
2. In WSL (auth key method — browser not needed):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscaled &
   sudo tailscale up --authkey tskey-auth-XXXXXXXXXXXX
   sudo service ssh start
   ```
3. In Termux on your phone:
   ```sh
   pkg update && pkg install openssh
   ssh youruser@your-tailscale-ip
   css    # Connect to Shogun
   ```
4. Open a new Termux window (+ button) for workers:
   ```sh
   ssh youruser@your-tailscale-ip
   csm    # See all 9 panes
   ```

**Disconnect:** Just swipe the Termux window closed. tmux sessions survive — agents keep working.

**Voice input:** Use your phone's voice keyboard to speak commands. The Shogun understands natural language, so typos from speech-to-text don't matter.

---

## How It Works

### 1. Give an order

```
You: "Research the top 5 MCP servers and create a comparison table"
```

### 2. Shogun delegates instantly

The Shogun registers the command in Botsunichiroku DB and dispatches to the appropriate Karo. Control returns to you immediately — no waiting.

### 3. Karo distributes

The Karo (Roju for external projects, Midaidokoro for internal system) breaks the task into subtasks registered in the DB:

| Worker | Assignment |
|--------|-----------|
| Ashigaru 1 | Research Notion MCP |
| Ashigaru 2 | Research GitHub MCP |
| Ashigaru 3 | Research Playwright MCP |
| Ashigaru 4 | Research Memory MCP |
| Ashigaru 5 | Research Sequential Thinking MCP |

### 4. Parallel execution

All 5 Ashigaru research simultaneously. You can watch them work in real time:

<p align="center">
  <img src="assets/screenshots/tmux_multiagent_working.png" alt="Ashigaru agents working in parallel" width="700">
</p>

### 5. Results in dashboard

Open `dashboard.md` to see aggregated results, skill candidates, and blockers — all maintained by the Karo.

---

## Real-World Use Cases

This system manages **all white-collar tasks**, not just code. Projects can live anywhere on your filesystem.

```yaml
# config/projects.yaml
projects:
  - id: client_x
    name: "Client X Consulting"
    path: "/mnt/c/Consulting/client_x"
    status: active
```

**Research sprints** — 8 agents research different topics in parallel, results compiled in minutes.

**Multi-project management** — Switch between client projects without losing context. Memory MCP preserves preferences across sessions.

**Document generation** — Technical writing, test case reviews, comparison tables — distributed across agents and merged.

---

## Configuration

### Language

```yaml
# config/settings.yaml
language: ja   # Samurai Japanese only
language: en   # Samurai Japanese + English translation
```

### Model assignment

| Agent | Default Model | Thinking |
|-------|--------------|----------|
| Shogun | Opus | Disabled (delegation doesn't need deep reasoning) |
| Karo | Opus | Enabled |
| Ashigaru 1–4 | Sonnet | Enabled |
| Ashigaru 5–8 | Opus | Enabled |

### MCP servers

```bash
# Memory (auto-configured by first_setup.sh)
claude mcp add memory -e MEMORY_FILE_PATH="$PWD/memory/shogun_memory.jsonl" -- npx -y @modelcontextprotocol/server-memory

# Notion
claude mcp add notion -e NOTION_TOKEN=your_token -- npx -y @notionhq/notion-mcp-server

# GitHub
claude mcp add github -e GITHUB_PERSONAL_ACCESS_TOKEN=your_pat -- npx -y @modelcontextprotocol/server-github

# Playwright (browser automation)
claude mcp add playwright -- npx @playwright/mcp@latest
```

### Screenshot integration

```yaml
# config/settings.yaml
screenshot:
  path: "/mnt/c/Users/YourName/Pictures/Screenshots"
```

Tell the Shogun "check the latest screenshot" and it reads your screen captures for visual context. (`Win+Shift+S` on Windows.)

---

## File Structure

```
multi-agent-shogun/
├── install.bat                # Windows first-time setup
├── first_setup.sh             # Linux/Mac first-time setup
├── shutsujin_departure.sh     # Daily deployment script
│
├── instructions/              # Agent behavior definitions
│   ├── shogun.md
│   ├── karo.md               # Shared by Roju and Midaidokoro
│   ├── ashigaru.md            # Shared by Ashigaru and Heyago
│   └── ohariko.md             # Auditor instructions
│
├── config/
│   ├── settings.yaml          # Language, model, screenshot settings
│   └── projects.yaml          # Project registry
│
├── data/
│   └── botsunichiroku.db      # Command/subtask/report database (SQLite)
│
├── scripts/
│   ├── botsunichiroku.py      # DB CLI (cmd/subtask/report operations)
│   ├── init_db.py             # Database initialization
│   └── generate_dashboard.py  # Auto-generate dashboard.md
│
├── queue/                     # Legacy (archived). DB is now source of truth
│   └── shogun_to_karo.yaml    # Shogun → Karo dispatch queue
│
├── memory/                    # Memory MCP persistent storage
├── dashboard.md               # Human-readable status board
└── CLAUDE.md                  # System instructions (auto-loaded)
```

---

## Troubleshooting

<details>
<summary><b>Agents asking for permissions?</b></summary>

Agents should start with `--dangerously-skip-permissions`. This is handled automatically by `shutsujin_departure.sh`.

</details>

<details>
<summary><b>MCP tools not loading?</b></summary>

MCP tools are lazy-loaded. Search first, then use:
```
ToolSearch("select:mcp__memory__read_graph")
mcp__memory__read_graph()
```

</details>

<details>
<summary><b>Agent crashed?</b></summary>

Don't use `css`/`csm` aliases inside an existing tmux session (causes nesting). Instead:

```bash
# From the crashed pane:
claude --model opus --dangerously-skip-permissions

# Or from another pane:
tmux respawn-pane -t shogun:0.0 -k 'claude --model opus --dangerously-skip-permissions'
```

</details>

<details>
<summary><b>Workers stuck?</b></summary>

```bash
tmux attach-session -t multiagent
# Ctrl+B then 0-8 to switch panes
```

</details>

<details>
<summary><b>Ooku session issues?</b></summary>

The ooku session hosts Midaidokoro, Heyago 1-3, and Ohariko:
```bash
tmux attach-session -t ooku
# Pane 0: Midaidokoro (manager)
# Pane 1-3: Heyago (researchers)
# Pane 4: Ohariko (auditor)
```

</details>

---

## tmux Quick Reference

| Command | Description |
|---------|-------------|
| `tmux attach -t shogun` | Connect to the Shogun |
| `tmux attach -t multiagent` | Connect to workers |
| `tmux attach -t ooku` | Connect to Heyago + Ohariko |
| `Ctrl+B` then `0`–`8` | Switch panes |
| `Ctrl+B` then `d` | Detach (agents keep running) |

Mouse support is enabled by default (`set -g mouse on` in `~/.tmux.conf`, configured by `first_setup.sh`). Scroll, click to focus, drag to resize.

---

## Contributing

Issues and pull requests are welcome.

- **Bug reports**: Open an issue with reproduction steps
- **Feature ideas**: Open a discussion first
- **Skills**: Skills are personal by design and not included in this repo

## Credits

Based on [Claude-Code-Communication](https://github.com/Akira-Papa/Claude-Code-Communication) by Akira-Papa.

## License

[MIT](LICENSE)

---

<div align="center">

**One command. Eleven agents. Zero coordination cost.**

⭐ Star this repo if you find it useful — it helps others discover it.

</div>
