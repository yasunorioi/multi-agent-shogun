# Maintainer's Guide (メンテナ向けガイド)

このドキュメントは、`multi-agent-shogun` のフォーク主であるあなた（Maintainer）のための、公開運用ガイドです。

## 1. 心構え：これは「製品」ではなく「研究」です
公開にあたって最大の不安は「完璧なサポートを求められるのではないか」という点かと思います。
しかし、オープンソースの世界では **「現状有姿 (AS IS)」** が基本です。

*   **サポート義務はありません**: 質問に答える義務も、バグを直す義務もありません。
*   **研究プレビューです**: 「現在進行形で実験中のコードです」と胸を張って言ってください。
*   **私の庭です**: あなたのリポジトリです。あなたのルールで運営して構いません。

## 2. Issue（質問・バグ報告）への対応方針
見知らぬ人からIssueが来ても焦る必要はありません。以下のパターンで対応しましょう。

### パターンA：面白い提案・建設的なバグ報告
> "Thank you for the report! interesting finding. Ideally, we should fix this in `karo.md`. Feel free to open a PR."
> （報告ありがとう！面白いですね。理想的にはXXを直すべきです。PR歓迎します。）

### パターンB：使い方がわからない・サポート要求
> "This represents a highly experimental research environment and setup involves complexity. Please refer to existing docs. I cannot provide individual setup support."
> （これは非常に実験的な研究環境であり、セットアップは複雑です。ドキュメントを参照してください。個別のサポートはできません。）

### パターンC：自分の方針と合わない要求
> "Thanks for the suggestion, but this goes against the core design philosophy of Shin-Ooku. I will close this as out-of-scope."
> （提案ありがとう。でもそれはシン・大奥の設計思想に合いません。今回は見送ります。）

## 3. Pull Request (PR) のレビュー基準
PRが来た場合、コードの綺麗さよりも **「自律サイクルの維持」** を最優先にチェックしてください。

*   ✅ **OK**: バグ修正、ドキュメント改善、新しいツールの追加。
*   ⚠️ **注意**: プロンプト（`instructions/`）の変更。
    *   エージェントの性格（ツンデレ等）を変えていないか？
    *   「大奥ループ（監査→報告）」を壊すような変更ではないか？
    *   **特に `karo.md` と `ohariko.md` はシステムの心臓部なので慎重に。**

## 4. リリースとバージョニング
厳密なセマンティックバージョニング（v1.0.0等）は不要です。
「動いている状態」で `git tag v0.1-preview` のようにタグを打つだけで十分です。

## 5. 免責事項（READMEにも記載推奨）
> This software is experimental research code. It is provided "as is", without warranty of any kind.
> （本ソフトウェアは実験的な研究コードです。現状有姿で提供され、いかなる保証もありません。）

---
**楽しんでください！**
世界中の誰かが、あなたのコードで新しい発見をするかもしれません。それがOSSの醍醐味です。
