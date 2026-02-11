# OSS Competitor Analyzer

OSS競合プロジェクトを体系的に調査・分析し、YAML形式の報告書を生成するスキル。

- Skill ID: oss-competitor-analyzer
- Category: analysis
- Version: 1.0.0
- Created: 2026-02-07
- Platform: Any

## 概要

特定キーワードでGitHub/GitLab上のOSSプロジェクトを検索し、Star数・更新頻度・コミュニティ規模・技術スタック等の定量指標で評価した競合分析レポートをYAML形式で生成する。新規プロジェクト開始時の市場調査、既存プロジェクトの差別化戦略策定に使用。

## 使用方法

ユーザーが以下のいずれかを要求したら、このスキルを使用：

- 類似OSSプロジェクトを調査したい
- 競合分析レポートを作成したい
- 自分のOSSの差別化ポイントを見つけたい
- 特定分野のOSSランドスケープを把握したい

## 入力パラメータ

| 項目 | 説明 | 例 | 必須 |
|------|------|-----|------|
| project_name | 自プロジェクト名 | rotation-planner | Yes |
| keywords | 検索キーワード（複数可） | ["crop rotation", "farm planning"] | Yes |
| language | 対象プログラミング言語 | Python | No |
| min_stars | 最低Star数フィルタ | 10 | No (default: 0) |
| max_results | 最大結果件数 | 20 | No (default: 15) |
| focus_areas | 重点評価項目 | ["UI/UX", "data model", "API"] | No |

### 検索キーワード戦略

効果的なキーワードの組み立て方：

| レベル | 戦略 | 例 |
|--------|------|-----|
| 直接競合 | 同じ問題を解くキーワード | "crop rotation planner" |
| 間接競合 | 上位カテゴリのキーワード | "farm management software" |
| 技術類似 | 同じ技術スタックのキーワード | "gradio sqlite agriculture" |
| 関連ドメイン | 隣接分野のキーワード | "garden planner", "field mapping" |

## 出力形式

### YAML報告書テンプレート

```yaml
# OSS競合分析レポート
# Generated: {date}

meta:
  project: "{project_name}"
  keywords: {keywords}
  search_date: "{date}"
  total_found: {count}
  analyst: "oss-competitor-analyzer skill"

competitors:
  - name: "{repo_name}"
    url: "https://github.com/{owner}/{repo}"
    description: "{description}"
    metrics:
      stars: {stars}
      forks: {forks}
      last_commit: "{date}"
      open_issues: {count}
      contributors: {count}
      license: "{license}"
    tech_stack:
      language: "{primary_language}"
      frameworks: ["{framework1}", "{framework2}"]
      database: "{db}"
    evaluation:
      activity_score: {1-5}     # 更新頻度
      community_score: {1-5}    # コミュニティ規模
      maturity_score: {1-5}     # 成熟度
      documentation_score: {1-5} # ドキュメント品質
      total_score: {4-20}
    strengths:
      - "{strength1}"
    weaknesses:
      - "{weakness1}"
    differentiation_notes: "{自プロジェクトとの差別化ポイント}"

summary:
  landscape: |
    {市場全体の傾向・分析}
  gaps: |
    {競合が埋めていないニーズ・機会}
  recommendations:
    - "{recommendation1}"
    - "{recommendation2}"
  risk_assessment: |
    {競合リスクの評価}
```

## 実装パターン

### GitHub検索の実行手順

```bash
# 1. GitHub CLI で検索（Star数降順）
gh search repos "{keyword}" --language={language} --sort=stars --limit={max_results} --json name,owner,description,stargazersCount,forksCount,updatedAt,licenseInfo,primaryLanguage

# 2. 追加情報の取得（各リポジトリ）
gh api repos/{owner}/{repo} --jq '{
  open_issues: .open_issues_count,
  subscribers: .subscribers_count,
  created_at: .created_at,
  topics: .topics
}'

# 3. コントリビューター数の取得
gh api repos/{owner}/{repo}/contributors --jq 'length'

# 4. 最新コミット日の確認
gh api repos/{owner}/{repo}/commits --jq '.[0].commit.committer.date' --paginate=false
```

### WebSearch による補完調査

```
# GitHubで見つからない場合の補完
WebSearch("{keyword} open source site:gitlab.com")
WebSearch("{keyword} OSS alternative")
WebSearch("{keyword} awesome list github")
```

### 評価基準（スコアリングルール）

| スコア | activity | community | maturity | documentation |
|--------|----------|-----------|----------|---------------|
| 5 | 週1+コミット | 50+ contributors | 3年+, v2.0+ | 専用サイトあり |
| 4 | 月2+コミット | 20-49 contributors | 2年+, v1.0+ | README充実+Wiki |
| 3 | 月1コミット | 10-19 contributors | 1年+, beta | README充実 |
| 2 | 3ヶ月に1回 | 5-9 contributors | 6ヶ月+, alpha | README基本 |
| 1 | 6ヶ月以上停止 | 1-4 contributors | 6ヶ月未満 | README最低限 |

### 分析レポート生成の手順

1. **検索フェーズ**: 全キーワードで検索し、重複除去・マージ
2. **データ収集フェーズ**: 各リポジトリの定量データを取得
3. **評価フェーズ**: スコアリングルールに基づき各指標を評価
4. **分析フェーズ**: 強み・弱み・差別化ポイントを分析
5. **報告フェーズ**: YAMLテンプレートに記入し報告書を生成

## サンプル出力

```yaml
meta:
  project: "rotation-planner"
  keywords: ["crop rotation", "farm planning", "agriculture software"]
  search_date: "2026-02-07"
  total_found: 8
  analyst: "oss-competitor-analyzer skill"

competitors:
  - name: "FarmHack/crop-planner"
    url: "https://github.com/FarmHack/crop-planner"
    description: "Open source crop rotation planning tool"
    metrics:
      stars: 342
      forks: 87
      last_commit: "2025-11-15"
      open_issues: 23
      contributors: 12
      license: "MIT"
    tech_stack:
      language: "JavaScript"
      frameworks: ["React", "Node.js"]
      database: "MongoDB"
    evaluation:
      activity_score: 3
      community_score: 3
      maturity_score: 4
      documentation_score: 3
      total_score: 13
    strengths:
      - "直感的なドラッグ&ドロップUI"
      - "モバイルレスポンシブ対応"
    weaknesses:
      - "日本の作物・圃場に未対応"
      - "面積集計機能がない"
    differentiation_notes: "rotation-plannerは日本農業特化+GIS面積計算が差別化要素"

summary:
  landscape: |
    輪作計画OSSは欧米圏で数件存在するが、日本農業に特化したものは皆無。
    GIS機能との統合も希少。
  gaps: |
    - 日本の作物体系（水稲・畑作輪作）への対応
    - 畑地化制度等の日本固有制度への対応
    - JA・普及所との連携機能
  recommendations:
    - "日本農業特化を最大の差別化軸とする"
    - "GIS面積集計は競合にない独自機能として推す"
```

## 注意事項

### 必須要素

- GitHub CLI（gh）を使用した定量データ取得
- スコアリングルールに基づく客観的評価
- 自プロジェクトとの差別化ポイント明示
- YAML形式の構造化レポート

### 推奨要素

- WebSearchによる補完調査（GitLab、Awesome Lists等）
- ライセンス互換性の確認
- 直近のリリースノート確認（方向性把握）

### 避けるべき実装

- 主観的な評価（必ず定量指標に基づく）
- 古い情報での判断（last_commitが1年以上前なら注記）
- 自プロジェクトへの過大評価
