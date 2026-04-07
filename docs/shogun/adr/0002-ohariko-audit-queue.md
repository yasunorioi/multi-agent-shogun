# ADR-0002: お針子監査キュー方式

- **Status**: accepted
- **Date**: 2026-02-25

## Context

テキスト成果物（設計書・README・instructions等）の品質保証として、お針子（ohariko）による事後監査を導入した。しかし以下の問題が発生した：

1. **同時殺到**: 複数足軽が同時に完了報告→お針子に監査依頼が殺到→お針子が処理しきれない
2. **お針子は1名**: リソース制約により、並列監査は不可能
3. **監査ステータス管理**: 誰が何の監査中か、何が待ちかが不明確

## Decision

キュー方式による1件ずつの監査フローを採用する。

- **audit_status**: 没日録DBのsubtaskに `pending/in_progress/done/rejected` の4状態を追加
- **家老のトリガ判断**: 足軽完了報告受信時に `needs_audit=true` なら `pending` に設定
- **IDLE/BUSY判定**: `audit_status=in_progress` のsubtaskがあればBUSY、なければIDLE
- **通知ルール**: IDLEの場合のみお針子にsend-keys。BUSYならpendingに積むだけ
- **お針子の自律**: 監査完了時に次のpendingを自分で拾う

代替案：
- **全件同時送信**: お針子のコンテキストが溢れるため不採用
- **家老が監査**: 家老は管理専任（F001）のため不採用

## Consequences

- **メリット**: お針子の過負荷防止、監査漏れの防止（pending状態で追跡可能）、家老の判断負荷軽減
- **デメリット**: 監査待ち時間の発生（キュー待ち）、家老のIDLE/BUSY判定手順の追加
- **制約**: お針子からの報告はqueue/inbox/roju_ohariko.yamlで老中に統一（将軍直通は廃止）
