---
date: "2022-05-30 17:52:38+09:00"
tags:
  - "shotonnikon"
  - "ubiquiti"
  - "hardware"
  - "review"
title: "Ubiquiti UniFi Access Point U6 Lite を購入"
description: "我が家ではWi-Fi接続している端末が50台ほどあるため、同時接続数300以上に対応している Ubiquiti UniFi Access Point WiFi 6 Lite (U6-Lite) に変更しました"
summary: "我が家ではWi-Fi接続している端末が50台ほどあるため、同時接続数300以上に対応している Ubiquiti UniFi Access Point WiFi 6 Lite (U6-Lite) に変更しました"
categories:
  - "Computer"
  - "What I Bought"
---

![](featured.jpg)

我が家ではWi-Fi接続している端末が50台ほどあるため、家庭用Wi-Fiルーターでは力不足です。また、Wi-Fiは応答不能になると影響が大きい重要インフラのため、我が家では企業用Wi-Fiアクセスポイントを2台導入して冗長構成にしています。今回、これを同時クライアント数300以上に対応している Ubiquiti UniFi Access Point U6 Lite (U6-Lite) に変更しました。



## 企業用Wi-Fiアクセスポイントについて



一部の家庭用Wi-FiルーターはメッシュWi-Fiに対応していますが、メッシュWi-Fiの場合は2つの機器に親子関係があるため、親（コントローラー）が応答不能になると子（エージェント）も使えなくなります。一方で、一般的な企業用Wi-Fiアクセスポイントは親子関係がなく、2つのアクセスポイントに依存関係がないため、冗長構成なります。ただし、メッシュWi-Fiの場合は子（エージェント）にはLANケーブルを挿す必要がないですが、複数台Wi-Fiアクセスポイントの場合はすべてにLANケーブルを挿す必要があります（一部のWi-FiアクセスポイントはメッシュWi-Fiにも対応しているので、LANケーブルがないところだけをメッシュWi-Fiにすることもできます）。



{{< mermaid >}}
flowchart TD
  hgw[ホームゲートウェイ] -- 有線 --- mesh1[Wi-Fiコントローラー] -. 無線 -.- mesh2[Wi-Fiエージェント]
  mesh1 -. 無線 -.- mesh3[Wi-Fiエージェント]
{{< /mermaid >}}



メッシュWi-Fiは直列につながっているため、Wi-Fiコントローラーが単一障害点になっている



{{< mermaid >}}
flowchart TD
  hwg[ホームゲートウェイ] -- 有線 --- ap1[Wi-Fiアクセスポイント]
  hwg[ホームゲートウェイ] -- 有線 --- ap2[Wi-Fiアクセスポイント]
  ap2[Wi-Fiアクセスポイント] -. 無線 -.- ap3[Wi-Fiアクセスポイント]
{{< /mermaid >}}



Wi-Fiアクセスポイントは並列につながっているため、Wi-Fiアクセスポイントは単一障害点にならない。また、一部の機種ではメッシュWi-Fiにも対応している



メッシュWi-Fi非対応の家庭用Wi-Fiルーターは [802.11k, 802.11r, 802.11v](https://support.apple.com/ja-jp/HT202628) にも対応していないため、複数台導入したとしてもローミングが行われません。Wi-Fiアクセスポイントと端末の両方がローミングに対応していると、たとえばiPhoneを1階で使いながら2階に移動した場合、シームレスに接続先のWi-Fiアクセスポイントが切り替わります。このように企業用Wi-Fiアクセスポイントは複数台導入されることが前提になっており、協調動作するようになっています。



注意点として、アクセスポイントと呼ばれる製品にはルーター機能がありません。そのため、ルーターを別途用意する必要があります。私はルーター専用機として [YAMAHA RTX1200](https://network.yamaha.com/products/routers/rtx1200/) を使っていますが、ホームゲートウェイ (HGW) があるならば、それのルーター機能でも大丈夫です。我が家では以下のような構成になっています。



{{< mermaid >}}
flowchart TD
    I([auひかり]) --- ONU[ONU: au H06NU5]
    ONU --- HGW[HGW: au Aterm BL900HW]
    HGW --- Router[Router: YAMAHA RTX1200]
    Router --- WAP1[Wi-Fi AP: Ubiquiti U6-Lite]
    Router --- WAP2[Wi-Fi AP: Ubiquiti U6-Lite]
{{< /mermaid >}}



もう一つの注意点として、企業用Wi-Fiアクセスポイントは複数台導入されることが前提なので、電波干渉を防ぐために、1台の出力は家庭用に比べて必ずしも強いわけではありません。



## Ubiquiti UniFi について



今までは Wi-Fi 5 対応でクラウド管理できる [NETGEAR WAC510](https://www.netgear.com/jp/business/wifi/access-points/wac510/) を使っていたのですが、Wi-Fi 6 対応でクラウド管理できる[WAX610](https://www.netgear.com/jp/business/wifi/access-points/wax610/)は24,000円程度して、2台導入するにはそれなりの投資で躊躇していました。また、いくつかの不満がありました。



1. たまに一部の端末が常にアソシエーションに失敗するようになり、WAC510の手動再起動が必要になる
2. Watchdogで自己再起動するものの、2カ月に一回くらい応答不能から自己復旧している
3. 購入当初はできたSSH接続が新ファームウェアではできなくなった
4. 購入当初はあったベンダーMIBに新ファームウェアが対応しなくなった
5. ログから何が起きているのか把握しにくい
6. Unable to apply RF settings という謎のエラー通知が、1週間に一回くらい送られるようになった



2の挙動は良いのか悪いのか微妙なところですが、1が問題です。また、1が発生すると、端末がもう片方のアクセスポイントに接続先を切り替えることもないため、二重化が機能しません。[Wireless Access Point Competitive - Cisco](https://web.archive.org/web/20220719151633/https://www.cisco.com/c/en/us/solutions/small-business/wireless/wireless-competitive-comparison.html) によると、Ciscoは[Ubiquiti](https://ui.com/jp/ja) / [Aruba](https://www.arubanetworks.com/ja/) / [NETGEAR](https://www.netgear.com/jp/) / [D-Link](https://www.dlink-jp.com/)を中小企業向けWi-Fiソリューションにおける競合と考えており、Cisco / Aruba / D-Linkは個人での入手が簡単ではないため、Ubiquitiに変更することにしました。



Ubiquitiは価格競争力が高く、たとえばAX5300の[U6-Pro](https://jp.store.ui.com/collections/unifi-network-wireless/products/unifi-ap6-professional)が18,950円です。AX3600の [NETGEAR WAX620](https://www.netgear.com/jp/business/wifi/access-points/wax620/) が38,000円、AX6000の[WAX630](https://www.netgear.com/jp/business/wifi/access-points/wax630/)が49,000円なので、U6-Proはかなり安いです。ただし、残念ながらU6-Proは現在品切れのため、AX1500のU6-Liteを12,591円で2台購入しました。また、NETGEARだと[端末1台あたり年間1,125円](https://www.netgear.com/jp/business/services/insight/subscription/)掛かるサブスクリプション費用が、Ubiquitiはまったく掛からない点も特徴です。



ひとつ気をつける必要がある点は、Ubiquiti UniFi では別途コントローラーを用意する必要がある点です。コントローラーがなくても [UniFi Network](https://apps.apple.com/app/unifi-network/id1057750338) アプリから設定できなくはないのですが、SSID / パスワード / WPA2の有効化しか設定できないため、ほとんどの場合は機能不足でしょう。


![](IMG_1959.png)

コントローラーがない場合に UniFi Network Mobile から設定できる項目




コントローラーには [UniFi OS Console](https://ui.com/jp/ja/cloud-gateways) が推奨されています。UniFi OS Cosole にはいくつかの製品がありますが、家庭利用には [Dream Router](https://ui.com/us/ja/cloud-gateways/wifi-integrated/dream-router) という、UniFi OS + ルーター + スイッチ + Wi-Fiアクセスポイントなオールインワン製品をゲートウェイとして使用することが推奨されています。これらのUniFiの概要を知るには [Ubiquiti | UniFi | UniFI OS ハードウェア・プラットフォーム](https://ui.com/jp/ja/cloud-gateways) を参照すると良いでしょう。ただし、手間を掛ければ Ubuntu / Debian / Windows / macOS に無償配布されている [UniFi Network Application](https://www.ui.com/download/unifi) をインストールして、Self-Hosted環境を構築することもできます。私は Ubuntu 20.04 がインストールされた [Raspberry Pi 4 Model B](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/) に構築し、その後、Amazon EC2 に移行しました。




[Wp Content](/blog/posts/wp-content/)




## U6-Liteについて



UniFi Network Application からはWi-Fiについては以下のような項目が設定できます。私に必要な機能は全てありました。U6-Liteでは、SSIDは2.4GHz / 5GHzそれぞれに8個作れます。


[![](a9cbdb22-3d16-4cbb-b836-3a458c2bd1af.png)](/blog/images/2022/05/a9cbdb22-3d16-4cbb-b836-3a458c2bd1af.png)

画像をクリックすると別ウインドウで開きます




システム全体の設定は以下のような項目です。


[![](7df4f193-045b-487c-9066-75a9c79f0419.png)](/blog/images/2022/05/7df4f193-045b-487c-9066-75a9c79f0419.png)

画像をクリックすると別ウインドウで開きます




SSHでU6-Liteにログインしてみましょう。



```
BusyBox v1.25.1 () built-in shell (ash)


  ___ ___      .__________.__
 |   |   |____ |__\_  ____/__|
 |   |   /    \|  ||  __) |  |   (c) 2010-2022
 |   |  |   |  \  ||  \   |  |   Ubiquiti Inc.
 |______|___|  /__||__/   |__|
            |_/                  https://www.ui.com

      Welcome to UniFi U6-Lite!

********************************* NOTICE **********************************
* By logging in to, accessing, or using any Ubiquiti product, you are     *
* signifying that you have read our Terms of Service (ToS) and End User   *
* License Agreement (EULA), understand their terms, and agree to be       *
* fully bound to them. The use of SSH (Secure Shell) can potentially      *
* harm Ubiquiti devices and result in lost access to them and their data. *
* By proceeding, you acknowledge that the use of SSH to modify device(s)  *
* outside of their normal operational scope, or in any manner             *
* inconsistent with the ToS or EULA, will permanently and irrevocably     *
* void any applicable warranty.                                           *
***************************************************************************

xray-liv-BZ.6.0.19#
```



OSはLEDE（現[OpenWrt](https://openwrt.org/)）ベースのようです。



```
xray-liv-BZ.6.0.19# cat /etc/os-release
NAME="LEDE"
VERSION="17.01.6, Reboot"
ID="lede"
ID_LIKE="lede openwrt"
PRETTY_NAME="LEDE Reboot 17.01.6"
VERSION_ID="17.01.6"
HOME_URL="http://lede-project.org/"
BUG_URL="http://bugs.lede-project.org/"
SUPPORT_URL="http://forum.lede-project.org/"
BUILD_ID="r3979-2252731af4"
LEDE_BOARD="mtk/mt7621"
LEDE_ARCH="mipsel_24kc"
LEDE_TAINTS="no-all mklibs busybox"
LEDE_DEVICE_MANUFACTURER="LEDE"
LEDE_DEVICE_MANUFACTURER_URL="http://lede-project.org/"
LEDE_DEVICE_PRODUCT="Generic"
LEDE_DEVICE_REVISION="v0"
LEDE_RELEASE="LEDE Reboot 17.01.6 r3979-2252731af4"
```



CPUは4論理コアの MediaTek MT7621 です。



```
xray-liv-BZ.6.0.19# cat /proc/cpuinfo | head -20
system type             : MediaTek MT7621 ver:1 eco:3
machine                 : Ubiquiti Networks, Inc. U6-Lite
processor               : 0
cpu model               : MIPS 1004Kc V2.15
BogoMIPS                : 586.13
wait instruction        : yes
microsecond timers      : yes
tlb_entries             : 32
extra interrupt vector  : yes
hardware watchpoint     : yes, count: 4, address/irw mask: [0x0ffc, 0x0ffc, 0x0ffb, 0x0ffb]
isa                     : mips1 mips2 mips32r1 mips32r2
ASEs implemented        : mips16 dsp mt
shadow register sets    : 1
kscratch registers      : 0
package                 : 0
core                    : 0
VCED exceptions         : not available
VCEI exceptions         : not available
VPE                     : 0

xray-liv-BZ.6.0.19# cat /proc/cpuinfo | grep MediaTek | wc -l
4
```



メモリーは256MBです。



```
xray-liv-BZ.6.0.19# cat /proc/meminfo | head -5
MemTotal:         253744 kB
MemFree:          113424 kB
MemAvailable:     158580 kB
Buffers:               0 kB
Cached:            56596 kB
```



U6-Liteは 802.3af PoE からしか給電できません。私は [NETGEAR GS308P](https://www.jp.netgear.com/support/product/gs308p.aspx) から給電していますが、PoE対応スイッチがない場合は [Ubiquiti PoE Injector, 802.3af (U-POE-af)](https://jp.store.ui.com/collections/unifi-accessories/products/u-poe-af) のようなPoEインジェクターが必要です。



## まとめ



企業用Wi-Fiアクセスポイントは親子関係がなく、複数のアクセスポイントに依存関係がないため、冗長構成を組めます。企業用Wi-Fiアクセスポイントの中でUbiquitiは価格競争力が高く、Wi-Fi 6 に対応したU6-Liteを12,591円で2台購入しました。Ubiquiti UniFi ソリューションでは別途コントローラーを用意する必要があるため、私は UniFi Network Application を Ubuntu 20.04 がインストールされた Raspberry Pi 4 Model B に構築しました。




|  |  |
| --- | --- |
| ブランド | [Ubiquiti](https://ui.com/jp/ja) |
| 製品名 | UniFi Access Point U6 Lite |
| 型番 | U6-Lite |
| 販売店 | Ubiquiti |
| 支払金額 | 12,591円。送料無料 |
| 購入日 | 2022-05-17 |