# 技術スタック

## ビルドシステム

- **静的サイトジェネレーター**: Hugo
- **テーマ**: Blowfish (Tailwind CSS ベース)
- **設定形式**: YAML
- **コンテンツ形式**: Markdown

## 主要技術

- **フロントエンド**: Hugo + Blowfish テーマ
- **スタイリング**: Tailwind CSS (テーマに内包)
- **画像最適化**: pyvips
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

### 画像最適化

```bash
# 未処理の画像を処理
uv run scripts/optimize_images.py

# 特定のパスのみ処理
uv run scripts/optimize_images.py --path content/posts/new-article/

# 強制的に再処理
uv run scripts/optimize_images.py --force

# 実行せずに対象を確認（ドライラン）
uv run scripts/optimize_images.py --dry-run
```

## 設定ファイル

- `config/_default/hugo.yaml`: メイン設定
- `config/_default/params.yaml`: テーマパラメーター
- `config/_default/menus.yaml`: ナビゲーション設定
- `config/_default/languages.yaml`: 多言語設定
- `config/_default/markup.yaml`: マークダウン設定

## デプロイメント

- 開発用ベースURL: `http://localhost:1313/`
- 本番用ベースURL: `https://blog.rewse.jp/`
- AWS Amplify App ID: `d8gzy6xdskncg`

### AWS CLIプロファイル

AWS CLIを使用する際は `hugo` プロファイルを使用しなければならない。

```bash
aws <command> --profile hugo | cat
```

### Amplifyビルドログの取得

Amplifyのビルドログは署名付きURLで提供されるため、`webFetch`ツールではアクセスできない。代わりに`curl`コマンドを使用する必要がある。

```bash
# 1. ジョブ情報からログURLを取得
aws amplify get-job --app-id d8gzy6xdskncg --branch-name main --job-id <JOB_ID> --query "job.steps[0].logUrl" --output text

# 2. curlでログを取得
curl -s "<LOG_URL>"
```

## 旧ブログ

- 旧ブログはWordPressで動いていたが、Hugoへ移行された
- 旧ブログは https://rewse.jp/blog/ で公開されていた
- 旧ブログの全ての記事は exported/ にXMLで出力されている

## Hugoテンプレートのデバッグ

HTMLコメント（`<!-- -->`）はHugoのminify設定で削除されるため、テンプレートのデバッグには `warnf` を使用する。

```go
{{ warnf "[DEBUG] variable=%v" $variable }}
```

ビルド時に `WARN` としてコンソールに出力される。

## Amplifyトラブルシューティング

### amplify.yml の YAML 構文

- コロン（`:`）を含むechoコマンドはYAMLパーサーがキーと値の区切りと誤認するため、`->` などに置き換える
- 複数行コマンド（`|`）は避け、`||` でリトライする形式を使う

### キャッシュパスの指定

- キャッシュパスは相対パスで指定する（例: `static/img/optimized`）
- `${PWD}` を含む絶対パスはビルドごとに変わるため使用しない
- ワイルドカード（`**/*`）は不要で、ディレクトリ名だけで良い
