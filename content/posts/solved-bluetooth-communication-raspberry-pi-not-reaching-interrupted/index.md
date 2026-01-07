---
date: "2024-12-25 18:50:34+09:00"
tags:
  - "hardware"
  - "troubleshooting"
  - "review"
  - "affiliate"
  - "shotonnikon"
title: "[解決済み] ラズパイのBluetooth通信が届かない / 途切れる"
description: "Raspberry Pi 5 にSSDを付けると内蔵Bluetoothの通信品質が落ちたため、外付けBluetoothアダプター PLANEX BT-Micro4 を導入しました"
summary: "Raspberry Pi 5 にSSDを付けると内蔵Bluetoothの通信品質が落ちたため、外付けBluetoothアダプター PLANEX BT-Micro4 を導入しました"
categories:
  - "Computer"
  - "What I Bought"
---


Raspberry Pi 5 に [Crucial P3 Plus Gen4 NVMe SSD](https://www.crucial.jp/products/ssd/crucial-p3-plus-ssd) を付けたところ、ラズパイ5から遠いところに設置してある [SwitchBot Meter](https://www.switchbot.jp/products/switchbot-meter) と Home Assistant 経由のBluetooth通信がつながらなくなってしまいました。また、近くの [SwitchBot Bot](https://www.switchbot.jp/products/switchbot-bot) を操作したときも、何度もリトライしていることがログに残っていました。おそらくSSDを付けたことでノイズが増えて、頼りないラズパイ5内蔵Bluetoothに悪影響が出ているようです。


{{< article link="/blog/posts/bought-crucial-p3-plus-gen4-nvme-ssd/" >}}



Home Assistant の [Bluetooth Integration](https://www.home-assistant.io/integrations/bluetooth/) のページにはBluetooth通信の品質をLinuxで向上させるためのノウハウがまとまっていて参考になります。今回は手軽な外付けBluetoothアダプターを使用することにしました。Linuxドライバーの品質の関係もあり、やや古いCSR8510A10チップを使ったものが良さそうです。製品名もリストされていますが、日本で今でも入手できそうなのものは限られており、私は [PLANEX BT-Micro4](https://www.planex.co.jp/products/bt-micro4/) にしました。入手しやすい [TP-Link UB500](https://www.tp-link.com/jp/home-networking/computer-accessory/ub500/) / [UB400](https://www.tp-link.com/jp/home-networking/computer-accessory/ub400/) は未サポートアダプターにリストされているので注意が必要です。



## セットアップ



上記Integrationページで USB 3.0 ではなく USB 2.0 ポートに挿したほうが良いとあったので、ラズパイ5の USB 2.0 ポートに PLANEX BT-Micro4 を挿そうとしますが挿さりません……。どちらか、またはどちらもUSBポートの精度が悪いようです。上記ページで延長ケーブルを使って本体からBluetoothアダプターを離すことが推奨されていたこともあり、余っていた1mの USB 2.0 延長ケーブルを挟むことで接続しました。



`hciconfig`を実行すると、Ubuntu 24.04 でも問題なく自動認識されていました。`Bus: UART` というのが内蔵Bluetoothで、`Bus: USB` というのがUSB接続のもの、つまりBT-Micro4です。



```
tats@fox:~$ hciconfig  
hci1:   Type: Primary  Bus: UART  
        BD Address: 2C:CF:67:0F:F6:5F  ACL MTU: 1021:8  SCO MTU: 64:1  
        UP RUNNING  
        RX bytes:3715 acl:0 sco:0 events:390 errors:0  
        TX bytes:66963 acl:0 sco:0 commands:390 errors:0  
  
hci0:   Type: Primary  Bus: USB  
        BD Address: 00:1B:DC:E0:76:BB  ACL MTU: 310:10  SCO MTU: 64:8  
        UP RUNNING  
        RX bytes:648 acl:0 sco:0 events:41 errors:0  
        TX bytes:2168 acl:0 sco:0 commands:41 errors:0
```



`bluetoothctl list` では、どちらがデフォルトデバイスなのかが分かります。どうやら内蔵デバイスがデフォルトで使用されているようです。



```
tats@fox:~$ bluetoothctl list  
Controller 2C:CF:67:0F:F6:5F fox.rewse.jp #2 [default]  
Controller 00:1B:DC:E0:76:BB fox.rewse.jp
```



`bluetoothctl select` でデフォルトデバイスを変更できるはずなのですが、なぜか変更されません……。



```
tats@fox:~$ sudo bluetoothctl select 00:1B:DC:E0:76:BB  
Controller 00:1B:DC:E0:76:BB fox.rewse.jp [default]  
tats@fox:~$ bluetoothctl list  
Controller 2C:CF:67:0F:F6:5F fox.rewse.jp #2 [default]  
Controller 00:1B:DC:E0:76:BB fox.rewse.jp
```



Home Assistant の Bluetooth Integration で追加したデバイスを Home Assistant は使う気もしますが、内蔵デバイスを有効にしておく理由もないので、元からオフにすることにします。以下のようにconfig.txtに記述して再起動します。



```
tats@fox:~$ echo 'dtoverlay=disable-bt' | sudo tee -a /boot/firmware/config.txt  
dtoverlay=disable-bt  
tats@fox:~$ sudo reboot
```



起動してきたら再度`hcinconfig`を実行してみましょう。`Bus: USB` のみになり、内蔵デバイスが見えなくなりました。



```
tats@fox:~$ hciconfig  
hci0:   Type: Primary  Bus: USB  
        BD Address: 00:1B:DC:E0:76:BB  ACL MTU: 310:10  SCO MTU: 64:8  
        UP RUNNING  
        RX bytes:11823 acl:0 sco:0 events:386 errors:0  
        TX bytes:2192 acl:0 sco:0 commands:44 errors:0
```



結果、内蔵Bluetoothではつながらなかった遠くの SwitchBot Meter とも電波到達距離が長くなったことで問題なくつながるようになり、リトライがなくなったことで SwitchBot Bot も即座に反応するようになりました。ラズパイのBluetooth性能に困っている方は外付けアダプターを薦めます。



## まとめ



Raspberry Pi 5 にSSDを付けた後、内蔵Bluetoothの通信品質が落ち、デバイスとの接続に問題が出ました。対策として、外付けBluetoothアダプターの PLANEX BT-Micro4 を購入し、USB延長ケーブルで本体から離して設置、内蔵Bluetoothを無効化しました。



この結果、遠くのデバイスとつながり、操作も即座に反応するようになりました。ラズパイの内蔵Bluetoothでは通信品質が十分でない場合、外付けアダプターを使うことで改善できます。






{{< amazon asin="B0071TE1G2" title="PLANEX BT-Micro4" >}}
|  |  |
| --- | --- |
| ブランド | [PLANEX](https://www.planex.co.jp/) |
| 製品名 | [BT-Micro4](https://www.planex.co.jp/products/bt-micro4/) |
| 購入場所 | [ヨドバシカメラ](https://www.yodobashi.com/product-detail/100000001001472243/) |
| 購入価格 | 1,290円（- 129円相当ポイント還元） |
| 購入日 | 2024/12/06 |
