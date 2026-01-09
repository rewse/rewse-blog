# rewse-blog

Hugoを使用した個人ブログサイトです。技術レビュー、購入品レビュー、旅行記録などの個人的なコンテンツを日本語で発信しています。

## 概要

- **静的サイトジェネレーター**: Hugo
- **テーマ**: Blowfish (Tailwind CSS ベース)
- **デプロイ先**: AWS Amplify

## 開発環境のセットアップ

### 必要な環境

- Hugo
- Git

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

## プロジェクト構造

```
rewse-blog/
├── archetypes/              # コンテンツテンプレート
├── assets/                  # 静的アセット
│   ├── css/                # カスタムCSS
│   ├── icons/              # アイコンファイル
│   └── img/                # 画像ファイル
├── config/                  # Hugo設定ファイル
│   └── _default/           # デフォルト設定
├── content/                 # コンテンツファイル
│   ├── posts/              # ブログ投稿
│   ├── uses/               # 使用機材ページ
│   └── about-tats-shibata/ # プロフィールページ
├── i18n/                   # 多言語対応ファイル
├── layouts/                # カスタムレイアウト
├── scripts/                # コンテンツ一括修正用スクリプト
│   └── optimize_images.py  # 画像最適化スクリプト
├── static/                 # 静的ファイル（favicon等）
│   └── img/
│       └── optimized/      # 最適化済み画像出力先
├── themes/                 # Hugoテーマ
    └── blowfish/           # Blowfishテーマ
├── amplify.yml              # AWS Amplify ビルド設定
└── Dockerfile               # AWS Amplify カスタムビルドイメージ
```

## 設定ファイル

- `config/_default/hugo.yaml`: サイト基本設定、ビルド設定
- `config/_default/params.yaml`: テーマ固有の設定、レイアウト設定
- `config/_default/menus.yaml`: ナビゲーションメニュー構成
- `config/_default/languages.yaml`: 多言語設定
- `config/_default/markup.yaml`: マークダウン処理設定

## コンテンツ作成ガイド

### ブログ投稿

各投稿は独自のディレクトリを持ち、以下の構造で作成します：

```
content/posts/[post-slug]/
├── index.md           # メインコンテンツ
├── featured.jpg       # アイキャッチ画像
└── [other-images]     # 記事内で使用する画像
```

### フロントマター例

```yaml
---
date: "2024-01-08 22:57:23+09:00"
categories:
  - "Computer"
  - "What I Bought"
tags:
  - "hardware"
  - "apple"
  - "review"
title: "記事タイトル"
description: "記事の説明文"
summary: "記事の要約"
---
```

## 画像最適化

pyvipsを使用して画像のリサイズとWebP/AVIF形式への変換変換を行うスクリプトを提供しています。

### 必要な環境

- Python 3.10+
- uv (Python パッケージマネージャー)
- libvips (画像処理ライブラリ)

### 使い方

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

### 生成されるファイル

各画像に対して以下のサイズ・フォーマットが生成されます：

- サイズ: 400w, 800w, 1200w, 1600w, 2400w
- フォーマット: 元形式 (JPG/PNG), WebP, AVIF

出力先: `static/img/optimized/`

処理済み画像は `.manifest.json` で管理され、再実行時にスキップされます。

## AWS Amplify カスタムビルドイメージ

このプロジェクトでは、libvipsとAVIFサポートを含むカスタムDockerイメージを使用して AWS Amplify でビルドしています。

### Docker イメージの構成

- **ベースイメージ**: Ubuntu 24.04
- **主要パッケージ**:
  - Hugo (動的インストール)
  - libvips-dev, libvips-tools (画像処理)
  - libheif-dev, libheif-plugin-* (AVIF サポート)
  - rav1e, librav1e0 (AV1 エンコーダー)
  - Python 3.12, uv (画像最適化スクリプト用)
  - Amplify 必須パッケージ (curl, git, openssh-client, bash)

### Docker イメージのビルド

```bash
# イメージをビルド
podman build -t public.ecr.aws/v5r5z4u0/amplify-hugo-vips:v2 .
```

### ECR Public へのプッシュ

```bash
# ECR Public にログイン
aws ecr-public get-login-password --region us-east-1 | podman login --username AWS --password-stdin public.ecr.aws

# イメージをプッシュ
podman push public.ecr.aws/v5r5z4u0/amplify-hugo-vips:v2
```
