# Anymize Deployment Guide

## Quick Start (Copy & Run)

Die App ist so konfiguriert, dass sie nach dem Kopieren des Ordners sofort läuft:

```bash
# 1. Ordner auf neuen Server kopieren
scp -r Anymize-UI-1.1/ user@server:/path/to/destination/

# 2. Auf dem neuen Server
cd /path/to/destination/Anymize-UI-1.1/
chmod +x deploy_setup.sh
./deploy_setup.sh

# 3. App starten
./run_app_background.sh
```

## Was passiert automatisch?

1. **API Token**: Verwendet Development-Token als Default (mit Warnung)
2. **.env Datei**: Wird automatisch erstellt wenn nicht vorhanden
3. **Secret Key**: Wird sicher generiert
4. **Dependencies**: Werden installiert (requirements.txt)
5. **Verzeichnisse**: uploads/ und logs/ werden erstellt

## Sicherheits-Checkliste für Produktion

### 1. Eigenen NocoDB Token setzen
```bash
# In .env Datei:
NOCODB_TOKEN=ihr_eigener_sicherer_token
```

### 2. HTTPS aktivieren
- Nginx oder Apache als Reverse Proxy
- SSL-Zertifikat (Let's Encrypt)
- Session Cookies erfordern HTTPS

### 3. Firewall konfigurieren
```bash
# Nur benötigte Ports öffnen
ufw allow 22/tcp    # SSH
ufw allow 443/tcp   # HTTPS
ufw enable
```

### 4. Systemd Service erstellen
```bash
# /etc/systemd/system/anymize.service
[Unit]
Description=Anymize OCR App
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/Anymize-UI-1.1
Environment="NOCODB_TOKEN=your_token"
Environment="SECRET_KEY=your_secret_key"
ExecStart=/path/to/Anymize-UI-1.1/venv/bin/python /path/to/Anymize-UI-1.1/run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Umgebungsvariablen

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| NOCODB_TOKEN | API Token für NocoDB | Development Token (mit Warnung) |
| SECRET_KEY | Flask Session Key | Auto-generiert |
| NOCODB_BASE | NocoDB API URL | https://nocodb-s9q9e-u27285.vm.elestio.app/api/v2 |

## Logs & Monitoring

- App Logs: `logs/anymize_app.log`
- Uploads: `uploads/`
- Max Upload: 16 MB (konfigurierbar)

## Updates

```bash
# Code aktualisieren
git pull  # oder neuen Ordner kopieren

# Dependencies aktualisieren
source venv/bin/activate
pip install -r requirements.txt

# App neu starten
./stop_app.sh
./run_app_background.sh
```

## Troubleshooting

### App startet nicht
```bash
# Logs prüfen
tail -f logs/anymize_app.log

# Python Version prüfen (3.8+ benötigt)
python3 --version

# Dependencies prüfen
pip list
```

### Token Fehler
```bash
# .env prüfen
cat .env | grep NOCODB_TOKEN

# Token exportieren
export NOCODB_TOKEN='your_token'
```

### Port bereits belegt
```bash
# Prozess finden
lsof -i :8000

# Oder Port in run.py ändern
```
