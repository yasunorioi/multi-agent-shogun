<div align="center">

# multi-agent-shogun

**Multi-Agent Parallel Development Platform with Claude Code + tmux**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Built_for-Claude_Code-blueviolet)](https://code.claude.com)

*Manage multiple projects in parallel using a hierarchy inspired by Japan's Sengoku-era military structure*

[日本語](README.md)

</div>

---

Run multiple Claude Code instances simultaneously on tmux, orchestrated in a feudal military hierarchy. A single command launches up to 8 AI agents that autonomously decompose tasks, execute, audit, and strategize.

## Hierarchy

```
Lord (Human)
  |
  v  Orders
+--------------+
|   SHOGUN     | <- Supreme Commander
|  (General)   |
+------+-------+
       | via YAML
       v
+--------------+     +--------------+
|    ROJU      |     |   GUNSHI     | <- Strategy & Bloom L4-L6 Analysis
|  (Elder)     |---->|  (Strategist)|
+------+-------+     +--------------+
       |                    ^
       v                    | Audit Results
+---+ +---+ +---+  +--------------+
|Ft | |Ft | |Pa |  |   OHARIKO    | <- Post-hoc Audit & Pre-assignment
|So | |So | |ge |  |  (Seamstress)|
|ld | |ld | |   |  +--------------+
| 1 | | 2 | |   |
+---+ +---+ +---+
```

> **Naming**: Agent names follow Japan's feudal military ranks. *Shogun* = general, *Roju* = senior councilor, *Ashigaru* = foot soldier, *Heyago* = page, *Gunshi* = strategist, *Ohariko* = seamstress (auditor).

| Agent | Count | Role | Default Model |
|-------|-------|------|---------------|
| Shogun | 1 | Supreme commander. Instantly delegates lord's orders | Opus |
| Roju | 1 | Project overseer. Task decomposition, assignment & QA | Opus |
| Ashigaru | 2 | Execution squad. Code implementation & testing | Sonnet |
| Heyago | 1 | Roju's direct research & analysis unit | Opus |
| Gunshi | 1 | Strategy. Bloom L4-L6 analysis & North Star design | Opus |
| Ohariko | 1 | Two-phase audit (spec compliance + rubric scoring) | Sonnet |
| Kousatsu | 1 | FTS5 full-text search API + associative memory engine (Docker) | - |
| Baku | 1 | Dream daemon (hourly web search + daily summary) | - |

---

## Communication Protocol v3

All inter-agent communication is event-driven (polling is forbidden). Async coordination via YAML inbox + tmux send-keys.

| Feature | Description |
|---------|-------------|
| **Request ID Correlation** | Every message gets a truncated 8-char UUID. Instructions and reports are 1:1 linked |
| **Drain-on-Read** | Inbox auto-clears on read |
| **Identity Re-injection** | Agent identity and tasks are auto-injected on context compaction recovery |
| **Kousatsu API Reporting** | Full report body stored in DB; YAML inbox receives only summary + reference ID |

```
Orders:  Shogun -> YAML -> Roju -> YAML -> Ashigaru/Heyago
Analysis: Roju -> YAML -> Gunshi -> YAML -> Roju (Bloom L4-L6 delegation)
Reports:  Ashigaru -> Kousatsu API + YAML -> Roju -> dashboard.md
Audit:    Ohariko -> YAML -> Roju (Phase 1: spec compliance -> Phase 2: rubric)
```

## Four-Layer Memory Model

```
Layer 1: Memory MCP     <- Lord's preferences & rules (persistent across sessions)
Layer 2: Project YAML   <- Project-specific info (config/, context/)
Layer 3a: YAML Comms    <- In-progress tasks (volatile)
Layer 3b: Botsunichiroku DB <- Completed tasks + diary (SQLite, persistent)
Layer 4: Session        <- instructions/*.md (summarized on compaction)
```

Instructions hold minimal rules + index only. Detailed procedures are fetched on-demand from the Kousatsu API (`localhost:8080/docs/`) — a pattern we call "Okitegami-style" (after the fictional detective who forgets everything daily).

## Key Components

### Botsunichiroku (Database)

> *Botsunichiroku* = "Chronicle of the Dead" — a historical record of all completed work.

| Component | Description |
|-----------|-------------|
| `scripts/botsunichiroku.py` | CLI — CRUD for commands, subtasks, reports, agents & diary |
| `scripts/init_db.py` | DB initialization (commands, subtasks, reports, agents, diary_entries, etc.) |
| `data/botsunichiroku.db` | SQLite DB (source of truth; dashboard.md is secondary) |

### Communication & Control

| Component | Description |
|-----------|-------------|
| `scripts/inbox_write.sh` | Inbox write (auto-generates Request ID) |
| `scripts/inbox_read.sh` | Inbox read (Drain-on-Read) |
| `scripts/identity_inject.sh` | Auto-inject agent identity on compaction recovery |
| `scripts/worker_ctl.sh` | Dynamic worker start/stop |
| `scripts/shogun-gc.sh` | Report YAML auto-GC (retains last 10) |

### Kousatsu (Search & Knowledge API)

> *Kousatsu* = public notice board — the system's knowledge retrieval layer.

| Component | Description |
|-----------|-------------|
| `tools/kousatsu/` | Kousatsu API — FTS5 full-text search + doc serving + associative memory engine (Docker) |
| `scripts/build_cooccurrence.py` | Co-occurrence matrix builder (for associative memory) |

### Dream & Exploration

| Component | Description |
|-----------|-------------|
| `scripts/dream.py` | Dream feature — cross-references lord's interest map with recent keywords for web search |
| `scripts/baku.py` | Baku daemon — runs dream.py hourly, generates daily summary at 7 AM |

> *Baku* = a mythical creature that eats nightmares. Here it "dreams" on behalf of the system while humans sleep.

### Audit & Quality

| Component | Description |
|-----------|-------------|
| `scripts/audit_grading.py` | Ohariko rubric scoring (5 categories x 3 points = 15 max) |
| `scripts/gatekeeper_f006.sh` | Pre-commit hook — prevents accidental GitHub Issue/PR creation |
| `context/ohariko-kenchi.md` | Kenchi audit procedures (K-1 to K-5: existence, description accuracy, dependency integrity) |

### Kenchi (Resource Registry)

> *Kenchi* = land survey — a comprehensive registry of all resources (scripts, configs, APIs, etc.) in the domain.

| Component | Description |
|-----------|-------------|
| `botsunichiroku.py kenchi` | Kenchi CLI — register, search & manage domain resources |

```bash
python3 scripts/botsunichiroku.py kenchi add --path scripts/notify.py --category script --description "External notification sender"
python3 scripts/botsunichiroku.py kenchi list
python3 scripts/botsunichiroku.py kenchi search "notify"
```

### External Notifications

| Component | Description |
|-----------|-------------|
| `scripts/notify.py` | Multi-backend notifications (ntfy/Discord/Slack/MQTT). No external deps, non-blocking |
| `config/notify_auth.env.sample` | Auth template |

Enable with `notify.enable: true` in `config/settings.yaml`. Auto-notifies on command registration and report submission.

### Diary & Matome

> *Matome* = summary/compilation, styled after Japan's iconic 2channel bulletin board format.

| Component | Description |
|-----------|-------------|
| `scripts/diary_matome.py` | 2ch-style HTML matome + 2ch-compatible dat generation (JDim/Jane Style compatible) |
| `data/matome/` | Matome HTML output directory |
| `data/matome/shogun/` | 2ch-compatible board directory (dat/, subject.txt, SETTING.TXT) |

---

## Design Influences

| Project | Patterns Adopted |
|---------|-----------------|
| [memx-core](https://github.com/RNA4219/memx-core) | ADR, auto GC, Gatekeeper, knowledge promotion |
| [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | Request ID correlation, Drain-on-Read, Identity Re-injection |
| [pm-skills](https://github.com/phuryn/pm-skills) | SKILL.md v1 format, ICE scoring |

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| tmux | `sudo apt install tmux` |
| Node.js v20+ | Required for Claude Code CLI |
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| Docker | Required for Kousatsu API |
| Python 3.10+ | Required for Botsunichiroku CLI & Dream feature |
| nginx (optional) | For serving matome HTML |

## Installation

```bash
git clone https://github.com/yasunorioi/multi-agent-shogun.git ~/multi-agent-shogun
cd ~/multi-agent-shogun && chmod +x *.sh
./first_setup.sh
```

On Windows, run `install.bat` as administrator first.

## Launch

```bash
./shutsujin_departure.sh           # Normal launch
./shutsujin_departure.sh -c        # Clean start (reset queues)
./shutsujin_departure.sh -c -d     # Full clean (queues + DB reset)
./shutsujin_departure.sh -k        # Battle mode (all agents use Opus)
./shutsujin_departure.sh -i        # Minimal launch (Shogun + Roju only)
./shutsujin_departure.sh -h        # Help
```

## Connect

```bash
tmux attach-session -t shogun      # Connect to Shogun to issue orders
tmux attach-session -t multiagent  # Monitor Roju + Ashigaru
tmux attach-session -t ooku        # Monitor Gunshi + Ohariko + Kousatsu + Baku
```

Aliases (auto-configured by `first_setup.sh`): `css`=shogun, `csm`=multiagent, `cso`=ooku

## Usage

1. Connect to the Shogun session and issue orders
2. Shogun delegates tasks to Roju (non-blocking)
3. Roju decomposes tasks using "Five Questions", routes via Bloom-based routing to Gunshi/Ashigaru
4. Ashigaru and Heyago execute implementation and research in parallel
5. Ohariko performs two-phase audit (Phase 1: spec compliance -> Phase 2: rubric scoring)
6. Results are aggregated in `dashboard.md` and permanently recorded in the Botsunichiroku DB

### Browse with 2ch Clients

All activity from the Botsunichiroku is generated in 2ch-compatible dat format. Viewable with JDim, Jane Style, Siki, etc.

```bash
python3 scripts/diary_matome.py --full-rebuild   # Generate all threads
python3 scripts/diary_matome.py                   # Today only
```

To serve via nginx:
```bash
sudo ln -s ~/multi-agent-shogun/data/matome/shogun /var/www/html/botsunichiroku
# -> Register http://localhost/botsunichiroku/ as a board in your 2ch browser
```

---

<details>
<summary><b>Troubleshooting</b></summary>

### Agent crashed

```bash
# Launch directly in the pane
claude --model opus --dangerously-skip-permissions

# Force restart from another pane
tmux respawn-pane -t shogun:main -k 'claude --model opus --dangerously-skip-permissions'
```

### Worker stopped

```bash
scripts/worker_ctl.sh status          # Check all worker status
scripts/worker_ctl.sh start ashigaru1 # Start individually
```

### MCP tools not working

MCP tools use deferred loading. Run `ToolSearch` to load them first.

### Kousatsu API not responding

```bash
cd tools/kousatsu && docker compose up -d   # Start Kousatsu
curl -s http://localhost:8080/health        # Health check
```

</details>

---

## Differences from Upstream

This repository is a fork of [yohey-w/multi-agent-shogun](https://github.com/yohey-w/multi-agent-shogun). The following are original extensions:

| Feature | Description |
|---------|-------------|
| **Kousatsu v2 Associative Memory** | FTS5 full-text search + Hopfield co-occurrence matrix for automatic knowledge retrieval |
| **Gunshi (Strategist)** | Dedicated strategy agent with Bloom-based routing for L4-L6 analysis |
| **Ohariko Two-Phase Audit** | Phase 1: spec compliance (early FAIL), Phase 2: 15-point rubric scoring |
| **Dream System** | Serendipity search by crossing lord's interest map with Botsunichiroku keywords |
| **Baku Daemon** | Hourly dreaming + daily summary (system learns while humans sleep) |
| **AI Diary** | Records agent thought processes. Supplements context on compaction recovery |
| **2ch-Compatible dat** | All activity viewable in 2ch browsers (dat + subject.txt) |
| **Botsunichiroku Auto-Enrich** | Auto-caches knowledge in Kousatsu API on command registration |
| **Communication Protocol v3** | Request ID correlation, Drain-on-Read, Kousatsu API report registration |
| **Identity Re-injection** | Auto-inject agent identity and tasks on compaction recovery |
| **Pre-commit Gatekeeper** | Prevents accidental GitHub Issue/PR creation and repo misfires |
| **External Notifications** | Four backends (ntfy/Discord/Slack/MQTT). No external deps, non-blocking fire-and-forget |
| **Kenchi (Resource Registry)** | Domain resource registration & search. Ohariko Kenchi Audit (K-1 to K-5) verifies existence & integrity |
| **Slash Commands** | Custom skills: `/md2pdf` (Japanese PDF), `/audit` (audit), and more |

---

## Credits

Built on [Claude-Code-Communication](https://github.com/Akira-Papa/Claude-Code-Communication) by Akira-Papa.

## License

[MIT](LICENSE)
