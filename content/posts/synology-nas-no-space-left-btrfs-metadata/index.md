---
title: "[解決済み] Synology NAS で容量に余裕があるのに「No space left on device」エラーが発生"
date: "2025-11-02T01:18:00+09:00"
aliases:
  - /blog/synology-nas-no-space-left-btrfs-metadata/
tags:
  - "troubleshooting"
categories:
  - "Computer"
description: "Synology NAS でBtrfsファイルシステムのメタデータ領域不足により発生した「No space left on device」エラーの原因調査と解決方法について"
summary: "チャンクのバランスを行って割当て可能なチャンクを増やし、不要なバックアップセットを削除して領域を解放することで、メタデータ領域不足による書き込みエラーを解決しました"
externalUrl: "https://zenn.dev/rewse/articles/synology-nas-no-space-left-btrfs-metadata"
featureimage: "/img/fireflies.svg"
---
