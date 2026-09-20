# Project guidelines

## Content

- Write public content primarily in Japanese.
- Store each post as `content/posts/<kebab-case-slug>/index.md`, with `featured.jpg` and article images in the same directory.
- Use descriptive image names. Write tags in lowercase and separate multiple words with hyphens.
- Use existing category names where applicable, including `Computer`, `Photo`, `Travel`, and `What I Bought`.

## Images

Run `uv run scripts/optimize_images.py` after adding or changing article images. Use `--path <post-directory>` to limit processing, `--dry-run` to inspect targets, and `--force` only when reprocessing is required.

## Hugo and theme

- Run `hugo` after changes that can affect rendering or configuration.
- The Blowfish theme is a Git submodule. Before updating it, review its release notes; afterward, compare files under `layouts/` with their theme counterparts and run `hugo`.
- Use `warnf` for Hugo template debugging because minification removes HTML comments.

## AWS Amplify

- Use the AWS CLI profile `hugo` for this project.
- The Amplify app ID is `d8gzy6xdskncg`; the production URL is `https://blog.rewse.jp/`.
- Fetch Amplify build logs with `curl` from the signed `logUrl` returned by `aws amplify get-job`; generic web fetchers may not support the signed URL.
- In `amplify.yml`, avoid colons in unquoted echo commands and YAML multiline commands. Use relative cache paths without `${PWD}` or unnecessary wildcards.
- The custom build image is `public.ecr.aws/v5r5z4u0/amplify-hugo-vips`. Amplify runs on x86_64, so build the image with `container build --platform linux/amd64` on Apple Silicon. ECR Public authentication must use `us-east-1`.
