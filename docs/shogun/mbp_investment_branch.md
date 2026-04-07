# MBP投資支店 偵察+設計+実行計画

> **軍師分析書** | 2026-03-30 | cmd_466 / subtask_1034 | project: systrade
> **North Star**: 7600x.local単一障害点を解消。MBP支店で投資パイプラインが自律稼働する構成。

---

## §1 MBP現状構成棚卸し（SSH実地偵察結果）

### 1a. ハードウェア

| 項目 | 値 |
|------|-----|
| マシン | Apple MacBook Pro |
| SoC | Apple M4 Pro |
| RAM | 48 GB |
| OS | macOS 26.3.1 (Tahoe) |
| ホスト名 | mbp.local |
| LAN IP | 192.168.15.x (mDNS: 7600x.local→192.168.15.14 とLAN疎通OK, 0.37ms) |
| WireGuard | **未起動**（wgコマンド応答なし、utun0はIPv6 link-localのみ） |

### 1b. Crucix（OSINT trade ideas生成）

| 項目 | 値 |
|------|-----|
| パス | `/Users/yasu/Crucix/` |
| ランタイム | **Node.js**（`node dashboard/inject.mjs`） |
| cron | `*/30 * * * *` → `cron_ideas.sh` |
| 出力先 | `~/Crucix/runs/ideas_log/{TS}.json` |
| ソース数 | 28ソース（Crucix内蔵） |
| 動作 | sweep → idea生成 → jarvis.htmlからideas抽出 → JSON保存 |

### 1c. ollama（ローカルLLM）

| モデル | サイズ | 用途 |
|--------|--------|------|
| gpt-oss-fin-thinking:latest | 22.3GB (20.9B Q8_0) | 金融推論特化 |
| gpt-oss:20b | 13.8GB | 汎用 |

**⚠️ Memory MCPの情報は古い**: qwen3:8b / qwen3.5:35b-a3bは既に置換済み。

### 1d. Python環境

| 項目 | 値 |
|------|-----|
| バージョン | **3.9.6（システム標準）** |
| パス | `/usr/bin/python3` |
| pip3パッケージ | **26個のみ**（ほぼ空） |
| venv | なし |

**⚠️ systrade要件はPython 3.11+。homebrewでpython@3.12インストール+venv構築が必要。**

### 1e. ディレクトリ構成

| パス | 内容 |
|------|------|
| `~/Crucix/` | Crucix本体（Node.js） |
| `~/multi-agent-shogun/` | shogunリポ（clone済み） |
| `~/systrade/` | **存在しない**（未clone） |
| `~/agent-swarm/` | **存在しない** |

### 1f. 環境変数

| ファイル | 状態 |
|----------|------|
| `~/.config/env/edinet.env` | **存在しない** |
| EDINET_API_KEY | **未設定** |

---

## §2 systrade既存スクリプト依存マップ

### 2a. pyproject.toml依存一覧

```toml
dependencies = [
    "yfinance>=0.2",
    "wbgapi>=1.0",
    "scikit-learn>=1.4",
    "hmmlearn>=0.3",
    "pandas>=2.0",
    "numpy>=1.26",
    "matplotlib>=3.8",
    "requests>=2.31",
    "edinet-tools==0.4.3",
]
```

### 2b. スクリプト依存マトリクス

| スクリプト | stdlib | pip依存 | 環境変数 | ファイル依存 | 外部API |
|-----------|:------:|---------|---------|-------------|---------|
| **daily_risk.py** | pathlib, datetime | yfinance, pandas, numpy, matplotlib, requests | なし | data/processed/cache/ | FRED CSV, yfinance |
| **edinetdb_drill.py** | json, os | requests | EDINET_DB_TOKEN | なし | EDINET DB API (cabocia) |
| **edinet_pipeline.py** | json, os, sqlite3, xml, zipfile | edinet-tools(==0.4.3) | EDINET_API_KEY | data/edinet_holdings.db, data/dreams.jsonl | EDINET API v2 |
| **risk_alert.py** | - | (daily_risk wrapper) | なし | - | - |
| **run_pipeline.py** | - | (未確認) | - | - | - |

### 2c. MBP移植に必要なもの

```
1. Python 3.12 (homebrew)
2. venv + pip install -e .  (pyproject.tomlの全依存)
3. git clone yasunorioi/systrade (private)
4. ~/.config/env/edinet.env  (EDINET_API_KEY)
5. EDINET_DB_TOKEN (edinetdb_drill.py用、現在7600x.localにある)
6. data/ ディレクトリ (初回実行で自動生成)
```

---

## §3 baku.py投資リサーチ機能の切り出し範囲

### 3a. baku.py全体構造（~1620行、45関数）

#### 投資リサーチ層（MBPに移植候補）

| 関数 | 行数 | 概要 | MBP移植 |
|------|------|------|:-------:|
| `_fetch_fred_latest()` | 727-747 | FRED経済データ取得 | ✅ |
| `_fetch_wb_indicator()` | 749-768 | 世界銀行データ取得 | ✅ |
| `finance_deepdive()` | 770-854 | 金融深掘り分析 | ✅ |
| `format_finance_report()` | 856-890 | レポート整形 | ✅ |
| `post_finance_report()` | 1381-1406 | finance板投稿 | ✅（HTTP化） |
| `post_risk_alert()` | 1409-1413 | リスクアラート投稿 | ✅（HTTP化） |

#### shogun内部層（7600xに残す）

| 関数 | 概要 | 残す理由 |
|------|------|---------|
| `get_recent_keywords()` | 没日録DB参照 | DB権限は7600xのみ |
| `get_recent_cmd_summary()` | cmd履歴参照 | 没日録DB依存 |
| `search_kousatsu()` | 高札検索 | localhost:8080依存 |
| `generate_dream_queries()` | 夢クエリ生成 | TONO_INTERESTS + 没日録 |
| `interpret_dream()` / `sonnet_selection()` | 夢解釈・選別 | Claude API (shogun負担) |
| `chew_loop()` / `should_chew()` | 噛み砕きループ | Claude API + 高札 |
| `daemon_loop()` | デーモン本体 | 7600xでcron稼働中 |

#### 共有層（両方で使う）

| 関数 | 概要 | 方式 |
|------|------|------|
| `search_ddg()` | DuckDuckGo検索 | そのまま（外部API） |
| `search_rss_sources()` / `_fetch_rss_source()` | RSS巡回 | そのまま（外部API） |
| `save_dream()` / `load_recent_dreams()` | dreams.jsonl読み書き | パス差し替え |

### 3b. 切り出し方針: **分離しない。systradeに投資リサーチスクリプトを新規作成**

**理由**:
1. baku.pyは7600x.localで安定稼働中。手を入れるリスクが高い
2. 投資リサーチ関数はbaku.py内で他関数と密結合（dream → finance_deepdive → post）
3. MBPの投資パイプラインは**systrade側に新規スクリプト**を作る方が清潔
4. baku.pyの投資関数を「参考実装」として、systrade/scripts/に**投資リサーチ特化スクリプト**を新規作成

→ **systrade/scripts/investment_report.py**（新規）:
- daily_risk.py結果の集約
- edinet_pipeline.py急変検出結果の統合
- Crucix ideas_logの集約
- finance板へのHTTP POST投稿
- ollama(gpt-oss-fin-thinking)での分析

### 3c. dreams.jsonlの扱い

| 項目 | 値 |
|------|-----|
| パス | `/home/yasu/multi-agent-shogun/data/dreams.jsonl` |
| 書き手 | baku.py, edinet_pipeline.py |
| 読み手 | baku.py（噛み砕きループ） |

MBP版edinet_pipeline.pyでは、dreams.jsonlに書く代わりに:
1. ローカルdreams.jsonlに書く（MBP内完結）
2. OR finance板に投稿（7600x.local経由で全エージェント可視化）

→ **推奨: finance板投稿**。dreams.jsonlはshogun依存が強すぎる。

---

## §4 agent-swarm通信設計

### 4a. agent-swarm API仕様

| 項目 | 値 |
|------|-----|
| サーバー | `python3 server/dat_server.py` (7600x.local) |
| ポート | **8824** |
| バインド | **127.0.0.1（loopbackのみ）** ⚠️ |
| プロトコル | 2ch互換 HTTP (JDim対応) |
| DB | `/home/yasu/agent-swarm/data/swarm.db` (SQLite) |

**書き込みエンドポイント**:
```
POST /test/bbs.cgi
Content-Type: application/x-www-form-urlencoded

bbs=finance&key=<thread_id>&FROM=baku&MESSAGE=<本文>
新スレッド: bbs=finance&subject=<タイトル>&FROM=baku&MESSAGE=<本文>
```

**認証**: FROM欄のエージェント名でtrip認証。`resolve_agent(from_field)`で名前→agent_id解決。
**finance板writers**: `["baku", "gunshi", "shogun", "roju"]`

### 4b. リモートアクセス問題と解決策

**現状**: dat_server.pyが`127.0.0.1`にバインド → MBPから直接HTTP POST不可。

| 案 | 方式 | 利点 | 欠点 | 推奨 |
|----|------|------|------|:----:|
| **A: SSHトンネル** | `ssh -L 8824:127.0.0.1:8824 7600x.local` | 変更ゼロ、暗号化 | SSH維持が必要 | ★★★ |
| B: バインド変更 | `0.0.0.0:8824` | 簡単 | セキュリティ低下（LAN全公開） | ★★ |
| C: nginx proxy | `7600x.local:8825` → `127.0.0.1:8824` | 柔軟 | nginx追加依存 | ★ |

**推奨: 案A（SSHトンネル）+案B(フォールバック)**

実装:
```bash
# MBP側: autosshで永続SSHトンネル（launchdで自動起動）
autossh -M 0 -N -L 8824:127.0.0.1:8824 yasu@7600x.local
# → MBP上で curl http://localhost:8824/test/bbs.cgi でPOST可能
```

フォールバック（7600x.local不通時）:
```bash
# MBP側: ローカルファイルに蓄積
echo '{"ts":"...","board":"finance","body":"..."}' >> ~/systrade/data/pending_posts.jsonl
# → 7600x.local復帰後、一括POST
```

### 4c. MBP支店長エージェント設計

| 項目 | 値 |
|------|-----|
| agent_id | **mbp_branch**（新規追加） |
| 表示名 | 「MBP支店長」 |
| tripコード | ◆MBP1 |
| 書き込み権限 | finance板 |

→ `config/swarm.yaml`に追加:
```yaml
  mbp_branch:
    name: "MBP支店長"
    trip: "◆MBP1"
    pane: null  # リモートエージェント（tmuxペインなし）
```

→ `boards.finance.writers`に`"mbp_branch"`追加。

### 4d. 投稿スクリプト（MBP側）

```python
# systrade/scripts/swarm_post.py — agent-swarm投稿ヘルパー
import urllib.request, urllib.parse, json
from pathlib import Path

SWARM_URL = "http://localhost:8824"  # SSHトンネル経由
PENDING_FILE = Path("~/systrade/data/pending_posts.jsonl").expanduser()

def post_to_finance(thread_id: str, body: str, agent: str = "mbp_branch") -> bool:
    """agent-swarm finance板に投稿。失敗時はpending_posts.jsonlに蓄積。"""
    data = urllib.parse.urlencode({
        "bbs": "finance", "key": thread_id,
        "FROM": agent, "MESSAGE": body
    }).encode()
    req = urllib.request.Request(f"{SWARM_URL}/test/bbs.cgi", data=data)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        # フォールバック: ローカル蓄積
        with open(PENDING_FILE, "a") as f:
            f.write(json.dumps({"thread_id": thread_id, "body": body}) + "\n")
        return False
```

---

## §5 7600x.local依存ゼロ検証チェックリスト

### 5a. MBP単体で回るもの ✅

| パイプライン | 依存先 | MBP単体 | 備考 |
|-------------|--------|:-------:|------|
| **Crucix** | 外部28ソースAPI, Node.js, ollama | ✅ | 既に30分cron稼働中 |
| **daily_risk.py** | FRED CSV, yfinance API | ✅ | 外部API直叩き、7600x依存なし |
| **edinet_pipeline.py** | 金融庁EDINET API v2 | ✅ | 外部API直叩き、7600x依存なし |
| **edinetdb_drill.py** | EDINET DB API (cabocia.com) | ✅ | 外部API直叩き、7600x依存なし |
| **ollama推論** | ローカルモデル | ✅ | gpt-oss-fin-thinking 22GB |
| **investment_report.py** | 上記スクリプト群の出力 | ✅ | ローカル集約 |

### 5b. 7600x.local依存のもの ⚠️

| 機能 | 依存 | 不通時の影響 | フォールバック |
|------|------|-------------|---------------|
| **finance板投稿** | agent-swarm (7600x:8824) | レポートが共有されない | pending_posts.jsonlに蓄積→復帰後同期 |
| **dreams.jsonl注入** | /home/yasu/multi-agent-shogun/data/ | 獏が夢を噛まない | finance板投稿で代替 |
| **没日録DB参照** | botsunichiroku.db (7600x) | 過去cmd/subtask参照不可 | MBPでは不要（投資系のみ） |
| **高札検索** | localhost:8080 (7600x) | 過去分析の検索不可 | MBPでは不要 |

### 5c. 非7600x依存の確認

| 依存 | 状態 | 対策 |
|------|------|------|
| DNS | MBP自身のDNS（ISP or Starlink） | 問題なし |
| NTP | macOS自動（time.apple.com） | 問題なし |
| EDINET API | disclosure2dl.edinet-fsa.go.jp | 問題なし |
| FRED | fred.stlouisfed.org | 問題なし |
| yfinance | Yahoo Finance | 問題なし |
| ollama | localhost:11434 | MBPローカル |

### 5d. graceful degradation設計

```
7600x.local 正常時:
  Crucix → ideas_log → investment_report.py → finance板投稿
  edinet_pipeline.py → 急変検出 → finance板投稿
  daily_risk.py → リスク判定 → finance板投稿

7600x.local 障害時:
  Crucix → ideas_log → investment_report.py → pending_posts.jsonl（ローカル蓄積）
  edinet_pipeline.py → 急変検出 → pending_posts.jsonl
  daily_risk.py → リスク判定 → pending_posts.jsonl
  ※投資パイプライン自体は完全に回り続ける。共有のみ遅延。

7600x.local 復帰時:
  scripts/flush_pending.sh → pending_posts.jsonlを一括POST → 削除
```

---

## §6 MBP投資支店 目標構成+実行計画

### 6a. 目標構成図

```
┌──────────────────────────────────────────────────────┐
│  MBP投資支店 (mbp.local / M4 Pro 48GB)                │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Crucix       │  │ systrade/    │  │ ollama       │ │
│  │ (Node.js)    │  │ scripts/     │  │ gpt-oss-fin  │ │
│  │ 30min cron   │  │              │  │ :11434       │ │
│  └──────┬──────┘  │ daily_risk   │  └──────┬──────┘ │
│         │          │ edinet_pipe  │         │        │
│         │          │ edinetdb_drl │         │        │
│         │          │ investment_  │◄────────┘        │
│         │          │  report.py   │                   │
│         │          └──────┬──────┘                   │
│         │                 │                           │
│         └────────┬────────┘                           │
│                  │                                    │
│         ┌────────▼────────┐                           │
│         │ swarm_post.py    │                           │
│         │ (HTTP POST)      │                           │
│         └────────┬────────┘                           │
│                  │ SSHトンネル                          │
│                  │ (autossh)                           │
└──────────────────┼───────────────────────────────────┘
                   │
                   ▼ LAN (192.168.15.x)
┌──────────────────┼───────────────────────────────────┐
│  7600x.local 本店                                     │
│                  │                                    │
│         ┌────────▼────────┐                           │
│         │ agent-swarm      │                           │
│         │ :8824            │                           │
│         │ finance板        │                           │
│         └────────┬────────┘                           │
│                  │                                    │
│         ┌────────▼────────┐  ┌──────────────┐        │
│         │ 獏 (baku.py)     │  │ 没日録DB      │        │
│         │ 噛み砕きループ    │  │ 高札          │        │
│         └─────────────────┘  └──────────────┘        │
└──────────────────────────────────────────────────────┘
```

### 6b. cron設定一式（MBP）

```crontab
# === 既存 ===
*/30 * * * * /Users/yasu/Crucix/scripts/cron_ideas.sh

# === 追加（systrade） ===
# EDINET大量保有報告書 日次取得（平日18時）
0 18 * * 1-5 cd ~/systrade && ~/.venv/systrade/bin/python scripts/edinet_pipeline.py --date $(date +\%Y-\%m-\%d) >> ~/systrade/logs/edinet.log 2>&1

# EDINET急変検出（平日18:30）
30 18 * * 1-5 cd ~/systrade && ~/.venv/systrade/bin/python scripts/edinet_pipeline.py --detect >> ~/systrade/logs/edinet.log 2>&1

# daily_risk（毎日8時）
0 8 * * * cd ~/systrade && ~/.venv/systrade/bin/python scripts/daily_risk.py >> ~/systrade/logs/daily_risk.log 2>&1

# 投資日報（毎日20時: Crucix + EDINET + daily_risk集約→finance板投稿）
0 20 * * * cd ~/systrade && ~/.venv/systrade/bin/python scripts/investment_report.py >> ~/systrade/logs/report.log 2>&1

# 未送信レポート一括投稿（毎時、7600x.local復帰時に自動flush）
0 * * * * cd ~/systrade && ~/.venv/systrade/bin/python scripts/flush_pending.py >> ~/systrade/logs/flush.log 2>&1
```

### 6c. 殿向けMBPセットアップ手順書

以下のコマンドを**MBPのターミナルで**順次実行:

```bash
# === Step 1: Python 3.12 インストール ===
brew install python@3.12

# === Step 2: systradeリポジトリ clone ===
cd ~
git clone git@github.com:yasunorioi/systrade.git
cd systrade

# === Step 3: venv構築+依存インストール ===
/opt/homebrew/bin/python3.12 -m venv ~/.venv/systrade
~/.venv/systrade/bin/pip install -e ".[dev]"

# === Step 4: EDINET APIキー設定 ===
mkdir -p ~/.config/env
echo 'EDINET_API_KEY=ここにAPIキー' > ~/.config/env/edinet.env

# === Step 5: EDINET DB TOKEN設定（7600x.localから取得） ===
# 7600x.localの ~/.config/env/ からEDINET_DB_TOKENを確認してコピー
echo 'EDINET_DB_TOKEN=ここにトークン' >> ~/.config/env/edinet.env

# === Step 6: ログディレクトリ作成 ===
mkdir -p ~/systrade/logs

# === Step 7: autossh インストール（agent-swarm SSHトンネル用） ===
brew install autossh

# === Step 8: 動作確認 ===
~/.venv/systrade/bin/python scripts/daily_risk.py         # マクロリスク
~/.venv/systrade/bin/python scripts/edinet_pipeline.py --test  # EDINET API接続

# === Step 9: cron設定 ===
crontab -e
# → §6bのcron設定を追記

# === Step 10: SSHトンネル設定（launchd） ===
# plistファイルは足軽が作成 → 殿がcpでインストール
```

### 6d. 新規作成ファイル一覧

| ファイル | リポ | 用途 | 行数見積 |
|---------|------|------|---------|
| `scripts/investment_report.py` | systrade | 投資日報集約+finance板投稿 | ~200行 |
| `scripts/swarm_post.py` | systrade | agent-swarm HTTP投稿ヘルパー | ~60行 |
| `scripts/flush_pending.py` | systrade | 未送信レポート一括投稿 | ~40行 |
| `config/mbp_crontab.txt` | systrade | MBP cron設定テンプレート | ~15行 |
| `config/com.systrade.tunnel.plist` | systrade | launchd SSHトンネル設定 | ~25行 |

### 6e. 既存修正ファイル

| ファイル | リポ | 変更内容 |
|---------|------|---------|
| `config/swarm.yaml` | agent-swarm | mbp_branchエージェント追加 |
| `scripts/edinet_pipeline.py` | systrade | dreams.jsonl→swarm_post.py経由に変更(MBP時) |

---

## §7 トレードオフ比較

### 7a. agent-swarm通信方式

| 案 | 方式 | セキュリティ | 可用性 | 変更コスト | 推奨 |
|----|------|:----------:|:------:|:---------:|:----:|
| **A: SSHトンネル** | autossh -L 8824 | ◎ 暗号化 | ○ SSH依存 | 低（サーバー変更なし） | **★★★** |
| B: 0.0.0.0バインド | dat_server.py修正 | △ LAN全公開 | ◎ 直接 | 低（1行変更） | ★★ |
| C: WireGuard復活 | wg-quick up | ◎ | △ 設定不明 | 中 | ★ |
| D: SSH exec | ssh 7600x cli.py reply add | ◎ | ○ | 低 | ★★★ |

**案Dも有力**: MBPからの投稿頻度は日に数回程度。SSHコマンド直叩きが最もシンプル:
```bash
ssh yasu@7600x.local "cd /home/yasu/agent-swarm && python3 server/cli.py reply add finance_daily_20260330 --board finance --agent mbp_branch --body '本文'"
```
→ **SSHトンネル不要、autossh不要、launchd不要。`ssh + cli.py`で完結。**

**最終推奨: 案D（SSH exec）をメイン、案A（SSHトンネル）は高頻度化した場合のアップグレードパス。**

### 7b. baku.py切り出し方式

| 案 | 方式 | リスク | 再利用性 | 推奨 |
|----|------|--------|---------|:----:|
| A: baku.py改修 | 投資関数を外部モジュール化 | 高（安定稼働中を改修） | ◎ | ★ |
| **B: systrade新規** | investment_report.py新規作成 | **低** | ○ | **★★★** |
| C: baku.pyコピー | 投資関数のみ抜き出し | 中 | △（デッドコピー） | ★★ |

### 7c. Python環境

| 案 | 方式 | メンテ性 | 推奨 |
|----|------|---------|:----:|
| **A: homebrew + venv** | python@3.12 + ~/.venv/systrade | ◎ | **★★★** |
| B: pyenv + venv | pyenv install 3.12 | ○ | ★★ |
| C: conda | miniconda | △（重い） | ★ |

---

## §8 リスク・見落とし分析

### 見落としの可能性

1. **MBP スリープ問題**: MacBookは蓋を閉じるとスリープ → cronが止まる。対策: `caffeinate`でスリープ抑制 or Power Nap設定 or launchdでwakeup指定。**要確認・要対策。**

2. **SSH鍵認証**: MBP→7600x.localのSSH鍵認証がパスフレーズ付きの場合、cron内のsshが対話的に聞いてきて詰まる。→ パスフレーズなし鍵 or ssh-agent + keychain。

3. **Crucix ideas_log肥大化**: 30分×24時間×365日 = 17,520ファイル/年。JSON蓄積の定期ローテーションが必要。

4. **edinet-tools macOS対応**: Pure Pythonなので問題ないはずだが、M4 Proでの動作実績は未確認。初回テストで検証。

5. **EDINET_DB_TOKEN**: edinetdb_drill.pyのCabocia API認証トークン。Google OAuth経由。MBPでの再認証が必要かもしれない。

6. **ollama連携**: investment_report.pyでgpt-oss-fin-thinkingを呼ぶ場合、ollama APIのレスポンスタイムが長い（20.9B Q8_0）。cron実行のtimeoutに注意。

---

## §9 運用開始後チェックリスト（殿向け）

> **更新**: 2026-03-30 (subtask_1038 / Wave 4/4 完了)
>
> **殿裁定**:
> - スリープ対策: 実施済み（caffeinate plist不要）
> - WireGuard: 未設定（当面 LAN mDNS + SSH exec 運用。外出先リモートは後日）

### 9a. 初回セットアップ

- [ ] **MBP で `bash ~/systrade/scripts/mbp_setup.sh` 実行**
  - Python 3.12 / venv / git clone / autossh が自動インストールされる
- [ ] **APIキー記入**: `nano ~/.config/env/edinet.env`
  - `EDINET_API_KEY=edb_xxxxx`（7600x.local の同ファイルから転記）
  - `EDINET_DB_TOKEN=xxxxx`（edinetdb_drill.py 用・任意）
- [ ] **SSH鍵設定** (7600x.local への BatchMode ssh が通ること)
  ```bash
  ssh-keygen -t ed25519 -f ~/.ssh/id_7600x -N ''
  ssh-copy-id -i ~/.ssh/id_7600x.pub yasu@7600x.local
  ssh -o BatchMode=yes yasu@7600x.local echo OK
  ```

### 9b. 動作確認（crontab 設定前に必ずテスト）

- [ ] **daily_risk.py 動作確認**
  ```bash
  cd ~/systrade
  ~/.venv/systrade/bin/python scripts/daily_risk.py --no-chart 2>&1 | tail -20
  # → Overall Risk Score: X.XX [CAUTION/SAFE/DANGER] が表示されること
  ```
- [ ] **EDINET API 接続テスト**
  ```bash
  ~/.venv/systrade/bin/python scripts/edinet_pipeline.py --test
  # → [TEST 1] DB初期化 OK / [TEST 2] 設定ファイル読み込み OK / [TEST 3] EDINET API OK
  ```
- [ ] **agent-swarm 投稿テスト**
  ```bash
  ~/.venv/systrade/bin/python scripts/swarm_post.py --test
  # → [TEST] OK — agent-swarm boards: finance ... が表示されること
  # 失敗時: SSH設定を確認 (BatchMode鍵認証)
  ```
- [ ] **投資日報 dry-run 確認**
  ```bash
  ~/.venv/systrade/bin/python scripts/investment_report.py --dry-run --no-ollama
  # → # MBP投資日報 YYYY-MM-DD が stdout に出力されること
  ```

### 9c. crontab 設定

- [ ] **`crontab -e` で `config/mbp_crontab.txt` の内容をペースト**
  ```bash
  cat ~/systrade/config/mbp_crontab.txt
  # 内容を確認してから crontab -e でペースト
  crontab -e
  ```
- [ ] **設定確認**: `crontab -l` で登録内容を確認
- [ ] **ログディレクトリ確認**: `ls ~/systrade/logs/`

### 9d. 翌日確認

- [ ] **ログ確認（翌朝 08:30 頃）**
  ```bash
  # daily_risk 結果
  cat ~/systrade/data/processed/cache/daily_risk_latest.txt | grep "Risk Score"

  # EDINET（平日のみ）
  tail -20 ~/systrade/logs/edinet.log

  # 投資日報
  tail -20 ~/systrade/logs/report.log

  # flush（7600x.local不通時に蓄積されていないか）
  cat ~/systrade/data/pending_posts.jsonl
  ```
- [ ] **finance板確認**: agent-swarm で `investment_daily_{YYYYMMDD}` スレが立っていること

### 9e. 既知の制約・後日対応事項

| 項目 | 状態 | 対応方針 |
|------|------|---------|
| WireGuard | **未設定** | 当面 LAN 内 mDNS 運用。外出先リモートは後日設定 |
| SSH鍵パスフレーズ | パスフレーズなし鍵推奨 | `ssh-keygen -N ''` で作成 |
| Crucix ideas_log 肥大化 | 要監視 | `log_rotate.sh` で管理（週1実行） |
| edinet-tools M4 Pro | 動作実績未確認 | 初回 `--test` で検証 |
| EDINET_DB_TOKEN | 再認証が必要な場合あり | Google OAuth ブラウザ認証 |
| ollama タイムアウト | 20.9B Q8_0 は遅い | timeout=120s 設定済み。`--no-ollama` でスキップ可 |

---

## North Star Alignment

```yaml
north_star_alignment:
  status: aligned
  reason: |
    7600x.local単一障害点の解消。MBP支店で投資パイプライン（Crucix + EDINET + daily_risk）が
    自律稼働する構成を実現。7600x.local障害時もpending_posts.jsonlで蓄積→復帰後同期。
    殿のマクガイバー精神に合致: homebrew + venv + ssh + cron。月額¥0追加。
  risks_to_north_star:
    - "MBPスリープでcronが止まる可能性。caffeinate or launchd wake対策が必要"
    - "SSH鍵認証の対話的パスフレーズ問題。パスフレーズなし鍵 or keychain"
    - "edinet-tools Alpha版のmacOS M4 Pro動作未確認。初回テストで検証"
```

---

*戦場を二つに分け、本陣が落ちても支城が独立して戦い続ける。それが支店の意味だ。—— 軍師*
