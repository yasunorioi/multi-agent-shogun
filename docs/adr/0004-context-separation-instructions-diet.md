# ADR-0004: context分離とinstructions軽量化

- **Status**: accepted
- **Date**: 2026-03-08

## Context

instructions/karo.md が1373行に肥大化し、以下の問題が発生した：

1. **コンテキスト圧迫**: 家老のセッション開始時に1373行を読み込むとトークンの大部分を消費
2. **コンパクション頻発**: 大量のinstructions読み込みにより、実作業前にコンパクションが発生
3. **CLAUDE.md肥大化**: 全エージェント共通のCLAUDE.md（401行）にも将軍専用セクションが混在
4. **参照頻度の偏り**: send-keysルールは毎回参照するが、モデル切替手順は稀にしか参照しない

## Decision

instructionsの内容をトピック別のcontext/*.mdファイルに分離し、必要時のみ読み込む方式を採用。

- **context/karo-*.md**: karo.mdの8つのトピックを個別ファイルに抽出（sendkeys, botsunichiroku, audit, clear, model, dashboard, parallel, yaml-format）
- **CLAUDE.md圧縮**: 401行→145行。将軍専用セクション7項目をinstructions/shogun.mdに移動
- **高札配信**: context/*.mdは高札API（`curl -s http://localhost:8080/docs/context/ファイル名`）で配信可能
- **instructions本体は編集しない**: 既存のkaro.md（1373行）は当面維持。将来的に参照方式に移行

代替案：
- **karo.md自体を分割**: 既存のinstructionsフォーマットを壊すため当面不採用
- **全てMemory MCPに移行**: 構造化されたルールの検索性が低下するため不採用

## Consequences

- **メリット**: コンテキスト消費の最適化（必要な時だけ読む）、コンパクション頻度の低減、CLAUDE.md 64%削減
- **デメリット**: ファイル数の増加（context/karo-*.md 8ファイル）、二重管理のリスク（karo.md本体とcontext/の乖離）
- **制約**: context/フォルダは.gitignore対象（Git管理外）。高札経由で配信する設計
- **将来**: karo.md本体を圧縮し、context/*.mdへの参照に置き換えることで完全軽量化
