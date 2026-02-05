# jar-decompile-analyzer

JARファイルのクラスをstringsコマンドで解析し、文字列リソースを抽出するスキル。

## 概要

Javaアプリケーション（JARファイル）内のクラスファイルから、stringsコマンドを使用して文字列リソースを抽出・分析する。デコンパイラなしで設定値、エンドポイント、メッセージ等を調査できる。

## 使用方法

```
/jar-decompile-analyzer <JARファイルパス> [オプション]
```

### 入力パラメータ

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|-----|
| `jar_path` | Yes | 解析対象のJARファイルパス | `/path/to/app.jar` |
| `--filter` | No | 文字列フィルタ（正規表現） | `--filter "http\|https"` |
| `--min-length` | No | 最小文字列長（デフォルト: 4） | `--min-length 8` |
| `--class-pattern` | No | 対象クラスパターン | `--class-pattern "Config"` |
| `--output` | No | 出力ファイルパス | `--output report.md` |

## 処理フロー

```
1. JARファイル展開（一時ディレクトリ）
2. クラスファイル一覧取得
3. 各クラスにstringsコマンド実行
4. 結果を集計・分類
5. レポート生成
```

## 出力形式

### Markdown形式のレポート

```markdown
# JAR解析レポート: app.jar

## 基本情報
- ファイル: app.jar
- サイズ: 2.3 MB
- クラス数: 156
- 解析日時: 2026-02-04 15:00:00

## クラス一覧（主要）
| パッケージ | クラス数 |
|-----------|---------|
| com.example.config | 12 |
| com.example.service | 45 |
| com.example.model | 28 |

## 文字列リソース

### URL/エンドポイント
- `http://api.example.com/v1/`
- `https://auth.example.com/oauth/`

### 設定キー
- `database.host`
- `database.port`
- `api.timeout`

### メッセージ/ラベル
- `Error: Connection failed`
- `Successfully completed`
```

## サンプル出力

```
$ /jar-decompile-analyzer /opt/arsprout/arsprout-server.jar --filter "UECS\|CCM"

# JAR解析レポート: arsprout-server.jar

## 基本情報
- ファイル: arsprout-server.jar
- サイズ: 4.8 MB
- クラス数: 423
- 解析日時: 2026-02-04 15:12:30

## フィルタマッチ結果

### UECS関連文字列 (23件)
| クラス | 文字列 |
|--------|--------|
| UecsController.class | `UECS_PORT=16520` |
| UecsController.class | `UECS_MULTICAST=239.255.0.1` |
| CcmParser.class | `CCM_VERSION=1.00-E10` |
| CcmBuilder.class | `InAirTemp.mIC` |
| CcmBuilder.class | `InAirHumid.mIC` |
| StandardControl.class | `SetTemp.sIC` |

### 定数定義 (15件)
- `DEFAULT_UECS_PORT = 16520`
- `CCM_HEADER_SIZE = 128`
- `MAX_CCM_DATA_SIZE = 1024`

## 統計
- 総抽出文字列: 12,456
- フィルタマッチ: 38
- ユニーク文字列: 8,234
```

## 実装コマンド例

```bash
#!/bin/bash
# JAR解析スクリプト

JAR_FILE="$1"
WORK_DIR=$(mktemp -d)
trap "rm -rf $WORK_DIR" EXIT

# JAR展開
unzip -q "$JAR_FILE" -d "$WORK_DIR"

# クラスファイル一覧
find "$WORK_DIR" -name "*.class" | while read class; do
    echo "=== $(basename $class) ==="
    strings -n 4 "$class" | grep -E "$FILTER_PATTERN"
done
```

## 用途

- **リバースエンジニアリング**: 設定値・エンドポイント調査
- **セキュリティ監査**: ハードコード認証情報の検出
- **移植作業**: 既存システムの仕様把握
- **デバッグ**: エラーメッセージの追跡

## 注意事項

- 難読化されたJARでは文字列が暗号化されている場合がある
- 大規模JARは解析に時間がかかる（進捗表示あり）
- 著作権に注意し、適法な範囲で使用すること
