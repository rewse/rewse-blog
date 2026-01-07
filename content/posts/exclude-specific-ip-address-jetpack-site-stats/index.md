---
date: "2022-02-01 23:57:38+09:00"
tags:
  - "software"
  - "linux"
title: "Jetpackのサイト統計情報から特定のIPアドレスを除外する方法"
description: "Jetpack 10.6 で特定のIPアドレスからのアクセスをサイト統計でカウントしないようにするフィルターが追加されました"
summary: "Jetpack 10.6 で特定のIPアドレスからのアクセスをサイト統計でカウントしないようにするフィルターが追加されました"
categories:
  - "Computer"
---

![](featured.jpg)

Wordpressにさまざまな機能を追加してくれるプラグインである[Jetpack](https://ja.jetpack.com/)、その中でもサイト統計情報機能は人気です。従来のJetpackでも管理者などのログインしているユーザーをサイト統計情報でカウントしないことはできましたが、Jetpack 10.6 で特定のIPアドレスからのアクセスをサイト統計情報でカウントしないようにするフィルターが追加されました。これによって、例えば動作確認したい端末全てでログインする必要がなくなりますし、特定のボットから大量アクセスされている場合に、そのボットからのアクセスをサイト統計から除外することができます。


> Stats: add new filter allowing site owners to exclude IP addresses from being tracked in stats.
>
> [Changelog | Jetpack – WP Security, Backup, Speed, & Growth – WordPress plugin | WordPress.org](https://wordpress.org/plugins/jetpack/#developers)



しかし、この追加されたフィルターの設定方法が見当たらなかったので、こちらに記載しておきます。



## 設定方法



Jetpackが10.6以上であることを確認し、外観 > テーマファイルエディター > functions.php に以下のフィルターを追加します。`$excluded_ips[]` には除外したいIPアドレスを指定します。



functions.php



```
add_filter(
    'jetpack_stats_excluded_ips',
    function ( $excluded_ips ) {
       $excluded_ips[] = '124.213.127.nnn';
       return $excluded_ips;
    }
);
```



## 確認方法



ログインしていない状態で設定したIPアドレスからアクセスし、ソースコードを表示します。ソースコードに `'https://stats.wp.com/e-nnnnnn.js'` が含まれていなければ、そのアクセスはサイト統計から除外されています。



## 参考



[Stats: add filter allowing folks to exclude IPs from tracking by jeherve · Pull Request #22269 · Automattic/jetpack](https://github.com/Automattic/jetpack/pull/22269)