#!/usr/bin/env python3
"""
build_cooccurrence.py - Hopfield共起行列プロトタイプ（高札v2 Phase 0-A）

設計書: context/hopfield_associative.md §4.2

Usage:
    python3 scripts/build_cooccurrence.py            # 全処理（抽出→共起→PMI）
    python3 scripts/build_cooccurrence.py --rebuild  # doc_keywords を再構築してから実行
    python3 scripts/build_cooccurrence.py --test     # hopfield_expand() 動作確認
"""

from __future__ import annotations

import argparse
import math
import re
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "botsunichiroku.db"

# ---------------------------------------------------------------------------
# ストップワード（高頻度すぎて共起情報として無意味な語）
# ---------------------------------------------------------------------------

STOP_WORDS: set[str] = {
    # 一般的な助詞・助動詞相当の語（漢字）
    "場合", "以下", "以上", "追加", "設定", "確認", "実行", "変更", "対応",
    "修正", "作成", "削除", "更新", "取得", "処理", "管理", "実装", "動作",
    "完了", "開始", "終了", "停止", "起動", "接続", "使用", "利用", "方法",
    "必要", "可能", "不可", "対象", "結果", "情報", "データ", "ファイル",
    "エラー", "テスト", "スクリプト", "コード", "システム", "サーバー",
    "ユーザー", "バージョン", "インストール", "セットアップ", "コマンド",
    # 数字・単位
    "分", "秒", "時間", "以降", "以前",
    # 英語短縮
    "DB", "ID", "OK", "NG", "PR",
}

# キーワードの最小長
MIN_KEYWORD_LEN = 2


# ---------------------------------------------------------------------------
# キーワード抽出（MeCabフォールバック: 正規表現ベース）
# ---------------------------------------------------------------------------

def extract_keywords(text: str) -> list[str]:
    """テキストからキーワード（名詞相当）を抽出する。

    MeCab未使用。正規表現で以下を抽出:
    - カタカナ連続 2文字以上
    - 漢字連続 2文字以上
    - 英数字+記号 2文字以上（英字を含む）
    """
    if not text:
        return []

    candidates: list[str] = []

    # カタカナ連続（2文字以上）
    candidates += re.findall(r'[ァ-ヴー]{2,}', text)

    # 漢字連続（2文字以上）
    candidates += re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]{2,}', text)

    # 英字を含む英数字（2文字以上）: API, LLM, FTS5, RPi5, VPN, etc.
    candidates += re.findall(r'[A-Za-z][A-Za-z0-9_\-\.]{1,}', text)

    # 正規化・フィルタリング
    result: list[str] = []
    seen: set[str] = set()
    for w in candidates:
        w = w.strip("-_.")
        if (
            len(w) >= MIN_KEYWORD_LEN
            and w not in STOP_WORDS
            and w not in seen
            and not re.fullmatch(r'[0-9\-\._]+', w)  # 数字のみは除外
        ):
            result.append(w)
            seen.add(w)

    return result


# ---------------------------------------------------------------------------
# DB接続
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"Error: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables(conn: sqlite3.Connection) -> None:
    """doc_keywords / cooccurrence テーブルが存在しない場合は作成する。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doc_keywords (
            doc_id   TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            keyword  TEXT NOT NULL,
            PRIMARY KEY (doc_id, keyword)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dk_keyword ON doc_keywords(keyword)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cooccurrence (
            term_a TEXT NOT NULL,
            term_b TEXT NOT NULL,
            count  INTEGER NOT NULL DEFAULT 0,
            pmi    REAL,
            PRIMARY KEY (term_a, term_b)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cooc_a ON cooccurrence(term_a)")
    conn.commit()


# ---------------------------------------------------------------------------
# ステップ1: doc_keywords 構築
# ---------------------------------------------------------------------------

def build_doc_keywords(conn: sqlite3.Connection, rebuild: bool = False) -> int:
    """commands テーブルから doc_keywords を構築する。"""
    if rebuild:
        conn.execute("DELETE FROM doc_keywords WHERE doc_type = 'cmd'")
        conn.commit()

    rows = conn.execute(
        "SELECT id, command, details FROM commands"
    ).fetchall()

    inserted = 0
    for row in rows:
        doc_id = row["id"]
        text = " ".join(filter(None, [row["command"] or "", row["details"] or ""]))
        keywords = extract_keywords(text)

        for kw in keywords:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO doc_keywords (doc_id, doc_type, keyword) VALUES (?, ?, ?)",
                    (doc_id, "cmd", kw),
                )
                inserted += conn.execute(
                    "SELECT changes()"
                ).fetchone()[0]
            except sqlite3.Error:
                pass

    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# ステップ2: 共起行列構築
# ---------------------------------------------------------------------------

def build_cooccurrence(conn: sqlite3.Connection) -> int:
    """doc_keywords の self-join で共起行列を構築する。

    同一 doc_id 内のキーワードペア（term_a < term_b）をカウント。
    HAVING COUNT >= 2: 最低2件の cmd で共起したペアのみ。
    """
    conn.execute("DELETE FROM cooccurrence")

    conn.execute("""
        INSERT INTO cooccurrence (term_a, term_b, count)
        SELECT a.keyword, b.keyword, COUNT(DISTINCT a.doc_id)
        FROM doc_keywords a
        JOIN doc_keywords b
          ON a.doc_id = b.doc_id AND a.keyword < b.keyword
        GROUP BY a.keyword, b.keyword
        HAVING COUNT(DISTINCT a.doc_id) >= 2
    """)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM cooccurrence").fetchone()[0]
    return count


# ---------------------------------------------------------------------------
# ステップ3: PMI計算
# ---------------------------------------------------------------------------

def update_pmi(conn: sqlite3.Connection) -> None:
    """共起行列の PMI (PPMI) を計算・更新する。

    設計書 §4.2 の update_pmi() 実装。
    負のPMIはゼロにクランプ（PPMI）。
    """
    conn.create_function("LOG2", 1, lambda x: math.log2(x) if x > 0 else None)

    total_docs = conn.execute(
        "SELECT COUNT(DISTINCT doc_id) FROM doc_keywords"
    ).fetchone()[0]

    if total_docs == 0:
        return

    # 各キーワードの文書頻度 (df) を一時テーブルに
    conn.execute("DROP TABLE IF EXISTS _df_tmp")
    conn.execute("""
        CREATE TEMP TABLE _df_tmp AS
        SELECT keyword, COUNT(DISTINCT doc_id) AS df
        FROM doc_keywords
        GROUP BY keyword
    """)

    # PMI = log2( P(a,b) / (P(a) * P(b)) )
    #      = log2( (count/N) / ((df_a/N) * (df_b/N)) )
    #      = log2( count * N / (df_a * df_b) )
    conn.execute("""
        UPDATE cooccurrence SET pmi = (
            SELECT LOG2(
                CAST(cooccurrence.count AS REAL) * ? /
                (CAST(a_df.df AS REAL) * CAST(b_df.df AS REAL))
            )
            FROM _df_tmp a_df, _df_tmp b_df
            WHERE a_df.keyword = cooccurrence.term_a
              AND b_df.keyword = cooccurrence.term_b
        )
    """, (total_docs,))

    # PPMI: 負をゼロにクランプ
    conn.execute("UPDATE cooccurrence SET pmi = 0.0 WHERE pmi < 0 OR pmi IS NULL")

    conn.execute("DROP TABLE IF EXISTS _df_tmp")
    conn.commit()


# ---------------------------------------------------------------------------
# ステップ4: hopfield_expand()
# ---------------------------------------------------------------------------

def hopfield_expand(
    conn: sqlite3.Connection,
    terms: list[str],
    top_k: int = 8,
    min_pmi: float = 0.5,
) -> list[tuple[str, float]]:
    """1段Hopfield更新: 入力キーワード群 → 共起PMIで連想語展開。

    設計書 §4.2 の hopfield_expand() 実装。
    w_ij = PMI、s_j = 入力キーワードの有無。
    活性化 = Σ PMI（入力キーワードと共起する全ての語のPMI合計）

    Returns:
        [(関連語, activation_score), ...] 降順 top_k件
    """
    if not terms:
        return []

    input_set = set(terms)
    placeholders = ",".join("?" * len(terms))

    # 双方向の共起を UNION で取得
    rows = conn.execute(f"""
        SELECT term_b AS related, SUM(pmi) AS activation
        FROM cooccurrence
        WHERE term_a IN ({placeholders}) AND pmi >= ?
          AND term_b NOT IN ({placeholders})
        GROUP BY term_b

        UNION ALL

        SELECT term_a AS related, SUM(pmi) AS activation
        FROM cooccurrence
        WHERE term_b IN ({placeholders}) AND pmi >= ?
          AND term_a NOT IN ({placeholders})
        GROUP BY term_a

        ORDER BY activation DESC
        LIMIT ?
    """, (*terms, min_pmi, *terms, *terms, min_pmi, *terms, top_k * 2)).fetchall()

    # UNION ALL で重複が出る場合があるので集約
    aggregated: dict[str, float] = {}
    for row in rows:
        related = row[0]
        activation = float(row[1] or 0)
        if related not in input_set:
            aggregated[related] = aggregated.get(related, 0) + activation

    result = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)
    return result[:top_k]


# ---------------------------------------------------------------------------
# --test モード
# ---------------------------------------------------------------------------

TEST_CASES = [
    (["側窓"],       "換気・温度・風速 等が連想されるか"),
    (["LINE"],       "Bot・webhook・VPS 等が連想されるか"),
    (["FTS5"],       "検索・SQLite・高札 等が連想されるか"),
    (["蒸留"],       "RPi・モデル・LLM 等が連想されるか"),
    (["コミット"],   "git・漏れ・ashigaru6 等が連想されるか"),
]


def run_test(conn: sqlite3.Connection) -> None:
    """hopfield_expand() の動作確認テスト。"""
    print("\n" + "=" * 70)
    print("  hopfield_expand() 動作確認テスト")
    print("=" * 70)

    total_docs = conn.execute(
        "SELECT COUNT(DISTINCT doc_id) FROM doc_keywords"
    ).fetchone()[0]
    cooc_pairs = conn.execute("SELECT COUNT(*) FROM cooccurrence").fetchone()[0]
    print(f"  doc_keywords: {total_docs} docs | cooccurrence pairs: {cooc_pairs}")
    print()

    for terms, expected in TEST_CASES:
        results = hopfield_expand(conn, terms, top_k=8, min_pmi=0.5)
        related_words = [r for r, _ in results]
        related_str = ", ".join(
            f"{r}({s:.2f})" for r, s in results[:6]
        ) if results else "（連想なし）"

        print(f"  入力: {terms}")
        print(f"  期待: {expected}")
        print(f"  結果: {related_str}")
        print()

    print("=" * 70)


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hopfield共起行列プロトタイプ（高札v2 Phase 0-A）"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="doc_keywords を削除して再構築する",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="hopfield_expand() の動作確認テストを実行する",
    )
    args = parser.parse_args()

    conn = get_connection()
    ensure_tables(conn)

    # --- ステップ1: doc_keywords ----------------------------------------
    existing_kw = conn.execute(
        "SELECT COUNT(*) FROM doc_keywords WHERE doc_type = 'cmd'"
    ).fetchone()[0]

    if existing_kw == 0 or args.rebuild:
        print("[1/3] doc_keywords 構築中...")
        inserted = build_doc_keywords(conn, rebuild=args.rebuild)
        total_kw = conn.execute(
            "SELECT COUNT(*) FROM doc_keywords"
        ).fetchone()[0]
        unique_terms = conn.execute(
            "SELECT COUNT(DISTINCT keyword) FROM doc_keywords"
        ).fetchone()[0]
        print(f"      inserted: {inserted} | total rows: {total_kw} | unique terms: {unique_terms}")
    else:
        total_kw = conn.execute(
            "SELECT COUNT(*) FROM doc_keywords"
        ).fetchone()[0]
        unique_terms = conn.execute(
            "SELECT COUNT(DISTINCT keyword) FROM doc_keywords"
        ).fetchone()[0]
        print(f"[1/3] doc_keywords スキップ（既存 {total_kw} rows / {unique_terms} terms）。--rebuild で再構築。")

    # --- ステップ2: 共起行列 --------------------------------------------
    print("[2/3] 共起行列 構築中...")
    pair_count = build_cooccurrence(conn)
    print(f"      cooccurrence pairs: {pair_count}")

    # --- ステップ3: PMI -------------------------------------------------
    print("[3/3] PMI 計算中...")
    update_pmi(conn)
    nonzero_pmi = conn.execute(
        "SELECT COUNT(*) FROM cooccurrence WHERE pmi > 0"
    ).fetchone()[0]
    max_pmi_row = conn.execute(
        "SELECT term_a, term_b, pmi FROM cooccurrence ORDER BY pmi DESC LIMIT 5"
    ).fetchall()
    print(f"      PMI > 0: {nonzero_pmi} pairs")
    print("      Top-5 PMI:")
    for row in max_pmi_row:
        print(f"        {row[0]} ↔ {row[1]}: {row[2]:.3f}")

    # --- テスト ---------------------------------------------------------
    if args.test:
        run_test(conn)

    conn.close()
    print("\n完了。")


if __name__ == "__main__":
    main()
