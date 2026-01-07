---
date: "2024-12-23 21:50:50+09:00"
tags:
  - "itemonamazon"
  - "shotonnikon"
  - "review"
  - "affiliate"
title: "Anker USB-C Hub (14-in-1, Triple display) を購入"
description: "モニターやUSB機器をつなぐために Anker USB-C Hub (14-in-1, Triple display) を購入しました。4K 60Hz出力とLANに対応しています"
summary: "モニターやUSB機器をつなぐために Anker USB-C Hub (14-in-1, Triple display) を購入しました。4K 60Hz出力とLANに対応しています"
categories:
  - "Computer"
  - "What I Bought"
---


会社の MacBook Pro をモニターやUSB機器につなぐために [HP Thunderbolt3 Dock 120W G2](https://jp.ext.hp.com/accessories/business/thunderbolt3_120w_g2/) を使っていたのですが、モニターの信号やLANケーブルの通信が一日に数秒程度切れるようになったため、[Anker USB-C Hub (14-in-1, Triple display)](https://www.ankerjapan.com/products/a8389) に買い替えました。



私が必要なポートは以下のものでした。比較的シンプルな要件ですが、4K 60Hz での画面出力ができてLANポートの付いているAnkerで一番安いUSBハブ / ドッキングステーションがこれでした。14ポートもいらなかったのですが。



- 65W以上の USB-C PD 給電
- 4K 60Hz での画面出力。できればDisplayPort
- 1Gbps LANポート



AppleシリコンMacはHDMI接続するとカラーフォーマットがYUVリミテッドレンジになってしまうので [1](#a52be74b-b965-4a81-8b70-09611c818a85)、DisplayPortのほうが画質が良くなります。しかし、DisplayPortを必須にすると急に高くなってしまい、会社のMacなので画像編集するわけでもないので、そこは諦めました。



USBチップは Genesys Logic (05e3:0626) で、USB 3.0 (5Gbps) で接続されます。カードリーダーも Genesys Logic (05e3:0749) で、LANポートはRealtek RTL8153 (0bda:8153) でした。Macは机上、このUSBハブは机の下に置きたかったので、余っていた [Cable Matters USB-C Extension Cable](https://www.cablematters.com/pc-1639-188-usb-c-extension-cable.aspx) で延長しました。



一点気になるのは、以下のように [Cable Matters 4-Port USB 3.0 Switch with Remote Control](https://www.cablematters.com/pc-1266-178-4-port-usb-30-switch-with-remote-control.aspx) と [Anker Ultra Slim 4-Port USB 3.0 Data Hub](https://www.ankerjapan.com/products/a7516) を数珠つなぎした先に [Audioengine A2+ Home Music System w/ Bluetooth aptX](https://audioengine.com/shop/wirelessspeakers/a2-wireless-computer-speakers/) スピーカーをつなぐと認識しませんでした。



{{< mermaid >}}
flowchart Mac---Anker1[Anker USB-C Hub 14-in-1, Triple display]
  Anker1---CM[Cable Matters 4-Port USB 3.0 Switch]
  CM---Anker2[Anker Ultra Slim 4-Port USB 3.0 Data Hub]
  Anker2---AE[Audioengine A2+]
{{< /mermaid >}}



以下のように1個手前に接続したところ、問題なく認識するようになりました。このような問題を起こしているのは Audioengine A2+ のみなので、どちらの問題なのか分かりません。



{{< mermaid >}}
flowchart Mac---Anker1[Anker USB-C Hub 14-in-1, Triple display]
  Anker1---CM[Cable Matters 4-Port USB 3.0 Switch]
  CM---AE[Audioengine A2+]
  CM---Anker2[Anker Ultra Slim 4-Port USB 3.0 Data Hub]
{{< /mermaid >}}





|  |  |
| --- | --- |
| ブランド | [Anker](https://www.ankerjapan.com/) |
| 製品名 | [USB-C Hub (14-in-1, Triple display)](https://www.ankerjapan.com/products/a8389) |
| 型番 | A83890A1 |
| 購入先 | [Amazon](https://amzn.to/40hy9kt) |
| 購入価格 | 6,990円 |
| 購入日 | 2024-11-27 |
