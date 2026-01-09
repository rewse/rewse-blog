# rewse-blog

Hugoを使用した個人ブログサイトです。技術レビュー、購入品レビュー、旅行記録などの個人的なコンテンツを日本語で発信しています。

## 概要

- **静的サイトジェネレーター**: Hugo
- **テーマ**: Blowfish (Tailwind CSS ベース)

## 主要コンテンツ

- **技術記事**: ハードウェア・ソフトウェアのレビューと解説
- **購入品レビュー**: Apple製品、PC周辺機器、家電製品などの詳細レビュー
- **旅行記録**: 国内外の旅行体験記
- **ライフスタイル**: デスク環境、ホームオートメーション、写真・動画機材の紹介

## 開発環境のセットアップ

### 必要な環境

- Hugo (extended版)
- Git

### セットアップ手順

1. リポジトリをクローン
```bash
git clone --recursive [repository-url]
cd rewse-blog
```

2. 開発サーバーを起動
```bash
hugo server
```

3. ドラフト記事も含めて確認する場合
```bash
hugo server -D
```

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
├── archetypes/          # コンテンツテンプレート
├── assets/              # 静的アセット
│   ├── css/            # カスタムCSS
│   ├── icons/          # アイコンファイル
│   └── img/            # 画像ファイル
├── config/              # Hugo設定ファイル
│   └── _default/       # デフォルト設定
├── content/             # コンテンツファイル
│   ├── posts/          # ブログ投稿
│   ├── uses/           # 使用機材ページ
│   └── about-tats-shibata/ # プロフィールページ
├── i18n/               # 多言語対応ファイル
├── layouts/            # カスタムレイアウト
├── static/             # 静的ファイル（favicon等）
└── themes/             # Hugoテーマ
    └── blowfish/       # Blowfishテーマ
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

ShortPixel API を使用して画像を最適化し、WebP/AVIF 形式に変換するスクリプトを提供しています。

### 必要な環境

- Python 3.10+
- uv (Python パッケージマネージャー)
- 1Password CLI (`op`)

### 使い方

```bash
# 未処理の画像を処理
./scripts/optimize_images.sh

# 特定のパスのみ処理
./scripts/optimize_images.sh --path content/posts/new-article/

# 強制的に再処理
./scripts/optimize_images.sh --force

# 実行せずに対象を確認（ドライラン）
./scripts/optimize_images.sh --dry-run
```

### 生成されるファイル

各画像に対して以下のサイズ・フォーマットが生成されます：

- サイズ: 400w, 800w, 1200w, 1600w, 2400w
- フォーマット: 元形式 (JPG/PNG), WebP, AVIF

出力先: `static/img/optimized/`

処理済み画像は `.manifest.json` で管理され、再実行時にスキップされます。
