---
date: "2024-03-11 00:27:47+09:00"
tags:
  - "ubiquiti"
  - "hardware"
  - "review"
title: 'Ubiquiti UniFi Express レビュー: ネットワーク設定編'
description: "Ubiquiti UniFi Express のネットワーク設定方法を解説します。システム / Wi-Fi / ネットワーク / インターネット / VPN / セキュリティ / ルーティング / プロファイルなど、様々な設定画面について詳しく説明します"
summary: "Ubiquiti UniFi Express のネットワーク設定方法を解説します。システム / Wi-Fi / ネットワーク / インターネット / VPN / セキュリティ / ルーティング / プロファイルなど、様々な設定画面について詳しく説明します"
categories:
  - "Computer"
---

![](featured.png)

[Ubiquiti UniFi Express](https://ui.com/us/ja/cloud-gateways/express) (UX) はVPNとDPI (Deep Packet Inspection) を備えたWi-Fiメッシュルーターです。UniFiの中では最小の[ゲートウェイ](https://ui.com/us/ja/cloud-gateways)となっており、通常の家庭利用には十分な性能となっています。UniFiは法人用Wi-Fiシステムとして有名ですが、UniFi Express によって小規模環境にもさらに気軽に導入できるようになりました。この記事ではネットワーク設定について紹介したいと思います。ハードウェアと初期セットアップについては以下の記事を参照してください。



{{< article link="/blog/posts/ubiquiti-unifi-express-review-hardware-initial-setup/" showSummary=true compactSummary=true >}}



今回のレビューには UniFi OS 3.2.5 + UniFi Network 8.1.107 を使用しています。UniFi OS を3.2.5以上にアップデートすることでtransix回線 (DS-Lite) を利用した IPv4 over IPv6 IPoE（ネイティブ方式）に対応します。


![](ux-unifios-01.png)



上記のNetworkアプリケーションのアイコンを押すと UniFi Network の画面になります。いろいろ興味深いダッシュボードとなっていますが、今回はそのまま左にある歯車ボタンを押します。


![](ux-network-01.png)



ダッシュボードを含めたネットワーク監視については、以下の記事を参照してください。




[Ubiquiti Unifi Express Review Hardware Initial Setup](/blog/posts/ubiquiti-unifi-express-review-hardware-initial-setup/)




## システム



Systemから日本語に変更できるため、まずはこちらから見てみましょう。


![](ux-network-02.png)



〈更新〉タブでは、UniFiデバイスのファームウェアアップデートについて設定できます。UniFiデバイスは、万が一の場合は [Releases | Ubiquiti Community](https://community.ui.com/releases) に掲載されているURLを使って手動でダウングレードすることもできるので、私は自動更新しています。


![](ux-network-03.png)



〈バックアップ〉タブでは、UniFi Network の設定は自動で月次バックアップされています。週次や日次に変更することも可能です。


![](ux-network-04.png)



〈高度な〉タブでは最初から変更するようなものはありませんが、あるとしたら〈SNMPモニタリング〉と〈デバイスのSSH認証〉でしょうか。このSSH認証は UniFi Express に接続したアクセスポイントなどのUniFiデバイスにSSHログインするためのユーザー名やSSHキーです。


![](ux-network-05.png)



## Wi-Fi



〈Wi-Fi〉を見てみましょう。UniFi Express はコンソールモード（通常のモード）の場合、1バンドあたり3個のSSIDを作成できます。アクセスポイントモードの場合は1バンドあたり8個作成できます。


![](ux-network-06.png)



初期設定されているSSID（私の環境ではtango）を押すと以下のような画面になります。セキュリティプロトコルは〈WPA2/WPA3〉〈WPA3〉〈WPA2エンタープライズ〉〈WPA3エンタープライズ〉に変更することもできます。ゲスト用のネットワークを作成する場合は〈クライアントデバイスの分離〉をオンにしましょう。これにより、クライアント同士での通信ができなくなります。


![](ux-network-07.png)



ちなみに、一般的な家庭用ルーターでは2.4GHz専用のSSIDと5GHz専用のSSIDが別々に設定されているものが多いですが、UniFi Express のデフォルトのように、1個のSSIDにするのが[Appleのベストプラクティス](https://support.apple.com/ja-jp/HT202068)です。また、Wi-Fi 7 では複数バンドを束ねて通信できる Multi-Link Operation (MLO) 機能があるので、1個のSSIDで複数バンドに対応するのが時代の流れです。〈バンドステアリング〉がオンの場合、5GHzに対応しているクライアントは5GHzに優先的に接続されます。ただし、一部のIoT機器は2.4GHzと5GHzの両方に対応しているSSIDだと接続できなかったりするので、2.4GHzだけのSSIDを追加で作成するのも良いでしょう。



### ホットスポットポータル



〈ホットスポットポータル〉をオンにするとキャプティブポータルに対応させることができます。キャプティブポータルのロゴや文字は変更可能です。


![](ux-network-08.png)



デフォルトは認証なしですが、Facebookやパスワードだけでなく、[Stripe](https://stripe.com/jp)や[PayPal](https://www.paypal.com/jp/home)での支払いを要求することもできます。この時に無料枠を設けることもできます。バウチャーは、バウチャーの番号ごとに有効期限やデータ容量を設定することができます。


![](ux-network-11.png)



〈設定〉の〈承認アクセス〉の〈事前承認の許可〉に設定したホストにはキャプティブポータルなしでアクセスすることを可能にできます。


![](ux-network-12.png)



## ネットワーク



〈ネットワーク〉はLAN側の設定です。UniFiのVLANは独特ですが非常に分かりやすく、〈新しい仮想ネットワーク〉を作成するとVLANが切られます。このページでの設定はグローバル設定のため、すべてのネットワーク (VLAN)、スイッチに設定が適用されます。〈IGMPプロキシ〉が必要なIPTVを見る場合は、これを有効にします。


![](ux-network-13.png)



デフォルトのネットワーク (VLAN)、Defaultを押すと以下のような画面になります。〈自動スケールネットワーク〉はクライアントの数に応じて自動的にネットマスクを変更してくれます。〈コンテンツフィルタリング〉を有効にすると、悪意のあるサイトやアダルトサイトがブロックされます。また検索エンジンとYouTubeがセーフモードに設定されます。〈家族〉の場合は追加でVPNもブロックされます。


![](ux-network-15.png)



## インターネット



〈インターネット〉はWAN側の設定です。DS-Liteに対応したバージョンの場合、ここから設定できます。PPPoEにも対応しています。IPv6にはSLAACとDHCPv6の両方に対応しています。DS-Liteの詳しい設定については [IPv6 IPoE transix IPv4 (DS-Lite) の設定手順 | Ubiquiti UniFi | Ubiquiti Japan (UI Japan)](https://note.com/ui_japan/n/n3154ff641db5) を参照してください。


![](ux-network-16.png)



## VPN



〈テレポート〉はUniFi独自のVPN方式です。[WiFiman](https://apps.apple.com/jp/app/ubiquiti-wifiman/id1385561119)アプリをインストールしたmacOS / iOS / Androidであれば、このページで生成したリンクをクライアント側で1クリックするだけでVPNの設定が完了し、WiFimanからVPNを有効にすることができるようになります。ちなみに、Teleportは裏ではWireGuardを使用しています。


![](ux-network-17.png)



VPNサーバーはWireGuard / OpenVPN / L2TPに対応しています。WireGuardの〈クライアントを追加〉を押すと構成ファイルのダウンロードやQRコード表示ができるので、クライアントはこれを読むだけで設定が完了します。OpenVPNも同様に〈ダウンロード〉を押すと構成ファイルがダウンロードされます。


![](ux-network-18.png)



VPNクライアントはWireGuardとOpenVPNに対応しています。


![](ux-network-19.png)



サイト間VPNはOpenVPNとIPSecに対応しています。


![](ux-network-20.png)



AWSとサイト間VPNを組みたい場合は、以下の記事を参照してください。




https://rewse.jp/blog/how-build-site-vpn-ubiquiti-unifi-udm-se-aws




## セキュリティ



〈デバイス識別〉を有効にすると、クライアントがiPhoneなのか Nintendo Switch なのかなどを識別できるようになります。〈スマートフォン〉と言った種類別ではなく、（完璧ではないですが）製品レベルまで細かく識別できます。〈トラフィック識別〉を有効にすると、DPI (Deep Packet Inspection) によって、その通信がどのアプリによるものなのかを識別します。これによって、通信量が多いアプリを特定することができたり、後ほど設定するファイアウォールルールで、特定のアプリの通信だけをブロックしたりできます。



〈国の制限〉は国単位でのブロック / 許可を出力 / 入力個別に設定できます。たとえば自宅のサーバーに国内からしかアクセスしない場合は、〈日本〉〈許可〉〈入力〉にしておけば、その他の国からはアクセスできなくなります。詳しくは [UniFi Gateway - Country Restriction](https://help.ui.com/hc/en-us/articles/12567758783383-UniFi-Gateway-Country-Restriction) を参照してください。〈広告ブロック〉を有効にすると、広告関連のドメインがDNSレベルでブロックされます。詳しくは [UniFi Gateway - Ad Blocking](https://help.ui.com/hc/en-us/articles/9794438523799-UniFi-Gateway-Ad-Blocking) を参照してください。〈DNSシールド〉とは DNS over HTTPS (DoH) のことです。


![](ux-network-21.png)



Port Forwarding の設定項目は以下のとおりです。転送元ポートと転送先ポートを異なる値にすることもできますし、転送元ポートを複数指定や範囲指定することもできます。


![](ux-network-22.png)



〈トラフィックとファイアウォールルール〉では、デフォルトで以下のようなルールが設定されています。


![](ux-network-23.png)



〈エントリの作成〉を押すと〈シンプル〉または〈高度な〉設定ができます。まずは〈シンプル〉を見てましょう。こちらでは特定のアプリ / アプリグループ / ドメイン名 / IPアドレス / 地域 / インターネット / ローカルネットワークへのアクセスを制御できます。〈スケジュール〉は時間帯だけでなく、曜日を設定することもできます。〈送信元〉にはクライアント単位やネットワーク (VLAN) 単位で指定することができます。家庭利用ではペアレンタルコントールに使ったり、店舗利用ではオンラインゲームやメディアストリーミングサービスをアプリグループ単位で速度制限したりすることができます。


![](ux-network-24.png)



〈高度な〉設定は一般的なIPベースのものです。詳しくは [UniFi Gateway - Introduction to Firewall Rules](https://help.ui.com/hc/en-us/articles/115003173168-UniFi-Gateway-Introduction-to-Firewall-Rules) を参照してください。


![](ux-network-25.png)



## ルーティング



Policy-Based Routes では送信元（デバイス / ネットワーク）や送信先（ドメイン名 / IPアドレス / 地域）のルールでWANインターフェスを変更することができますが、UniFi Express はWANが1ポートしかないので意味はありません。UniFi Network はその他のゲートウェイにも使用されているので、その他のゲートウェイ用でしょう。


![](ux-network-26.png)



〈静的ルート〉では以下のような設定ができます。


![](ux-network-27.png)



OSPFにも対応してます。


![](ux-network-28.png)



## プロファイル



〈プロファイル〉からはEthernetポートの設定 / Wi-Fi速度制限 / RADIUS認証などの設定をプロファイルとして作成しておき、各ポートなどにプロファイルを適用することで、同じ設定をまとめて適用することができるようになります。また、複数のポートや複数のIPアドレスをグループ化して名前を付けておいて、グループ単位で適用することができるようになります。


![](ux-network-29.png)


![](ux-network-30.png)


![](ux-network-31.png)


![](ux-network-32.png)



## UniFiデバイス > UniFi Express > 設定



〈設定〉ではなく〈UniFiデバイス〉からWi-Fiのチャンネルやチャンネル幅、出力強度などを設定できます。〈チャネル幅〉が広いほど最大スループットは高くなりますが、干渉しやすくなるので、再送が増えて逆に実質スループットが下がる環境もあります。その場合はチャンネル幅を狭めましょう。[Appleのベストプラクティス](https://support.apple.com/ja-jp/HT202068)では、2.4GHzには20MHzが推奨されています。


![](ux-network-32-1.png)



また、フレッツ光にPPPoE接続しているときにLINEなどの一部の通信がうまくいかない場合は、〈MSSクランプ〉を〈カスタム〉に変更し、1414, 1400, 1258, 1215 などの値に徐々に小さくしてみてください。詳しくは [MTU/MSS問題 - Ubiquiti（ユビキティ）日本公式コミュニティ - Facebook](https://www.facebook.com/groups/uijapan/learning_content/?filter=167949146143924&post=625695289534534) をご覧ください（参照にはコミュニティへの参加が必要）。



## クライアントデバイス > 設定



〈クライアントデバイス〉から1個のデバイスを選び、〈設定〉を開くと〈固定IPアドレス〉の設定が可能です。また、〈ローカルDNSレコード〉を設定することで、名前でアクセスできるようになります。〈注意事項〉は何ごとかと思うでしょうが、英語だとNoteなのでメモ欄です。


![](ux-network-33.png)



## 設定時の参考資料



設定について悩んだ場合は [Network – Ubiquiti Help Center](https://help.ui.com/hc/en-us/sections/6582310816535-Network) に参考資料があるかもしれません。



## まとめ



Ubiquiti UniFi Express のネットワーク設定については以上となります。システム設定ではデバイスの言語設定 / ファームウェア更新 / バックアップ設定などを行えます。Wi-Fi設定ではSSIDの設定 / セキュリティプロトコル / クライアントデバイスの分離などが可能です。ホットスポットポータルの設定では、キャプティブポータルの有効化 / カスタマイズ / 認証方式の設定ができます。



ネットワーク設定ではVLAN設定 / IGMPプロキシ / コンテンツフィルタリングなどを行えます。インターネット設定ではDS-Lite / PPPoE / IPv6に対応できます。VPN設定ではTeleport / WireGuard / OpenVPN / L2TPなどの設定が可能です。セキュリティ設定ではデバイス識別 / トラフィック識別 / 国別制限 / 広告ブロック / ポート開放 / ファイアウォールルールの設定ができます。その他、ルーティングやプロファイルの設定についても説明しました。
