# 技術スタック

## ビルドシステム

- **静的サイトジェネレーター**: Hugo
- **テーマ**: Blowfish (Tailwind CSS ベース)
- **設定形式**: YAML
- **コンテンツ形式**: Markdown

## 主要技術

- **フロントエンド**: Hugo + Blowfish テーマ
- **スタイリング**: Tailwind CSS (テーマに内包)
- **画像最適化**: Hugo内蔵機能 (WebP対応)
- **検索機能**: 有効化済み
- **多言語対応**: 日本語がデフォルト、英語も設定済み
- **SEO**: 構造化データ、サイトマップ、robots.txt対応

## よく使うコマンド

### 開発・ビルド

```bash
# 開発サーバー起動
hugo server

# 開発サーバー起動（ドラフト含む）
hugo server -D

# 本番ビルド
hugo

# 本番ビルド（ドラフト含む）
hugo -D
```

### コンテンツ作成

```bash
# 新しい投稿作成
hugo new posts/[post-name]/index.md

# 新しいページ作成
hugo new [page-name]/index.md
```

## 設定ファイル

- `config/_default/hugo.yaml`: メイン設定
- `config/_default/params.yaml`: テーマパラメーター
- `config/_default/menus.yaml`: ナビゲーション設定
- `config/_default/languages.yaml`: 多言語設定
- `config/_default/markup.yaml`: マークダウン設定

## デプロイメント

- ベースURL: `http://localhost:1313/blog/` (開発用)
- Google Analytics: 設定済み (G-TPRYLTLRFG)
- サイトマップ: 自動生成
- RSS: 自動生成

## 旧ブログ

- このプロジェクトはWordPressで動いている旧ブログからHugoへの移行を行っている
- 旧ブログは https://rewse.jp/blog/ で公開されている
- 旧ブログの全ての記事は exported/ にXMLで出力されている
