# 高札 (kousatsu) v1 — Docker FastAPI

> ⚠️ DEPRECATED (2026-03-18, cmd_419)
> 高札v1のDocker環境は没日録CLI(scripts/botsunichiroku.py)に統合済み。
> 全16エンドポイントがCLIサブコマンドに置換済み。
> Docker起動不要。詳細: docs/shogun/2ch_integration_design.md

## 移行先コマンド対応表

| 旧: curl localhost:8080/... | 新: python3 scripts/botsunichiroku.py ... |
|----------------------------|------------------------------------------|
| GET /search?q=XXX | search "XXX" |
| GET /search/similar?subtask_id=XXX | search --similar XXX |
| POST /reports | report add ... |
| GET /check/orphans | check orphans |
| GET /check/coverage?cmd_id=XXX | check coverage XXX |
| POST /audit | subtask update --audit-status |
| GET /audit/subtask_XXX | audit list --subtask XXX |
| POST /enrich | search --enrich CMD_ID |

## このディレクトリについて

Dockerfile, docker-compose.yml, main.py は履歴参照用に保持。
再起動・ビルドは行わないこと。
