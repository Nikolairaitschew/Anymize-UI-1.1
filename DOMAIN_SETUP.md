# Anymize-UI: Domain-Setup mit Apache als Reverse-Proxy

Diese Dokumentation beschreibt, wie die Anymize-UI-Anwendung mit Apache als Reverse-Proxy und einer benutzerdefinierten Domain konfiguriert wurde.

## u00dcbersicht

Die Anymize-UI ist eine Flask-Anwendung, die standardmu00e4u00dfig auf Port 8000 lu00e4uft. Um sie unter einer eigenen Domain (explore.anymize.ai) ohne Port-Angabe erreichbar zu machen, haben wir Apache als Reverse-Proxy eingerichtet.

## Voraussetzungen

- Ubuntu Server 24.04
- Apache 2.4.x installiert
- DNS-Eintrag fu00fcr explore.anymize.ai, der auf die Server-IP (136.243.9.186) zeigt
- Anymize-UI-Anwendung konfiguriert fu00fcr Port 8000

## Konfigurationsschritte

### 1. Flask-App auf Port 8000 konfigurieren

In der Anwendung wurden folgende Dateien angepasst, um sicherzustellen, dass die App auf Port 8000 lu00e4uft:

- **run.py**: Port-Konfiguration auf 8000 eingestellt
- **enhanced_ocr_app.py**: Standardport auf 8000 gesetzt
- **run_app_background.bat/sh**: Verweise auf Port 8000 in Startskripten

### 2. Apache-Module aktivieren

```bash
sudo a2enmod proxy proxy_http
sudo systemctl restart apache2
```

### 3. VirtualHost-Konfiguration erstellen

Datei: `/etc/apache2/sites-available/explore-anymize.conf`

```apache
<VirtualHost *:80>
    ServerName explore.anymize.ai
    ServerAlias www.explore.anymize.ai

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    ErrorLog ${APACHE_LOG_DIR}/explore-anymize-error.log
    CustomLog ${APACHE_LOG_DIR}/explore-anymize-access.log combined
</VirtualHost>
```

Diese Konfiguration bewirkt, dass Apache alle Anfragen an explore.anymize.ai an die lokale Flask-Anwendung auf Port 8000 weiterleitet.

### 4. Konfiguration aktivieren

```bash
sudo a2dissite 000-default.conf  # Optional: Standard-Site deaktivieren
sudo a2ensite explore-anymize.conf
sudo systemctl restart apache2
```

### 5. Apache starten

```bash
sudo systemctl start apache2
sudo systemctl status apache2  # Pru00fcfen, ob Apache lu00e4uft
```

### 6. Anymize-UI-Anwendung starten

```bash
cd ~/NikolaiRaitschew/Anymize/Anymize-UI-1.1
./run_app_background.sh
```

## Fehlerbehebung

Wenn die Domain nicht erreichbar ist, pru00fcfen Sie folgende Punkte:

1. **DNS-Auflu00f6sung**: Mit `dig explore.anymize.ai` pru00fcfen, ob die Domain auf die Server-IP zeigt
2. **Apache-Status**: Mit `sudo systemctl status apache2` pru00fcfen, ob Apache lu00e4uft
3. **Logs**: In `/var/log/apache2/explore-anymize-error.log` nach Fehlern suchen
4. **Flask-App**: Pru00fcfen, ob die App auf Port 8000 lu00e4uft mit `curl http://localhost:8000/`

## SSL/HTTPS einrichten (Optional)

Fu00fcr eine sichere Verbindung kann Let's Encrypt verwendet werden:

```bash
sudo apt install certbot python3-certbot-apache
sudo certbot --apache -d explore.anymize.ai
```

## Wartung

Nach Aktualisierungen der Anwendung:

1. Flask-App neu starten: `./run_app_background.sh`
2. Bei Konfigurationsänderungen Apache neu laden: `sudo systemctl reload apache2`
