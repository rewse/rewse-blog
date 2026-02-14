# Project Structure

## Directory Structure

```
rewse-blog/
├── archetypes/              # Content templates
├── assets/                  # Static assets
│   ├── css/                # Custom CSS
│   ├── icons/              # Icon files
│   └── img/                # Image files
├── config/                  # Hugo configuration files
│   └── _default/           # Default configuration
├── content/                 # Content files
│   ├── posts/              # Blog posts
│   ├── uses/               # Equipment usage page
│   └── about-tats-shibata/ # Profile page
├── i18n/                   # Internationalization files
├── layouts/                # Custom layouts
├── scripts/                # Batch content modification scripts
│   └── optimize_images.py  # Image optimization script
├── static/                 # Static files (favicon, etc.)
│   └── img/
│       └── optimized/      # Optimized image output directory
├── themes/                 # Hugo themes
    └── blowfish/           # Blowfish theme
├── amplify.yml              # AWS Amplify build configuration
└── Dockerfile               # AWS Amplify custom build image
```

## Content Structure

### Blog Posts (`content/posts/`)

Each post has its own directory with the following structure:

```
content/posts/[post-slug]/
├── index.md           # Main content
├── featured.jpg       # Featured image
└── [other-images]     # Images used in the article
```

### Front Matter Structure

```yaml
---
date: 2024-01-08 22:57:23+09:00
tags:
  - hardware
  - apple
  - review
title: "Article Title"
description: "Article description"
summary: "Article summary"
categories:
  - "Computer"
  - "What I Bought"
---
```

## Naming Conventions

### Directory and File Names

- **Post Slugs**: Kebab case (e.g., `bought-apple-iphone-15-pro`)
- **Image Files**: Descriptive names (e.g., `featured.jpg`, `iphone-15-pro-geekbench.png`)
- **Configuration Files**: Lowercase + underscore (e.g., `hugo.yaml`, `params.yaml`)

### Categories

- `Computer`: Technology-related articles
- `What I Bought`: Product reviews
- `Photo`: Photography-related
- `Travel`: Travel logs

### Tags

- `hardware`, `software`, `apple`, `review`, `affiliate`, etc.
- Unified in lowercase
- Multiple words separated by hyphens as needed

## Image Management

- **Featured Images**: `featured.jpg` in each post directory
- **Article Images**: Placed in the same directory
- **Common Images**: Placed in `assets/img/` or `static/`

## Configuration File Roles

- `hugo.yaml`: Site basic configuration, build settings
- `params.yaml`: Theme-specific settings, layout configuration
- `menus.yaml`: Navigation menu structure
- `languages.yaml`: Multilingual settings
- `markup.yaml`: Markdown processing settings
