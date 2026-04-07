# ADR (Architecture Decision Record) 索引

> shogunシステムの設計判断を記録・追跡するためのADR集。
> memx-core方式を採用（docs/memx_migration_research.md §2参照）。

## 運用ルール

- **更新責任者**: 家老（karo-roju）。将軍の承認後に追加。
- **更新タイミング**: 設計判断が発生した都度。
- **フォーマット**: [TEMPLATE.md](./TEMPLATE.md) に従う。
- **検索**: 高札が未マウントの場合はGrepで検索。将来的に高札FTS5統合を検討。
- **Memory MCPとの棲み分け**: ADR=設計判断の経緯、MCP=殿の好み・行動原則

## ADR 一覧

| # | タイトル | Status | Date |
|---|---------|--------|------|
| [0001](./0001-yaml-db-two-layer-protocol.md) | YAML+DB二層通信プロトコル | accepted | 2026-02-08 |
| [0002](./0002-ohariko-audit-queue.md) | お針子監査キュー方式 | accepted | 2026-02-25 |
| [0003](./0003-blocked-by-dependency.md) | blocked_by依存関係管理 | accepted | 2026-02-27 |
| [0004](./0004-context-separation-instructions-diet.md) | context分離とinstructions軽量化 | accepted | 2026-03-08 |
| [0005](./0005-kousatsu-fts5-search.md) | 高札FTS5全文検索 | accepted | 2026-03-04 |
