# プロジェクト構造

## ディレクトリ構成

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

## コンテンツ構造

### ブログ投稿 (`content/posts/`)

各投稿は独自のディレクトリを持ち、以下の構造：

```
content/posts/[post-slug]/
├── index.md           # メインコンテンツ
├── featured.jpg       # アイキャッチ画像
└── [other-images]     # 記事内で使用する画像
```

### フロントマター構造

```yaml
---
date: 2024-01-08 22:57:23+09:00
tags:
  - hardware
  - apple
  - review
title: "記事タイトル"
description: "記事の説明文"
summary: "記事の要約"
categories:
  - "Computer"
  - "What I Bought"
---
```

## 命名規則

### ディレクトリ・ファイル名

- **投稿スラッグ**: ケバブケース（例：`bought-apple-iphone-15-pro`）
- **画像ファイル**: 説明的な名前（例：`featured.jpg`, `iphone-15-pro-geekbench.png`）
- **設定ファイル**: 小文字 + アンダースコア（例：`hugo.yaml`, `params.yaml`）

### カテゴリー

- `Computer`: 技術関連記事
- `What I Bought`: 購入品レビュー
- `Photo`: 写真関連
- `Travel`: 旅行記録

### タグ

- `hardware`, `software`, `apple`, `review`, `affiliate` など
- 小文字で統一
- 複数単語は必要に応じてハイフンで区切り

## 画像管理

- **アイキャッチ画像**: 各投稿ディレクトリの `featured.jpg`
- **記事内画像**: 同じディレクトリに配置
- **共通画像**: `assets/img/` または `static/` に配置

## 設定ファイルの役割

- `hugo.yaml`: サイト基本設定、ビルド設定
- `params.yaml`: テーマ固有の設定、レイアウト設定
- `menus.yaml`: ナビゲーションメニュー構成
- `languages.yaml`: 多言語設定
- `markup.yaml`: マークダウン処理設定
