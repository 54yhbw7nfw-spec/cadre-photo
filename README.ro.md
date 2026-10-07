# Cadre photo

[Français](README.md) · [English](README.en.md) · [Español](README.es.md) · [Deutsch](README.de.md) · **Română** · [中文](README.zh.md)

**Transformați orice televizor într-o ramă foto de familie, cu un Raspberry Pi de 20 €.**

Fotografiile rulează pe tot ecranul, cu tranziții line, cu data și locul în care au fost
făcute. Familia adaugă poze de pe telefon, fără aplicație și fără cont, sau le pune într-un
album iCloud partajat pe care rama îl urmărește singură. Gândită pentru a fi instalată la
rude și apoi uitată: se conectează la Wi-Fi printr-un cod QR, se comandă cu telecomanda
televizorului și se actualizează de la distanță.

> Videoclipul de prezentare este în franceză; rama și pagina de administrare vorbesc 7 limbi.

https://github.com/user-attachments/assets/5c049a34-5ee3-4dbe-9e44-6fbbceeaa3bd

## Ce știe să facă

[![Rama pe ecran: amintire, loc, oră și vreme](docs/images/ecran.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/ecran.jpg)

- **Prezentare pe tot ecranul**: estompare, glisare, cortină; fotografii verticale și
  orizontale bine încadrate; data, locul (« Sallanches, France ») și amintiri « acum 2 ani ».
- **Poze adăugate de pe telefon**: scanați codul QR afișat pe televizor, alegeți pozele și gata.
  Pozele sunt micșorate înainte de trimitere: rapid, chiar și cu Wi-Fi slab.
- **Album iCloud partajat**: lipiți linkul, rama se sincronizează la fiecare 30 de minute.
- **Fără tastatură**: fără o rețea Wi-Fi cunoscută, rama își creează propria rețea și afișează
  un cod QR; alegeți Wi-Fi-ul casei de pe telefon.
- **Telecomanda televizorului** (HDMI-CEC): poza următoare și cea anterioară, pauză, cod QR.
- **Mesaj pe ramă** (« La mulți ani, bunico! »), ca bandă sau pe tot ecranul, între două date.
- **Ora și vremea**, discrete; mod de veghe programat noaptea (televizorul se stinge și se
  aprinde din nou).
- **Favorite, poze ascunse, alegerea a ceea ce rulează** (album, trimiteri, perioadă).
- **Actualizare de la distanță** în două clicuri, semnată de dumneavoastră, cu revenire automată
  la versiunea anterioară dacă ceva nu merge; raport de diagnostic care vă poate fi trimis.
- **7 limbi**: pagina de administrare și ecranele ramei în franceză, engleză, spaniolă,
  germană, portugheză, română și chineză.
- **Confidențialitate**: totul rămâne pe ramă, fără cont și fără serviciu online obligatoriu.

| Configurarea Wi-Fi | Mesaj de la familie |
|---|---|
| [![Ecranul de configurare Wi-Fi](docs/images/hotspot.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/hotspot.jpg) | [![Mesaj pe ramă](docs/images/message.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/message.jpg) |

| Pagina de administrare (telefon sau calculator) | |
|---|---|
| [![Setări](docs/images/admin-reglages.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-reglages.jpg) | [![Galerie](docs/images/admin-galerie.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-galerie.jpg) |

## Componente

| Componentă | Observație |
|---|---|
| Raspberry Pi Zero W (sau Zero 2 W) | Zero 2 W pornește de aproximativ 3 ori mai repede |
| Card microSD de 16 până la 32 GB | de preferință clasa A1 |
| Alimentator micro-USB 5 V, 2,5 A | un alimentator bun evită blocările |
| Cablu sau adaptor mini-HDMI la HDMI | Pi Zero are o mufă mini-HDMI |
| Un televizor sau un ecran HDMI | HDMI-CEC (Anynet+, Simplink…) pentru telecomandă și veghe |
| Un calculator pentru instalare | Windows (Git Bash), macOS sau Linux |

Buget: aproximativ 30 €, fără televizor.

## Instalarea pe scurt

1. **Pregătiți cardul** cu [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   Raspberry Pi OS Lite (32 de biți), nume `cadre`, utilizator `cadre`, Wi-Fi-ul casei, SSH cu
   cheia dumneavoastră publică (servește și la semnarea actualizărilor).
2. **Instalați rama** de pe calculator:
   ```bash
   git clone https://github.com/54yhbw7nfw-spec/cadre-photo.git
   cd cadre-photo
   ./install.sh cadre@cadre.local     # cere o singură dată parola utilizatorului
   ssh cadre@cadre.local sudo reboot
   ```
3. **Conectați-o la televizor**: după un minut și jumătate, un cod QR duce la pagina de
   administrare. Adăugați pozele și gata.

Detalii (în franceză): [documentație tehnică](docs/technique.md) ·
[actualizare de la distanță](docs/mise-a-jour.md) ·
[caiet de sarcini](docs/cahier-des-charges.md).

## Sub capotă

Python 3 (pygame / SDL2 în KMSDRM pentru afișare, Flask pentru pagina de administrare, Pillow
pentru fotografii), NetworkManager, systemd. Totul încape în 512 MB de RAM, pe un procesor cu
un singur nucleu din 2017, cu tranziții fluide la 60 de cadre/s.

Licență: [CC0](LICENSE) (domeniu public).
