# Cadre photo

[Français](README.md) · [English](README.en.md) · [Español](README.es.md) · **Deutsch**

**Verwandeln Sie jeden Fernseher in einen digitalen Familien-Bilderrahmen – mit einem Raspberry
Pi für 20 €.**

Ihre Fotos laufen im Vollbild, mit sanften Übergängen, Aufnahmedatum und Aufnahmeort. Die
Familie fügt Fotos vom Handy hinzu, ohne App und ohne Konto, oder teilt sie in einem
iCloud-Album, dem der Rahmen von selbst folgt. Gemacht, um bei Angehörigen aufgestellt und
vergessen zu werden: Er verbindet sich per QR-Code mit dem WLAN, wird mit der
TV-Fernbedienung gesteuert und aus der Ferne aktualisiert.

> Die Bildschirme des Rahmens, seine Verwaltungsseite und das Erklärvideo sind auf Französisch.

https://github.com/user-attachments/assets/5c049a34-5ee3-4dbe-9e44-6fbbceeaa3bd

## Was er kann

[![Der Rahmen auf dem Bildschirm: Erinnerung, Ort, Uhrzeit und Wetter](docs/images/ecran.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/ecran.jpg)

- **Diashow im Vollbild**: Überblenden, Schieben, Wischen; Hoch- und Querformat gut
  eingepasst; Datum, Ort (« Sallanches, France ») und Erinnerungen « vor 2 Jahren ».
- **Fotos vom Handy hinzufügen**: QR-Code auf dem Fernseher scannen, Fotos auswählen, fertig.
  Die Fotos werden vor dem Senden verkleinert: schnell, auch bei schwachem WLAN.
- **Geteiltes iCloud-Album**: Link einfügen, der Rahmen synchronisiert alle 30 Minuten.
- **Ohne Tastatur**: Ohne bekanntes WLAN öffnet der Rahmen ein eigenes Netz und zeigt einen
  QR-Code; das Heim-WLAN wählt man am Handy.
- **TV-Fernbedienung** (HDMI-CEC): nächstes und vorheriges Foto, Pause, QR-Code.
- **Nachricht auf dem Rahmen** (« Alles Gute zum Geburtstag, Oma! »), als Banner oder im
  Vollbild, zwischen zwei Daten.
- **Dezente Uhrzeit und Wetter**, geplanter Nachtmodus (der Fernseher schaltet sich aus und
  wieder ein).
- **Favoriten, ausgeblendete Fotos, Auswahl der gezeigten Fotos** (Album, Uploads, Zeitraum).
- **Fern-Update** mit zwei Klicks, von Ihnen signiert, mit automatischer Rückkehr zur vorherigen
  Version bei Problemen; Diagnosebericht, den man Ihnen schicken kann.
- **Datenschutz**: Alles bleibt auf dem Rahmen, kein Konto und kein Online-Dienst nötig.

| WLAN-Einrichtung | Nachricht der Familie |
|---|---|
| [![WLAN-Einrichtungsbildschirm](docs/images/hotspot.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/hotspot.jpg) | [![Nachricht auf dem Rahmen](docs/images/message.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/message.jpg) |

| Verwaltungsseite (Handy oder Computer) | |
|---|---|
| [![Einstellungen](docs/images/admin-reglages.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-reglages.jpg) | [![Galerie](docs/images/admin-galerie.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-galerie.jpg) |

## Hardware

| Teil | Hinweis |
|---|---|
| Raspberry Pi Zero W (oder Zero 2 W) | der Zero 2 W startet etwa 3-mal schneller |
| microSD-Karte mit 16 bis 32 GB | möglichst Klasse A1 |
| Micro-USB-Netzteil 5 V, 2,5 A | ein gutes Netzteil vermeidet Abstürze |
| Mini-HDMI-auf-HDMI-Kabel oder -Adapter | der Pi Zero hat eine Mini-HDMI-Buchse |
| Ein Fernseher oder HDMI-Bildschirm | HDMI-CEC (Anynet+, Simplink…) für Fernbedienung und Standby |
| Ein Computer für die Installation | Windows (Git Bash), macOS oder Linux |

Budget: etwa 30 €, ohne Fernseher.

## Installation in Kürze

1. **Karte vorbereiten** mit dem [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   Raspberry Pi OS Lite (32 Bit), Hostname `cadre`, Benutzer `cadre`, Heim-WLAN, SSH mit Ihrem
   öffentlichen Schlüssel (er dient auch zum Signieren der Updates).
2. **Rahmen installieren** vom Computer aus:
   ```bash
   git clone https://github.com/54yhbw7nfw-spec/cadre-photo.git
   cd cadre-photo
   ./install.sh cadre@cadre.local     # fragt einmal nach dem Passwort des Benutzers
   ssh cadre@cadre.local sudo reboot
   ```
3. **An den Fernseher anschließen**: Nach anderthalb Minuten führt ein QR-Code zur
   Verwaltungsseite. Fotos hinzufügen, fertig.

Details (auf Französisch): [technische Dokumentation](docs/technique.md) ·
[Fern-Update](docs/mise-a-jour.md) ·
[Lastenheft](docs/cahier-des-charges.md).

## Unter der Haube

Python 3 (pygame / SDL2 mit KMSDRM für die Anzeige, Flask für die Verwaltungsseite, Pillow für
die Fotos), NetworkManager, systemd. Alles läuft mit 512 MB RAM auf einem Einkernprozessor von
2017, mit flüssigen Übergängen bei 60 Bildern/s.

Lizenz: [CC0](LICENSE) (gemeinfrei).
