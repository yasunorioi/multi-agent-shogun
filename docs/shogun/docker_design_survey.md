# shogunシステムDocker化 設計調査

> **軍師分析書** | 2026-03-27 | cmd_452 / subtask_1006 | project: shogun

---

## §0 分析前提

**優先度中。急ぎではない。** 殿の指示は「当面はallowlist拡充で対処（cmd_448）。Docker化は判断保留」。
本調査は殿が判断するための材料を提供するものであり、即実行の提案ではない。

### Docker化の動機

足軽がパーミッション確認プロンプトで停止する問題の**根本的解決**。
allowlist追加は対症療法であり、Claude Codeのバージョンアップで新たな確認が増えるたびにイタチごっこになる。

### 調査方針

4つの分析軸で評価する:
1. コンテナ構成案（何をどう分割するか）
2. 技術的障壁（何が動かないか）
3. 移行ロードマップ（どう段階的に進めるか）
4. ラズパイ/VPS展開との共通基盤

---

## §1 コンテナ構成案

### 案A: 1コンテナ1エージェント（完全分離）

```yaml
# docker-compose.yml 概念図
services:
  shogun:
    image: shogun-agent
    environment:
      - AGENT_ID=shogun
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - repo:/workspace
      - botsunichiroku-db:/data

  karo:
    image: shogun-agent
    environment:
      - AGENT_ID=karo-roju
    volumes:
      - repo:/workspace
      - botsunichiroku-db:/data

  ashigaru1:
    image: shogun-agent
    environment:
      - AGENT_ID=ashigaru1
    volumes:
      - repo:/workspace  # ← 同一ボリュームで衝突リスク

  ashigaru2: ...
  gunshi: ...
  ohariko: ...

  agent-swarm:
    image: agent-swarm
    ports:
      - "8824:8824"
    volumes:
      - swarm-db:/data

volumes:
  repo:
    driver: local
    driver_opts:
      device: /home/yasu/multi-agent-shogun
      type: none
      o: bind
  botsunichiroku-db:
  swarm-db:
```

| 観点 | 評価 | 詳細 |
|------|:----:|------|
| パーミッション隔離 | ◎ | 各コンテナ内で`--dangerously-skip-permissions`が安全に使える |
| リソース消費 | × | 7コンテナ×Claude Code常駐 = メモリ7GB+ |
| git衝突 | × | bind mount共有で足軽間のファイル競合が残る |
| 通信 | △ | tmux send-keys不可。HTTP通信への全面移行が前提 |
| 運用複雑性 | × | 7サービスの起動順・ヘルスチェック・ログ管理 |

**判定: 現時点では過剰。**

### 案B: セッション単位グループ化（推奨 ★）

```yaml
services:
  # メインセッション（将軍+老中+足軽）
  multiagent:
    image: shogun-agent
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    command: >
      bash -c "
        tmux new-session -d -s multiagent &&
        # tmux内で各ペインを起動（現行と同じ）
        scripts/shutsujin_departure.sh
      "
    volumes:
      - /home/yasu/multi-agent-shogun:/workspace
      - botsunichiroku-db:/workspace/data
    cap_add:
      - SYS_PTRACE  # tmuxのpty操作に必要な場合あり

  # 奥セッション（軍師+お針子+獏）
  ooku:
    image: shogun-agent
    command: >
      bash -c "
        tmux new-session -d -s ooku &&
        scripts/shutsujin_ooku.sh
      "
    volumes:
      - /home/yasu/multi-agent-shogun:/workspace
      - botsunichiroku-db:/workspace/data

  # agent-swarm（独立サービス）
  swarm:
    image: agent-swarm
    ports:
      - "8824:8824"
    volumes:
      - /home/yasu/agent-swarm:/app
```

| 観点 | 評価 | 詳細 |
|------|:----:|------|
| パーミッション | ○ | コンテナ内で`--dangerously-skip-permissions`。外部への影響を遮断 |
| リソース消費 | ○ | 2-3コンテナ。現行tmux構成とほぼ同じ |
| git衝突 | △ | bind mountは残るが、現行と同じリスクレベル |
| 通信 | ○ | **コンテナ内のtmux send-keysは動作する**（同一コンテナ内） |
| 運用複雑性 | ○ | 2-3サービス。manageable |

**判定: 現実的な落としどころ。tmux依存を温存しつつパーミッション問題を解決。**

### 案C: swarm Phase 2完了後のHTTPベース構成（将来案）

```yaml
services:
  # 各エージェントが独立コンテナ（tmux不要）
  karo:
    image: shogun-agent
    environment:
      - AGENT_ID=karo-roju
      - BBS_URL=http://swarm:8824
    command: claude --bare -p "..." --dangerously-skip-permissions

  ashigaru1:
    image: shogun-agent
    environment:
      - AGENT_ID=ashigaru1
      - BBS_URL=http://swarm:8824
    command: claude --bare -p "..." --dangerously-skip-permissions

  swarm:
    image: agent-swarm
    ports:
      - "8824:8824"

  # docker-compose.ymlでnetworkを共有
networks:
  shogun-net:
    driver: bridge
```

| 観点 | 評価 | 詳細 |
|------|:----:|------|
| パーミッション | ◎ | 完全隔離 |
| リソース消費 | △ | 各エージェントが`claude -p`で都度起動→完了→終了 |
| git衝突 | ◎ | worktree per containerで完全分離 |
| 通信 | ◎ | **HTTP (bbs.cgi) でコンテナ間通信。tmux不要** |
| 運用複雑性 | △ | swarm Phase 2が前提。未完成 |

**判定: 理想形だが、swarm Phase 2完了が必須前提。**

### 構成案の比較

| 案 | 実現可能性 | パーミッション解決 | tmux依存 | 前提条件 | 推奨度 |
|----|:---------:|:-----------------:|:--------:|---------|:------:|
| A: 1コンテナ1エージェント | △ | ◎ | 排除 | HTTP通信 | ★ |
| **B: セッション単位** | **◎** | **○** | **温存** | **なし** | **★★★** |
| C: HTTP完全分離 | △ | ◎ | 排除 | swarm Phase 2 | ★★（将来） |

---

## §2 技術的障壁

### 2a. Claude Code CLIのコンテナ内動作

**結論: 動作する。ただし認証方式に制約あり。**

| 項目 | 状態 | 対処 |
|------|:----:|------|
| `claude` CLI インストール | ○ | Dockerfileで`curl -fsSL https://claude.ai/install.sh \| bash` |
| `--bare` モード | ○ | OAuth不要。`ANTHROPIC_API_KEY`環境変数のみで動作 |
| `--dangerously-skip-permissions` | ○ | コンテナ内なら安全（外部への影響を遮断） |
| OAuth認証（対話モード） | × | ブラウザリダイレクトが必要。コンテナ内では困難 |
| `ANTHROPIC_API_KEY` | ○ | 環境変数で注入。Docker secrets推奨 |
| OMC(oh-my-claudecode) | △ | `~/.claude/`のマウントが必要。初期設定の配布が課題 |

**重要な発見**: `--bare`モードは「hooks, skills, plugins, MCP servers, auto memory, CLAUDE.mdをスキップ」する。
つまりshogunの根幹（instructions, hooks, skills）が動かない。

**対処案**:
```bash
# --bare は使わない。通常モードで起動し、設定をマウントで注入
claude --dangerously-skip-permissions \
  --append-system-prompt-file /workspace/instructions/ashigaru.md \
  --mcp-config /workspace/.mcp.json \
  --settings /workspace/.claude/settings.json
```

または`~/.claude/`ディレクトリ全体をボリュームマウント:
```yaml
volumes:
  - /home/yasu/.claude:/root/.claude
  - /home/yasu/multi-agent-shogun:/workspace
```

### 2b. MCP接続のコンテナ跨ぎ

| MCP | 現行の接続方式 | コンテナ内の動作 | 対処 |
|-----|--------------|:---------------:|------|
| **Memory MCP** | localhost stdio | △ | コンテナ内でmemory-mcp-serverを起動 or SSE/HTTP化 |
| **Notion MCP** | localhost stdio | △ | 同上 |
| **Browser Use** | localhost:8765 | × | ポートフォワード or 同一コンテナ内 |
| **GitHub MCP** | `gh` CLI | ○ | `gh auth`の設定をマウント |

**Memory MCPが最大の障壁。** 現行はstdio接続（プロセス内通信）のため、コンテナ跨ぎができない。

対処案:
1. **各コンテナ内で独立Memory MCPを起動**（データの共有が困難）
2. **Memory MCPのHTTP化**（SSEトランスポート対応が必要）
3. **Memory MCPを諦める**（殿の方針「記憶崩壊許容設計。正データは没日録DB+git」と整合）

**推奨: 案3。** Memory MCPは便利キャッシュであり、没日録DBが正データ。Docker化でMemory MCPを捨てても致命的ではない。

### 2c. tmux依存の全洗い出し

13スクリプトがtmuxを使用。依存の深度を3段階で分類:

**Level 1: 身元確認（必須、代替容易）**

| スクリプト | tmux用途 | 代替案 |
|-----------|---------|--------|
| `identity_inject.sh` | `tmux display-message -t "$TMUX_PANE" -p '#{@agent_id}'` | 環境変数 `AGENT_ID` で代替 |
| `policy_checker.py` | agent_id取得 | 同上 |

**Level 2: 通知（必須、swarm Phase 2で解消）**

| スクリプト | tmux用途 | 代替案 |
|-----------|---------|--------|
| `botsu/notify.py` | `tmux send-keys` でメッセージ送信 | bbs.cgi POST + 通知フック |
| `stop_hook_inbox.sh` | `tmux send-keys` で足軽を起動 | bbs.cgi POST の書き込み通知 |
| `worker_ctl.sh` | `tmux send-keys` でClaude Code起動/停止 | `docker exec` or docker API |
| 各instructionsの報告フロー | `tmux send-keys -t multiagent:agents.0` | bbs.cgi POST |

**Level 3: プロセス管理（必須、Docker Compose で代替）**

| スクリプト | tmux用途 | 代替案 |
|-----------|---------|--------|
| `shutsujin_departure.sh` | tmuxセッション+ペイン作成 | `docker-compose up` |
| `worker_ctl.sh` | ペイン内でClaude Code起動 | `docker exec` or docker-compose scale |
| `launch_mbp.sh` | MacBook Pro向け起動 | Dockerfile + docker-compose |

**swarm Phase 2でLevel 2が全解消される。** HTTP通信（bbs.cgi）でtmux send-keysが不要になる。

### 2d. hooks のコンテナ内動作

| hook | 動作 | コンテナ内 | 課題 |
|------|------|:---------:|------|
| `identity_inject.sh` (startup) | tmux @agent_id取得 | △ | AGENT_ID環境変数で代替可 |
| `stop_hook_inbox.sh` (stop) | inbox読み→block/approve判定 | ○ | ファイルパスがマウント内なら動作 |
| `policy_checker.py` (PreToolUse) | F001-F006ポリシーチェック | ○ | AGENT_ID環境変数が必要 |
| `healthcheck.sh` | Docker/DB/YAML構文チェック | ○ | Docker内からDocker確認はDinD問題 |

**核心**: hooks自体はシェルスクリプトなのでコンテナ内で動作する。問題は`TMUX_PANE`環境変数への依存のみ。
`AGENT_ID`環境変数をDockerfileで注入すれば、tmux無しでもidentity_inject.shのフォールバックが動作する。

---

## §3 移行ロードマップ案

### 3段階+判断ポイント

```
Phase 0: Dockerfile + 単体コンテナ試験     ← 即座に可能
  │
  ├── 判断ポイント1: パーミッション問題が解消されるか検証
  │
Phase 1: セッション単位コンテナ化（案B）    ← swarm Phase 0-1 並行
  │
  ├── 判断ポイント2: swarm Phase 2完了を待つか否か
  │
Phase 2: HTTP完全分離（案C）               ← swarm Phase 2 完了後
```

### Phase 0: Dockerfile作成 + 単体試験

**前提条件: なし。即座に着手可能。**

```dockerfile
# Dockerfile.shogun-agent
FROM ubuntu:24.04

# 基本ツール
RUN apt-get update && apt-get install -y \
    curl git tmux python3 python3-pip python3-venv \
    jq yq && \
    rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh | bash

# Python依存（没日録CLI等）
COPY requirements.txt /tmp/
RUN pip3 install --break-system-packages -r /tmp/requirements.txt

# 作業ディレクトリ
WORKDIR /workspace

# AGENT_ID は docker run -e で注入
ENV AGENT_ID=""
ENV ANTHROPIC_API_KEY=""

# tmux無し → identity_inject.sh の --agent-id フォールバック使用
# tmux有り → セッション単位コンテナで通常動作

CMD ["bash"]
```

**試験項目**:
1. コンテナ内で `claude --dangerously-skip-permissions -p "echo hello"` が動作するか
2. `AGENT_ID=ashigaru1 bash scripts/identity_inject.sh --agent-id ashigaru1` が動作するか
3. `python3 scripts/botsunichiroku.py search test` がDB接続できるか
4. `policy_checker.py` がAGENT_ID環境変数で動作するか

### Phase 1: セッション単位コンテナ化

**前提条件: Phase 0の試験合格。**

```yaml
# docker-compose.shogun.yml
version: "3.8"

services:
  multiagent:
    build:
      context: .
      dockerfile: Dockerfile.shogun-agent
    environment:
      - ANTHROPIC_API_KEY
    volumes:
      - .:/workspace
      - ${HOME}/.claude:/root/.claude
    stdin_open: true
    tty: true
    command: >
      bash -c "
        tmux new-session -d -s multiagent -x 200 -y 50 &&
        bash /workspace/scripts/shutsujin_departure.sh &&
        tmux attach -t multiagent
      "

  ooku:
    build:
      context: .
      dockerfile: Dockerfile.shogun-agent
    environment:
      - ANTHROPIC_API_KEY
    volumes:
      - .:/workspace
      - ${HOME}/.claude:/root/.claude
    stdin_open: true
    tty: true

  swarm:
    build:
      context: /home/yasu/agent-swarm
      dockerfile: Dockerfile
    ports:
      - "8824:8824"
    volumes:
      - /home/yasu/agent-swarm:/app

networks:
  default:
    name: shogun-net
```

**この段階でのtmux send-keys**:
- **同一コンテナ内(multiagent内 karo→ashigaru)**: 動作する
- **コンテナ間(multiagent→ooku 軍師/お針子)**: 動作しない → bbs.cgi経由に変更

### Phase 2: swarm Phase 2完了後のHTTP完全分離

swarm Phase 2（YAML inbox廃止+2ch HTTP通信）が完了すれば:
- tmux send-keys → bbs.cgi POST
- YAML inbox → thread_replies テーブル
- 各エージェントは独立コンテナで `claude -p` 実行

この段階でtmux依存がゼロになり、案Cが実現可能になる。

---

## §4 ラズパイ/VPS展開との共通基盤

### 4a. マルチアーキテクチャ

| アーキテクチャ | Claude Code CLI | Python/SQLite | tmux | 判定 |
|---------------|:--------------:|:-------------:|:----:|:----:|
| linux/amd64 (VPS) | ○ | ○ | ○ | ◎ |
| linux/arm64 (ラズパイ4/5) | △ | ○ | ○ | △ |

**Claude Code CLIのARM64対応が不確実。** Node.jsベースのCLIはARM64で動作するはずだが、公式にはmacOS ARM (Apple Silicon)のみがテスト済み。Linux ARM64の動作保証は未確認。

**対処案**:
```bash
# マルチアーキテクチャビルド
docker buildx build --platform linux/amd64,linux/arm64 -t shogun-agent .
```

ただし、ラズパイでClaude Code CLIを動かす実用性は疑問。APIコスト（Claude API呼び出し）はラズパイでも同じ。ラズパイの用途はsystradeのdaily_risk.py（Python + yfinance）のような**LLM不要のパイプライン**が適切。

### 4b. systrade放置運用との統合

```yaml
# docker-compose.systrade.yml（ラズパイ/VPS共通）
services:
  daily-risk:
    image: systrade-runner
    environment:
      - FRED_API_KEY  # 不要（FRED CSVは無料）
    volumes:
      - /home/yasu/systrade:/app
      - systrade-data:/app/data
    command: python3 scripts/daily_risk.py
    # cron相当: Docker + systemd timer or cron on host

  swarm:
    image: agent-swarm
    ports:
      - "8824:8824"
```

**shogun Docker化とsystrade Docker化は分離すべき。** 理由:
1. shogunはClaude Code CLI依存（重い）。systradeはPythonのみ（軽い）
2. shogunのDockerイメージサイズは1GB+。systradeは200MB程度
3. ラズパイではsystradeのみ動かし、shogunはVPSで動かす方が合理的

### 4c. 共通基盤として共有できるもの

| 共有可能 | 内容 |
|---------|------|
| **agent-swarm** | 2ch BBSサーバー。shogunもsystradeもHTTPで接続 |
| **没日録DB** | SQLite WALでread並行可。ただしwrite競合は注意 |
| **Dockerネットワーク** | shogun-netに全サービスを配置 |

| 共有不可 | 理由 |
|---------|------|
| Claude Code CLI設定(`~/.claude/`) | エージェントごとに設定が異なる |
| tmuxセッション | コンテナ間では共有不可 |
| MCPサーバー | stdio接続はプロセス内のみ |

---

## §5 トレードオフ分析（3案比較）

| 評価軸 | 案B（即座） | 案C（将来） | 現状維持+allowlist |
|--------|:----------:|:----------:|:-----------------:|
| パーミッション解決 | ○ | ◎ | △（イタチごっこ） |
| 実装コスト | 中（Dockerfile+compose） | 高（swarm Phase 2前提） | 低（yaml追記のみ） |
| 運用複雑性 | 中（2-3コンテナ） | 高（7+コンテナ） | 低（現状維持） |
| tmux依存 | 温存 | 排除 | 温存 |
| 着手可能時期 | 即座 | swarm Phase 2後 | 即座 |
| ラズパイ展開 | △ | ○ | × |
| 殿のJDim体験 | 変わらず | 向上（全HTTP） | 変わらず |
| ロールバック | 容易（compose down） | 中程度 | 不要 |

### 推奨判断フロー

```
Q: パーミッション問題で足軽が止まる頻度は?
  ├── 週1回未満 → 現状維持+allowlist（コスト最小）
  ├── 週1-3回  → 案B（セッション単位コンテナ化）で即対処
  └── 毎日     → 案B即実施 + swarm Phase 2を加速して案Cへ
```

---

## §6 見落としの可能性

1. **Docker-in-Docker (DinD) 問題**: healthcheck.shがDockerの状態をチェックしている。コンテナ内からホストのDockerを確認するにはDinDかDocker socket mountが必要。セキュリティリスクあり
2. **git push/pull の認証**: コンテナ内からgit pushするにはSSH鍵かgh auth tokenのマウントが必要。現行はホストの`~/.ssh/`を使用
3. **Claude Code のバージョンアップ**: コンテナイメージの再ビルドが必要。自動更新(`claude update`)がコンテナ内で期待通り動くかは未検証
4. **ログ管理**: 7エージェントのClaude Codeログがコンテナ内に閉じ込められる。`docker logs`で見えるか、ボリュームマウントが必要か
5. **コスト**: Docker自体は無料だが、Claude API呼び出しコストは変わらない。コンテナ化で「気軽に足軽を増やせる」ようになると、API消費が増加するリスク
6. **`--bare`モードの今後**: 公式ドキュメントに「`--bare`は将来`-p`のデフォルトになる」とある。これが実現するとhooks/skills/CLAUDE.mdの明示的注入が必須になる

---

## §7 総合所見

```
┌──────────────────────────────────────────────────────────────┐
│ Docker化は「やるべきか」ではなく「いつやるか」の問題である。  │
│                                                                │
│ パーミッション問題は構造的。Claude Codeの安全装置が            │
│ 厳格化するほど、足軽の無人運転は困難になる。                  │
│ allowlistは応急処置であり、根治ではない。                      │
│                                                                │
│ ただし、今日やるべきかと問われれば「まだ早い」。              │
│                                                                │
│ swarm Phase 2（YAML廃止+HTTP通信）が完了すれば、              │
│ tmux依存が消え、Docker化の障壁が大幅に下がる。               │
│ 今Docker化に着手するとtmux温存（案B）にならざるを得ず、       │
│ swarm Phase 2後に案Cへ移行する二度手間が発生する。            │
│                                                                │
│ 推奨: Phase 0（Dockerfile試作+単体試験）のみ先行。            │
│ 本格移行はswarm Phase 2完了を待て。                            │
│ その間はallowlist拡充で凌げ。                                  │
└──────────────────────────────────────────────────────────────┘
```

### 推奨アクション

| 優先度 | アクション | 前提条件 |
|:------:|-----------|---------|
| **即座** | Dockerfile.shogun-agent の試作（Phase 0） | なし |
| **即座** | identity_inject.sh の `AGENT_ID`環境変数フォールバック確認 | なし |
| **中期** | swarm Phase 2を完了させる（Docker化の真の前提条件） | swarm Phase 0-1完了 |
| **中期後** | Phase 1（セッション単位コンテナ化）実施 | Phase 0試験合格 |
| **長期** | Phase 2（HTTP完全分離）実施 | swarm Phase 2完了 |

---

---

## §8 追記: 殿の3拠点構成方針（addendum反映）

> 殿の基本方針: **「考える場所と作業する場所の分離」**

### 3拠点の役割と構成

```
┌─────────────────────────────────────────────────────────────────────┐
│                    shogun Docker 3拠点構成                           │
│                                                                       │
│  MBP（壁打ち場）        RPi（現場）           VPS（放置場）          │
│  ┌─────────────┐     ┌─────────────┐      ┌─────────────────┐      │
│  │ 将軍コンテナ  │     │ HW制御      │      │ 老中+足軽コンテナ│      │
│  │  (軽量)       │     │ エージェント │      │  (自律運用)      │      │
│  │ - 壁打ち      │     │ - 農業IoT    │      │ - タスク分解     │      │
│  │ - dashboard   │     │ - センサー   │      │ - 実装          │      │
│  │ - 判断+対話   │     │ - 灌水制御   │      │ - 監査          │      │
│  └──────┬───────┘     └──────┬──────┘      │ - systrade       │      │
│         │                    │              │ - 獏/軍師/お針子 │      │
│         │                    │              └──────┬──────────┘      │
│         │                    │                     │                  │
│         └────────────────────┴─────────────────────┘                  │
│                     agent-swarm (2ch BBS)                              │
│                     HTTP通信で3拠点接続                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 各拠点のコンテナ設計

#### MBP: 将軍コンテナ（軽量）

```yaml
# docker-compose.mbp.yml
services:
  shogun:
    image: shogun-agent:light  # Claude Code CLI + 最小依存
    environment:
      - AGENT_ID=shogun
      - ANTHROPIC_API_KEY
      - BBS_URL=http://vps.example:8824  # VPS上のswarmに接続
    volumes:
      - /Users/yasu/multi-agent-shogun:/workspace:ro  # 読み取り専用
      - /Users/yasu/.claude:/root/.claude
    ports: []  # MBPはサーバー機能不要
```

**特徴**:
- 読み取り専用ワークスペース（将軍は手を動かさない）
- dashboard閲覧 + JDimで2ch板を見る + 壁打ち
- Claude Codeの対話モード（OAuth認証、ブラウザ使用可）
- **パーミッション**: 将軍は元々instructionsで手動操作が禁止。コンテナ化の恩恵は限定的だが、環境統一の意味はある

#### RPi: HW制御コンテナ（ARM + リソース制約）

```yaml
# docker-compose.rpi.yml
services:
  hw-agent:
    image: shogun-agent:arm64  # ARM64ビルド
    environment:
      - AGENT_ID=hw_agent
      - BBS_URL=http://vps.example:8824
    volumes:
      - /home/yasu/uecs-llm:/workspace
      - /dev/ttyUSB0:/dev/ttyUSB0  # シリアルデバイス（Arduino/UniPi）
    devices:
      - /dev/i2c-1:/dev/i2c-1      # I2Cセンサー
      - /dev/spidev0.0:/dev/spidev0.0  # SPI (W5500等)
    privileged: false  # デバイスは明示的にマウント
    deploy:
      resources:
        limits:
          memory: 512M  # RPi 4GB中、他サービスと共存
```

**特徴**:
- **Claude Code CLIは不要の可能性が高い**。RPiのHW制御はPythonスクリプト（uecs-llm）で直接実行
- LLM APIはHTTP呼び出しで十分（`claude -p`の代わりにAnthropic Python SDK直接使用）
- デバイスアクセス（I2C/SPI/Serial）のマウントが核心
- メモリ512MB制限でClaude Code常駐は非現実的

**重要判断**: RPiではClaude Codeコンテナではなく、**Pythonスクリプトコンテナ**が適切。

```yaml
  # RPi向けの現実的な構成
  uecs-worker:
    image: python:3.12-slim-bookworm
    volumes:
      - /home/yasu/uecs-llm:/app
    devices:
      - /dev/i2c-1
    environment:
      - ANTHROPIC_API_KEY  # SDK直接呼び出し用
    command: python3 /app/scripts/control_loop.py
```

#### VPS: 放置運用コンテナ群（自己回復必須）

```yaml
# docker-compose.vps.yml
services:
  # 老中+足軽（メイン作業部隊）
  multiagent:
    image: shogun-agent:latest
    environment:
      - ANTHROPIC_API_KEY
    volumes:
      - /home/yasu/multi-agent-shogun:/workspace
      - botsunichiroku-db:/workspace/data
      - /home/yasu/.claude:/root/.claude
    restart: unless-stopped  # 自己回復
    healthcheck:
      test: ["CMD", "bash", "scripts/healthcheck.sh"]
      interval: 5m
      timeout: 30s
      retries: 3

  # 軍師+お針子+獏
  ooku:
    image: shogun-agent:latest
    environment:
      - ANTHROPIC_API_KEY
    volumes:
      - /home/yasu/multi-agent-shogun:/workspace
      - botsunichiroku-db:/workspace/data
    restart: unless-stopped

  # systrade放置運用
  systrade-daily:
    image: systrade-runner:latest
    volumes:
      - /home/yasu/systrade:/app
    # systemd timerまたはcronで日次実行
    command: python3 scripts/daily_risk.py

  # agent-swarm (全拠点の通信ハブ)
  swarm:
    image: agent-swarm:latest
    ports:
      - "0.0.0.0:8824:8824"  # 外部からの接続を許可
    volumes:
      - swarm-db:/app/data
    restart: unless-stopped

volumes:
  botsunichiroku-db:
  swarm-db:
```

**VPS自己回復の設計**:

| 障害 | 検知 | 自動復旧 |
|------|------|---------|
| コンテナクラッシュ | Docker healthcheck | `restart: unless-stopped` |
| Claude Code hang | healthcheck.sh timeout | Docker restart policy |
| DB lock | SQLite WAL timeout | WAL checkpoint + retry |
| メモリ不足 | OOM killer | Docker memory limits + restart |
| API認証切れ | HTTP 401 | **手動対処必要**（APIキー更新） |

**注意: API認証切れだけは自動回復できない。** `ANTHROPIC_API_KEY`の期限管理が必要。

### 3拠点間通信

```
MBP (殿の壁打ち)
  │
  │ HTTPS (WireGuard VPN経由)
  │ ← 殿がJDimでswarm板を閲覧
  │ ← 殿がbbs.cgiにスレ立て（指示）
  │
  ▼
VPS (agent-swarm: port 8824)  ← 通信ハブ
  │
  │ HTTP (LAN or WireGuard)
  │ ← RPiがセンサーデータ/アラートを投稿
  │ ← RPiが指示スレを読み取り
  │
  ▼
RPi (HW制御)
```

**WireGuard VPN**: 殿のmemory/vps_sakura.mdに既存のWireGuard設定がある。
MBP↔VPS間は既にVPN接続済み。RPi追加はWGピア追加のみ。

### パーミッション浪費根絶の効果試算

| 現状 | Docker化後 |
|------|-----------|
| 足軽がパーミッション確認で停止（推定週2-3回） | ゼロ（`--dangerously-skip-permissions`） |
| 停止→殿が気づく→再開 = 30分-数時間のロス | ゼロ |
| allowlist追加のイタチごっこ（Claude Code更新のたび） | 不要 |
| パーミッション確認のトークン消費 | ゼロ |

**保守的試算**: 週3回×30分のロス = 月6時間の浪費を根絶。

### §0修正: 推奨判断の更新

殿の3拠点方針を前提に、推奨を更新する:

**旧推奨**: 「swarm Phase 2を待て」
**新推奨**: **Phase 0（Dockerfile試作）は即座に着手。VPSコンテナの自己回復設計を優先。**

理由:
1. 殿の方針は明確。Docker化は「やるか否か」ではなく「いつどう進めるか」
2. VPSの放置運用（restart: unless-stopped + healthcheck）はswarm Phase 2を待たずに実現可能
3. MBPの将軍コンテナは軽量で、実装コストが低い
4. RPiはClaude Codeコンテナではなく、Pythonスクリプトコンテナが適切（判断変更）

---

*以上。戦場は三つに分かれた。考える場所（MBP）、手を動かす場所（VPS）、物理に触れる場所（RPi）。コンテナはこの分離を写し取る器である。*
