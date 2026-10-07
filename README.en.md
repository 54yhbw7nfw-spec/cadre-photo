# Cadre photo

[Français](README.md) · **English** · [Español](README.es.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [Română](README.ro.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [中文](README.zh.md)

**Turn any TV into a family photo frame, with a €20 Raspberry Pi.**

Your photos play full screen, with smooth transitions and the date and place they were taken.
The family adds photos from their phones, with no app and no account, or shares them in an
iCloud album that the frame follows on its own. Built to be set up at a relative's home and
forgotten: it joins the Wi-Fi through a QR code, is driven with the TV remote, and is updated
remotely.





https://github.com/user-attachments/assets/c21e93ef-faa0-494b-abfe-0f3351bc6d45




## What it does

[![The frame on screen: memory, place, time and weather](docs/images/ecran.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/ecran.jpg)

- **Full-screen slideshow**: fade, slides, wipe; portrait and landscape photos nicely framed;
  date, place (« Sallanches, France ») and memories « 2 years ago ».
- **Add photos from a phone**: scan the QR code shown on the TV, pick your photos, done. Photos
  are resized before upload: fast, even on weak Wi-Fi.
- **Shared iCloud album**: paste the link, the frame syncs every 30 minutes, videos
  included (with sound).
- **No keyboard needed**: without a known Wi-Fi, the frame creates its own network and shows a
  QR code; choose the home Wi-Fi from your phone.
- **TV remote** (HDMI-CEC): next and previous photo, pause, QR code.
- **Message on the frame** (« Happy birthday Grandma! »), as a banner or full screen, between
  two dates.
- **Discreet clock and weather**, scheduled night standby (the TV turns off and back on).
- **Favourites, hidden photos, choice of what plays** (album, uploads, period).
- **Remote update** in two clicks, signed by you, with automatic return to the previous version
  if anything goes wrong; diagnostic report sent to you.
- **9 languages**: management page and frame screens in French, English, Spanish, German,
  Portuguese, Romanian, Russian, Arabic and Chinese.
- **Privacy first**: everything stays on the frame, no account or online service required.

| Wi-Fi setup | Family message |
|---|---|
| [![Wi-Fi setup screen](docs/images/hotspot.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/hotspot.jpg) | [![Message on the frame](docs/images/message.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/message.jpg) |

| Management page (phone or computer) | |
|---|---|
| [![Settings](docs/images/admin-reglages.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-reglages.jpg) | [![Gallery](docs/images/admin-galerie.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-galerie.jpg) |

## Hardware

| Item | Note |
|---|---|
| Raspberry Pi Zero W (or Zero 2 W) | the Zero 2 W boots about 3 times faster |
| 16 to 32 GB microSD card | A1 class preferred |
| Micro-USB 5 V, 2.5 A power supply | a good power supply avoids crashes |
| Mini-HDMI to HDMI cable or adapter | the Pi Zero has a mini-HDMI port |
| A TV or HDMI screen | HDMI-CEC (Anynet+, Simplink…) for the remote and standby |
| A computer for the installation | Windows (Git Bash), macOS or Linux |

Budget: about €30, TV not included.

## Installation in short

1. **Prepare the card** with [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   Raspberry Pi OS Lite (32-bit), hostname `cadre`, user `cadre`, home Wi-Fi, SSH with your
   public key (it is also used to sign updates).
2. **Install the frame** from your computer:
   ```bash
   git clone https://github.com/54yhbw7nfw-spec/cadre-photo.git
   cd cadre-photo
   ./install.sh cadre@cadre.local     # asks for the user's password once
   ssh cadre@cadre.local sudo reboot
   ```
3. **Plug it into the TV**: after a minute and a half, a QR code leads to the management page.
   Add your photos and you are done.

Details (in French): [technical documentation](docs/technique.md) ·
[remote update](docs/mise-a-jour.md) ·
[specification](docs/cahier-des-charges.md).

## Under the hood

Python 3 (pygame / SDL2 on KMSDRM for display, Flask for the management page, Pillow for
photos), NetworkManager, systemd. It all fits in 512 MB of RAM on a 2017 single-core processor,
with smooth 60 fps transitions.

License: [CC0](LICENSE) (public domain).
