---
date: 2023-03-21 11:26:22+09:00
tags:
  - troubleshooting
title: '[解決済み] BenQ SW271 が「BenQディスプレイのUSBケーブルがコンピュータに接続されていることを確認してください」エラー'
description: "BenQ SW271 が認識されなくなった問題を解決しました。USB-CとUSB-Bの両方にケーブルを差した状態だとUSB-Bが動作しないという制限が原因でした"
summary: "BenQ SW271 が認識されなくなった問題を解決しました。USB-CとUSB-Bの両方にケーブルを差した状態だとUSB-Bが動作しないという制限が原因でした"
categories:
  - "Computer"
---

![](featured.jpg)

[Palette Master Element](https://www.benq.com/ja-jp/monitor/software/palette-master-element.html) が「BenQディスプレイのUSBケーブルがコンピュータに接続されていることを確認してください」エラーで [BenQ SW271](https://www.benq.com/ja-jp/business/monitor/sw271.html) を認識しない問題が発生していました。この問題は、ほかのMac / PCに接続しても解決せず、USBケーブルを交換しても解決しませんでした。そのため、SW271自体が故障したと判断し、ベンキューサポートセンターに修理依頼を出したところ、まさかの「再現せず」の回答でした。


![](mak-sure-your-benq-display-usb-cable-connected-to-your-computer.png)



しかし、ついに原因が判明しました。



## 解決方法



1. SW271のUSB-Cポートに刺さっているUSBケーブルを抜く



私はSW271のDisplayPortとUSB-Bポートから Mac Studio につなぎ、同時にUSB-Cポートから MacBook Pro につないでいました。しかし、どうやらSW271はUSB-Cポートを使用しているとUSB-Bポートは動作しない仕様のようで、USB-Cポートからケーブルを抜いたらUSB-Bポート側を認識するようになりました。


![](benq-sw271-connectivity.jpg)