# Docker支店設計メモ

> **種別**: 設計メモ（実装は殿裁定後）
> **作成**: subtask_1100 / cmd_500
> **参照**: docs/shogun/docker_design_survey.md（軍師調査書）

---

## 目的

足軽がパーミッション確認プロンプトで停止する問題の**根本解決**。

現状は `allowlist` に都度ツールを追加する対症療法。Claude Codeのバージョンアップで
新たな確認が増えるたびにイタチごっこになる。コンテナ内なら
`--dangerously-skip-permissions` を安全に使えるため、パーミッション問題が消滅する。

---

## allowlist対処 vs Docker化 比較

| 観点 | allowlist対処（現行） | Docker化（提案） |
|------|---------------------|----------------|
| パーミッション問題 | △ 都度追加が必要 | ◎ 根本解決 |
| 導入コスト | ◎ ゼロ | △ Dockerfile+compose作成 |
| 運用コスト | △ バージョンアップ毎に追加 | ○ 一度作れば安定 |
| 環境再現性 | △ ホスト依存 | ◎ Dockerfileで完全再現 |
| RPi/VPS移設 | × ホスト設定の再現が必要 | ○ docker pullで展開可 |
| リスク | 低 | 中（初期設定の手間） |

**判断基準**: allowlistイタチごっこの頻度が月2回以上になったらDocker化判断のサイン。

---

## 推奨構成: 案B（セッション単位グループ化）

軍師調査書§1より、**案B★★★**を採用。tmux依存を温存しつつパーミッション問題を解決する
現実的な落としどころ。

```
┌─────────────────────────────────────────┐
│  multiagentコンテナ                       │
│  tmux session: multiagent               │
│  ├── karo (agents.0)                    │
│  ├── ashigaru1 (agents.1)               │
│  ├── ashigaru2 (agents.2)               │
│  └── ashigaru6 (agents.3)               │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  ookuコンテナ                             │
│  tmux session: ooku                     │
│  ├── gunshi (agents.0)                  │
│  ├── ohariko (agents.1)                 │
│  └── baku (agents.3)                    │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  swarmコンテナ                            │
│  agent-swarm BBS (port 8824)            │
└─────────────────────────────────────────┘
       ↑ shogun-net (docker bridge)
```

コンテナ間通信（multiagent ↔ ooku）は現時点では bbs.cgi POST 経由。
tmux send-keysは同一コンテナ内のみ有効（案B の制約）。

---

## Dockerfile

```dockerfile
# Dockerfile.shogun-agent
FROM ubuntu:24.04

# 基本ツール
RUN apt-get update && apt-get install -y \
    curl git tmux python3 python3-pip \
    jq openssh-client sqlite3 && \
    rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN curl -fsSL https://claude.ai/install.sh | bash

# Python依存（没日録CLI, kanjou_ginmiyaku等）
COPY requirements.txt /tmp/
RUN pip3 install --break-system-packages -r /tmp/requirements.txt

WORKDIR /workspace

# tmux無し環境でもidentity_inject.shが動作するよう環境変数注入
ENV AGENT_ID=""
ENV ANTHROPIC_API_KEY=""

CMD ["bash"]
```

**注意事項**:
- `--bare` モードは使わない（instructions/hooks/skillsが無効化される）
- `--dangerously-skip-permissions` をCMDに含める（コンテナ内なら安全）
- Memory MCPはコンテナ内に持ち込まない（没日録DB+gitが正データ。許容設計）

---

## ネットワーク設計

```yaml
networks:
  shogun-net:
    driver: bridge
    # multiagent, ooku, swarm が同一ネットワーク内
    # BBS URL: http://swarm:8824 (コンテナ名で名前解決)
```

| 接続先 | 方式 | 設定 |
|-------|------|------|
| BBS (agent-swarm) | HTTP `http://swarm:8824` | shogun-net内で名前解決 |
| git push (fork) | SSH | `~/.ssh` をマウント |
| MBP SSH (ollama) | SSH `mbp.local` | `~/.ssh/known_hosts` + `~/.ssh/config` をマウント |
| GitHub API | HTTPS | `~/.gitconfig` をマウント |

```yaml
# docker-compose の volumes（各サービス共通）
volumes:
  - .:/workspace                        # リポジトリ本体
  - ${HOME}/.claude:/root/.claude       # settings, hooks, skills, CLAUDE.md
  - ${HOME}/.ssh:/root/.ssh:ro          # git push + MBP SSH（read-only）
  - ${HOME}/.gitconfig:/root/.gitconfig:ro
```

**worktreeの扱い**: `/tmp/worktree-subtask-XXXX` はコンテナの `/tmp` に作成される。
ホストからは見えないが、コンテナ内のgit操作は bind mount の `/workspace` に対して有効。

---

## ボリュームマウント

```yaml
services:
  multiagent:
    volumes:
      - .:/workspace                      # shogunリポジトリ（bind mount）
      - ${HOME}/.claude:/root/.claude     # Claude Code設定一式
      - ${HOME}/.ssh:/root/.ssh:ro        # SSH鍵（read-only）
      - ${HOME}/.gitconfig:/root/.gitconfig:ro
    environment:
      - ANTHROPIC_API_KEY
      - BBS_URL=http://swarm:8824         # agent-swarmのURL（scripts側で参照予定）

  ooku:
    volumes:
      - .:/workspace
      - ${HOME}/.claude:/root/.claude
      - ${HOME}/.ssh:/root/.ssh:ro
      - ${HOME}/.gitconfig:/root/.gitconfig:ro
    environment:
      - ANTHROPIC_API_KEY
      - BBS_URL=http://swarm:8824

  swarm:
    build:
      context: /home/yasu/agent-swarm
    ports:
      - "8824:8824"
    volumes:
      - /home/yasu/agent-swarm:/app
```

---

## 起動/停止（worker_ctl.sh 拡張案）

現行 `worker_ctl.sh` はtmuxペインでClaude Codeを起動/停止する。
Docker版では `docker exec` + `docker-compose` に拡張する。

```bash
# worker_ctl.sh 拡張（概念）

# 起動（現行: tmuxペインでclaude起動）
# Docker版: docker-compose up -d multiagent
docker-compose -f docker-compose.shogun.yml up -d multiagent

# 停止（現行: tmuxペインでCtrl+C）
# Docker版: docker-compose stop
docker-compose -f docker-compose.shogun.yml stop multiagent

# 特定エージェントを再起動（足軽1ペインのリセット相当）
docker exec multiagent tmux send-keys -t multiagent:agents.1 'q' Enter

# ログ確認
docker-compose -f docker-compose.shogun.yml logs --tail=50 multiagent
```

**移行方針**: 既存 `worker_ctl.sh` に `--docker` フラグを追加して両モード対応にする。
環境変数 `SHOGUN_DOCKER=1` で自動切替も可。

---

## 移行フェーズ（3段階）

| フェーズ | 内容 | 前提条件 | 判断ポイント |
|---------|------|---------|------------|
| **Phase 0** | Dockerfile単体試験。`--dangerously-skip-permissions`の動作確認 | なし | パーミッション問題が解消されるか |
| **Phase 1** | 案B: multiagent+ooku+swarmの3コンテナ化。tmux温存 | Phase 0合格 | コンテナ間send-keysの代替が必要か |
| **Phase 2** | 案C: HTTP完全分離。各エージェント独立コンテナ | swarm Phase 2完了 | tmux依存ゼロ達成後 |

**現在地**: Phase 0前（設計メモ段階）。殿裁定後にPhase 0着手。

---

## 未解決課題

| 課題 | 重要度 | 対処案 |
|------|:------:|-------|
| Memory MCPのコンテナ跨ぎ | 低 | 諦める（没日録DB+gitが正データ） |
| `shogun` tmuxセッション（将軍）のDocker化 | 中 | Phase 1では対話モードのため対象外 |
| arm64（ラズパイ）でのClaude Code動作 | 低 | 調査書§4参照。amd64エミュレーションで代替可 |
| BBS_URLのhardcode回避 | 中 | 環境変数 `BBS_URL` でスクリプト側を抽象化 |

---

## 関連ドキュメント

| 文書 | 内容 |
|------|------|
| `docs/shogun/docker_design_survey.md` | 軍師による詳細設計調査（案A/B/C比較・技術障壁・ロードマップ） |
| `memory/project_docker_sandbox.md` | 殿方針: 考える場所と作業する場所の分離 |
| `scripts/worker_ctl.sh` | 現行ワーカー起動/停止スクリプト |
