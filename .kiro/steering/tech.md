# Technology Stack

## Build System

- **Static Site Generator**: Hugo
- **Theme**: Blowfish (Tailwind CSS based)
- **Configuration Format**: YAML
- **Content Format**: Markdown

## Key Technologies

- **Frontend**: Hugo + Blowfish theme
- **Styling**: Tailwind CSS (included in theme)
- **Image Optimization**: pyvips
- **Search Functionality**: Enabled
- **Multilingual Support**: Japanese as default, English also configured
- **SEO**: Structured data, sitemap, robots.txt support

## Commonly Used Commands

### Development and Build

```bash
# Start development server
hugo server

# Start development server (including drafts)
hugo server -D

# Production build
hugo

# Production build (including drafts)
hugo -D
```

### Content Creation

```bash
# Create new post
hugo new posts/[post-name]/index.md

# Create new page
hugo new [page-name]/index.md
```

### Image Optimization

```bash
# Process unprocessed images
uv run scripts/optimize_images.py

# Process specific path only
uv run scripts/optimize_images.py --path content/posts/new-article/

# Force reprocessing
uv run scripts/optimize_images.py --force

# Dry run to check targets without execution
uv run scripts/optimize_images.py --dry-run
```

## Configuration Files

- `config/_default/hugo.yaml`: Main configuration
- `config/_default/params.yaml`: Theme parameters
- `config/_default/menus.yaml`: Navigation settings
- `config/_default/languages.yaml`: Multilingual settings
- `config/_default/markup.yaml`: Markdown settings

## Deployment

- Development base URL: `http://localhost:1313/`
- Production base URL: `https://blog.rewse.jp/`
- AWS Amplify App ID: `d8gzy6xdskncg`

### AWS CLI Profile

When using AWS CLI, you MUST use the `hugo` profile.

```bash
aws <command> --profile hugo | cat
```

### Retrieving Amplify Build Logs

When accessing Amplify build logs, you MUST to use `curl` command. `webFetch` tool does not support signed URLs.

```bash
# 1. Get log URL from job information
aws amplify get-job --app-id d8gzy6xdskncg --branch-name main --job-id <JOB_ID> --query "job.steps[0].logUrl" --output text

# 2. Retrieve logs with curl
curl -s "<LOG_URL>"
```

## Legacy Blog

- The legacy blog was running on WordPress but has been migrated to Hugo
- The legacy blog was published at https://rewse.jp/blog/
- All articles from the legacy blog are exported as XML in the exported/ directory

## Hugo Template Debugging

You MUST use `warnf` for template debugging. HTML comments (`<!-- -->`) are removed by Hugo's minify settings. This will be output to the console as `WARN` during build.

```go
{{ warnf "[DEBUG] variable=%v" $variable }}
```

## Amplify Troubleshooting

### amplify.yml YAML Syntax

- Echo commands containing colons (`:`) are misinterpreted by the YAML parser as key-value separators, so replace them with `->` or similar
- Avoid multi-line commands (`|`) and use retry format with `||` instead

### Cache Path Specification

- Specify cache paths as relative paths (e.g., `static/img/optimized`)
- Do not use absolute paths containing `${PWD}` as they change with each build
- Wildcards (`**/*`) are unnecessary; just the directory name is sufficient

## Custom Build Image

A custom Docker image with libvips and AVIF support is used for Amplify builds.

- **ECR Public**: `public.ecr.aws/v5r5z4u0/amplify-hugo-vips`
- **Base image**: Ubuntu 24.04
- **Key packages**: libvips, libheif (AVIF), rav1e (AV1), Python 3.12, uv

### Rebuilding the Image

Amplify runs on x86_64, so you MUST specify `--platform linux/amd64` when building on Apple Silicon.

```bash
# Check current tag
aws amplify get-app --app-id d8gzy6xdskncg --profile hugo --query "app.environmentVariables._CUSTOM_IMAGE" --output text

# Build (increment tag from current)
podman build --no-cache --platform linux/amd64 -t public.ecr.aws/v5r5z4u0/amplify-hugo-vips:<TAG> .

# Login to ECR Public (us-east-1 required)
aws ecr-public get-login-password --region us-east-1 --profile hugo | podman login --username AWS --password-stdin public.ecr.aws

# Push
podman push public.ecr.aws/v5r5z4u0/amplify-hugo-vips:<TAG>

# Update Amplify environment variable
aws amplify update-app --app-id d8gzy6xdskncg --profile hugo --environment-variables "_BUILD_TIMEOUT=60,_CUSTOM_IMAGE=public.ecr.aws/v5r5z4u0/amplify-hugo-vips:<TAG>"
```
