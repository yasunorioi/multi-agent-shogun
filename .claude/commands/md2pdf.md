# 日本語Markdown→PDF変換

MarkdownファイルをA4日本語PDFに変換する。Pandoc + XeLaTeX + Noto Sans CJK JP 使用。

## 使用方法

```
/md2pdf <入力.md> [出力.pdf] [--pages=N] [--fontsize=Npt] [--margin=Ncm]
```

- 出力省略時は入力と同名の.pdf
- --pages でおおよそのページ数を指定（フォントサイズ・マージンを自動調整）

## 実行手順

### 1. 前提確認

```bash
which pandoc xelatex && fc-list | grep -i "noto sans cjk"
```

pandoc, xelatex, Noto Sans CJK JP が必要。なければ：
```bash
sudo apt install pandoc texlive-xetex fonts-noto-cjk
```

### 2. 変換実行

ユーザーが指定したMarkdownファイルを読み、内容に応じてパラメータを決定する。

#### デフォルト（読みやすい標準設定）

```bash
pandoc INPUT.md -o OUTPUT.pdf \
  --pdf-engine=xelatex \
  -V mainfont="Noto Sans CJK JP" \
  -V monofont="Noto Sans Mono CJK JP" \
  -V geometry:margin=2cm \
  -V fontsize=10pt \
  -V papersize=a4 \
  -V colorlinks=true
```

#### コンパクト（2枚に収めたい等）

```bash
pandoc INPUT.md -o OUTPUT.pdf \
  --pdf-engine=xelatex \
  -V mainfont="Noto Sans CJK JP" \
  -V monofont="Noto Sans Mono CJK JP" \
  -V geometry:margin=1.5cm \
  -V fontsize=9pt \
  -V papersize=a4 \
  -V colorlinks=true
```

#### 超コンパクト（1枚に詰め込み）

```bash
pandoc INPUT.md -o OUTPUT.pdf \
  --pdf-engine=xelatex \
  -V mainfont="Noto Sans CJK JP" \
  -V monofont="Noto Sans Mono CJK JP" \
  -V geometry:margin=1cm \
  -V fontsize=8pt \
  -V papersize=a4 \
  -V colorlinks=true
```

### 3. 結果確認

```bash
pdfinfo OUTPUT.pdf | grep -E "Pages|Page size"
```

ページ数が要件と合わなければ fontsize/margin を調整して再実行。

## パラメータ早見表

| 用途 | fontsize | margin | 目安 |
|------|----------|--------|------|
| 標準 | 10pt | 2cm | A4で40行/ページ程度 |
| コンパクト | 9pt | 1.5cm | A4で50行/ページ程度 |
| 超コンパクト | 8pt | 1cm | A4で60行/ページ程度 |
| プレゼン風 | 12pt | 2.5cm | A4で30行/ページ程度 |

## 注意事項

- Markdown内の表はそのままPDF表に変換される
- URLリンクは青色で表示（colorlinks=true）
- 画像パスはMarkdownファイルからの相対パス
- コードブロックは等幅フォント(Noto Sans Mono CJK JP)で表示
- 日本語太字はXeLaTeX制約で**表示されない場合がある**（Noto Sans CJK JPのBoldウェイトが必要）
