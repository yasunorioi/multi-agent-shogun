# XLS→SQLiteインポーター

ExcelファイルをSQLiteデータベースにインポートするパターン。

## 使用方法

```
/xls-db-importer <xlsファイルパス> <テーブル名> [--header-row=N] [--sheet=シート名]
```

## 実装パターン

```python
import pandas as pd
from pathlib import Path

def import_xls_to_sqlite(
    xls_path: str,
    table_name: str,
    db_path: str,
    header_row: int = 0,
    sheet_name: str = None,
    column_mapping: dict = None
) -> int:
    """
    XLSファイルをSQLiteにインポート

    Args:
        xls_path: XLSファイルパス
        table_name: インポート先テーブル名
        db_path: SQLiteデータベースパス
        header_row: ヘッダー行（0始まり）
        sheet_name: シート名（Noneの場合は最初のデータシート）
        column_mapping: カラム名マッピング {元名: DB名}

    Returns:
        インポートした行数
    """
    import sqlite3

    # XLS読み込み
    xls = pd.ExcelFile(xls_path)

    # シート選択（更新日付等のメタシートをスキップ）
    if sheet_name is None:
        for name in xls.sheet_names:
            if '更新' not in name and '注意' not in name:
                sheet_name = name
                break

    df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row)

    # カラム名マッピング
    if column_mapping:
        df = df.rename(columns=column_mapping)

    # SQLiteに書き込み
    with sqlite3.connect(db_path) as conn:
        df.to_sql(table_name, conn, if_exists='replace', index=False)

    return len(df)
```

## 使用例（FAMICデータ）

```python
# 農薬登録基本部のインポート
column_mapping = {
    '登録番号': 'registration_number',
    '農薬の名称': 'name',
    '用途': 'category',
    '農薬の種類': 'type',
    '有効成分': 'active_ingredient',
    '登録を有する者の名称': 'manufacturer',
    '剤型名': 'formulation'
}

count = import_xls_to_sqlite(
    xls_path='data/famic/登録基本部.xls',
    table_name='pesticide_registry',
    db_path='data/app.db',
    header_row=0,
    column_mapping=column_mapping
)
print(f'{count}件インポート完了')
```

## 注意事項

- xlrdパッケージが必要（`pip install xlrd`）
- シート構成が変わる場合があるので、sheet_nameは明示的に指定推奨
- 大量データの場合はchunksizeオプションを検討
