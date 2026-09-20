# rewse-blog

This repository contains the source for [blog.rewse.jp](https://blog.rewse.jp/). The site is built with Hugo and Blowfish and deployed through AWS Amplify.

## Setup

Regular development requires the following tools:

- Git
- Hugo Extended 0.163.3

To add or modify images, also install [uv](https://docs.astral.sh/uv/) and a build of libvips with AVIF support.

After cloning the repository, initialize the Blowfish submodule:

```bash
git submodule update --init --recursive
```

Start the local server with:

```bash
hugo server
```

Use `hugo server -D` to include drafts.

## Creating a post

Store each post as a page bundle under `content/posts/<slug>/`. Use kebab-case for the slug.

```bash
hugo new posts/<slug>/index.md
```

```text
content/posts/<slug>/
├── index.md
├── featured.jpg
└── <article-images>
```

The generated `index.md` contains the following front matter:

```yaml
---
title: "Article title"
date: "2026-09-20T16:48:00+09:00"
categories:
tags:
description:
summary:
draft: true
---
```

Edit the post and its images, then preview it with `hugo server -D`. Set `draft: false` when the post is ready to publish.

## Optimizing images

After adding or modifying images, run the optimizer for that post:

```bash
uv run scripts/optimize_images.py --path content/posts/<slug>/
```

Add `--dry-run` to preview which images would be processed, or `--force` to reprocess unchanged images. The script creates resized and AVIF variants at widths of 400, 800, 1200, 1600, and 2400 pixels under `static/img/optimized/` and records their status in `.manifest.json`. Outputs wider than the source retain the source dimensions instead of being upscaled. The `static/img/optimized/` directory contains build artifacts and should not be committed.

## Building

Run a production-equivalent build with:

```bash
hugo --gc --minify
```

Hugo writes the generated site to `public/`. The AWS Amplify build steps and image cache are configured in `amplify.yml`.

## Updating Blowfish

Review the Blowfish release notes before updating, then run:

```bash
scripts/update_blowfish.sh
hugo --gc --minify
```

The script updates the submodule to the latest tag. If upstream changed any overridden layouts, it displays the diffs and offers merge options. After it finishes, review the changes to the submodule and `layouts/`.

## License

The contents of this repository are available under the [Creative Commons Attribution-ShareAlike 4.0 International](LICENSE) license.
