# ADR-0003: blocked_by依存関係管理

- **Status**: accepted
- **Date**: 2026-02-27

## Context

subtask間に依存関係がある場合（例: 設計書作成→実装→テスト）、waveによる粗い順序制御のみでは以下の問題があった：

1. **暗黙の依存**: 「subtask_Aが終わってからsubtask_Cを開始」が家老の記憶のみに依存
2. **手動管理**: 家老がコンパクション復帰後に依存関係を忘れるリスク
3. **自動進行不可**: subtask完了時に次のsubtaskを自動的にassignedにできない

## Decision

没日録DBのsubtasksテーブルに `blocked_by` カラムを追加し、依存関係を宣言的に管理する。

- **blocked_by**: カンマ区切りのsubtask_idリスト（例: `subtask_A,subtask_B`）
- **auto_unblock**: subtask完了時（`--status done`）に依存先を自動検索し、全依存が解消されたsubtaskを`assigned`に変更
- **循環検知**: subtask追加時に循環依存を自動検出してエラー
- **waveとの併用**: waveは粗い順序制御（人間向けの可視化）、blocked_byは細粒度の依存関係（機械向けの制御）

代替案：
- **waveのみ**: 細粒度の依存関係が表現できないため不採用
- **外部DAGエンジン**: 導入コストに対して効果が薄いため不採用

## Consequences

- **メリット**: 依存関係の明示化、コンパクション後も正データ（DB）に残る、自動進行によるタスク遅延の削減
- **デメリット**: CLIの引数が増える（`--blocked-by`）、循環検知のロジック追加
- **制約**: blocked_by指定時はstatusが自動的に`blocked`になり、workerが割当済みでも実行されない
