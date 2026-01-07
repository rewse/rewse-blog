---
date: "2022-07-27 20:42:10+09:00"
tags:
  - "software"
  - "ubiquiti"
  - "linux"
title: "Ubiquiti UniFi Network Application をラズパイにインストール"
description: "この記事では Raspberry Pi 4 Model B に UniFi Network Application を構築してコントローラーにする方法を紹介します"
summary: "この記事では Raspberry Pi 4 Model B に UniFi Network Application を構築してコントローラーにする方法を紹介します"
categories:
  - "Computer"
---

![](featured.png)

[Ubiquiti](https://ui.com/jp/ja) UniFi は別途コントローラーを用意する必要があります。コントローラーには [UniFi OS Cloud Gateway](https://ui.com/jp/ja/cloud-gateways) が推奨されていますが、手間を掛ければ Ubuntu / Debian / Windows / macOS に無償配布されている [UniFi Network Application](https://www.ui.com/download/unifi) をインストールして、Self-Hosted環境を構築することもできます。Ubuntu / Debian はx86\_64のみがサポートされていますが、この記事ではARMである [Raspberry Pi 4 Model B](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/) に構築する方法を紹介します。



## システム要件



システム要件は [UniFi Network - Self-Hosting your UniFi Network Without a Console (Advanced) – Ubiquiti Support and Help Center](https://help.ui.com/hc/en-us/articles/360012282453-UniFi-Network-Self-Hosting-your-UniFi-Network-Without-a-Console-Advanced-) に記載されています。



- Ubuntu Desktop / Server 16.04; Debian 9 "Stretch"
- CPU: x86-64 Processor (Intel / AMD x64 Processors)
- RAM: 2GB
- Network: 100Mbps Wired Ethernet
- HDD: Minimum 10GB free (20GB or more preferred)
- Java: Java Runtime Environment (JRE) 8
- MongoDB: version 3.2 or later



私の Raspberry Pi 4 Model B はメモリー8GBで、Ubuntu 20.04 がインストールされているので、CPUアーキテクチャ以外は要件を満たした状態です。私は未確認ですが、Raspberry Pi OS (Raspbian) でも動作するようです。



## インストール



APTの依存パッケージ解決に任せるとopenjdk-17-jre-headlessがインストールされてしまいますが、UniFi Network Application は JRE 8 である必要があります。そのため、事前に JRE 8 と関連パッケージだけインストールしておきます。



```
tats@fox:~$ sudo apt install openjdk-8-jre-headless jsvc libcommons-daemon-java
```



UbiquitiはAPTリポジトリも提供していますが、x86\_64しか対応していません。そのため、ARMであるラズパイの場合は手動でインストールおよびアップデートを行う必要があります。UniFi Network Application (unifi\_sysvinit\_all.deb) の最新バージョンのURLは [Ubiquiti - Downloads](https://www.ui.com/download/unifi) を参考にすると良いでしょう。また、`apt install -f` によってMongoDBなどの依存パッケージがインストールされます。



```
tats@fox:~$ curl -O https://dl.ui.com/unifi/7.1.66/unifi_sysvinit_all.deb
tats@fox:~$ sudo dpkg -i unifi_sysvinit_all.deb
tats@fox:~$ sudo apt install -f
```



UniFi Network Application が動作していることを確認しましょう。



```
tats@fox:~$ systemctl status unifi
● unifi.service - unifi
     Loaded: loaded (/lib/systemd/system/unifi.service; enabled; vendor preset: enabled)
     Active: active (running) since Wed 2022-06-22 11:07:32 JST; 1 weeks 1 days ago
   Main PID: 1100 (jsvc)
      Tasks: 122 (limit: 4435)
     CGroup: /system.slice/unifi.service
```



`https://<hostname_of_raspberrypi>:8443/` にアクセスするとSSL証明書の警告が出るものの、これで Unifi Network Application にアクセスできます。



## SSL証明書の設定



SSL証明書の警告を消すためにSSL証明書を設定します。この記事ではSSL証明書の取得方法は省きますが、Let’s Encrypt のSSL証明書を使っています。



[UniFi Linux Utils](https://github.com/stevejenkins/unifi-linux-utils) のunifi\_ssl\_import.shをダウロードします。



```
tats@fox:~$ curl -O https://raw.githubusercontent.com/stevejenkins/unifi-linux-utils/master/unifi_ssl_import.sh
```



unifi\_ssl\_import.sh内の変数を設定します。`UNIFI_HOSTNAME`は Raspberry Pi のホスト名ですが、私の環境ではワイルドカード証明書を使っているため、ドメイン名を設定しています。何を設定すれば良いのか分からないときは66行目を参照すると分かってくるでしょう。また、`UNIFI_DIR`, `JAVA_DIR`, `KEYSTORE` もUbuntuの用の値に変更します。



unifi\_ssl\_import.sh



```
UNIFI_HOSTNAME=rewse.jp

UNIFI_DIR=/var/lib/unifi
JAVA_DIR=/usr/lib/unifi
KEYSTORE=${UNIFI_DIR}/keystore
```



unifi\_ssl\_import.shを実行すると、UniFiのKeystoreにファイルがインポートされます。



```
tats@fox:~$ sudo chmod 755 unifi_ssl_import.sh
tats@fox:~$ sudo ./unifi_ssl_import.sh

Starting UniFi Controller SSL Import...

Running in Standard Mode...

Importing the following files:
Private Key: /etc/letsencrypt/live/rewse.jp/privkey.pem
CA File: /etc/letsencrypt/live/rewse.jp/chain.pem

Stopping UniFi Controller...

Backup of original keystore exists!

Creating non-destructive backup as keystore.bak...

Exporting SSL certificate and key data into temporary PKCS12 file...

Removing previous certificate data from UniFi keystore...

Importing SSL certificate into UniFi keystore...
Importing keystore /tmp/tmp.ePaAJOSchq to /var/lib/unifi/keystore...

Warning:
The JKS keystore uses a proprietary format. It is recommended to migrate to PKCS12 which is an industry standard format using "keytool -importkeystore -srckeystore /var/lib/unifi/keystore -destkeystore /var/lib/unifi/keystore -deststoretype pkcs12".

Removing temporary files...

Restarting UniFi Controller to apply new Let's Encrypt SSL certificate...

Done!
```



`https://<hostname_of_raspberrypi>:8443/` にアクセスするとSSL証明書の警告が出なくなっているはずです。



## SSL証明書の自動更新設定



certbotなどでSSL証明書は自動更新されるでしょうが、このままではUniFiのKeystore内のファイルは更新されません。そのため、Cronで自動更新するようにしておきましょう。



```
tats@fox:~$ sudo cp unifi_ssl_import.sh /usr/local/sbin
```



/etc/cron.monthly/update-unifi-ssl



```
#!/bin/sh

/usr/local/sbin/unifi_ssl_import.sh
```



## ポート番号の変更



HTTPSのデフォルトポート番号443でアクセスしたい場合は、Apacheでプロキシを構成します。



/etc/apache2/sites-available/unifi.rewse.jp.conf



```
<VirtualHost *:443>
    ServerAdmin hostmaster@<hostname_of_raspberrypi>
    ServerName <hostname_of_raspberrypi>

    ProxyPreserveHost on
    ProxyRequests off
    SSLProxyEngine on
    ProxyPass / https://<hostname_of_raspberrypi>:8443/
    ProxyPassReverse / https://<hostname_of_raspberrypi>:8443/

    RewriteEngine on
    RewriteRule /(.*)  https://<hostname_of_raspberrypi>:8443/$1 [P,L]

    SSLCertificateFile /etc/letsencrypt/live/rewse.jp/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/rewse.jp/privkey.pem
    Include /etc/letsencrypt/options-ssl-apache.conf
</VirtualHost>
```



```
tats@fox:~$ sudo a2ensite unifi.rewse.jp
```



これで `https://<hostname_of_raspberrypi>/` でアクセスできるようになりました。



## 参考



[[Step-By-Step Tutorial/Guide] Raspberry Pi with UniFi Controller and Pi-hole from scratch (headless) | Ubiquiti Community](https://community.ui.com/questions/Step-By-Step-Tutorial-Guide-Raspberry-Pi-with-UniFi-Controller-and-Pi-hole-from-scratch-headless/e8a24143-bfb8-4a61-973d-0b55320101dc)