# Cadre photo

[Français](README.md) · [English](README.en.md) · **Español** · [Deutsch](README.de.md) · [Português](README.pt.md) · [Română](README.ro.md) · [中文](README.zh.md)

**Convierte cualquier televisor en un marco de fotos familiar, con una Raspberry Pi de 20 €.**

Tus fotos pasan a pantalla completa, con transiciones suaves y la fecha y el lugar donde se
tomaron. La familia añade fotos desde el móvil, sin aplicación ni cuenta, o las comparte en un
álbum de iCloud que el marco sigue por sí solo. Pensado para instalarlo en casa de un familiar y
olvidarse: se conecta al Wi-Fi con un código QR, se maneja con el mando de la tele y se
actualiza a distancia.

▶ [Ver el vídeo tutorial (español)](docs/video/cadre-photo-mode-d-emploi-es.mp4)

## Qué hace

[![El marco en pantalla: recuerdo, lugar, hora y tiempo](docs/images/ecran.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/ecran.jpg)

- **Presentación a pantalla completa**: fundido, deslizamientos, cortinilla; fotos verticales y
  horizontales bien encuadradas; fecha, lugar (« Sallanches, France ») y recuerdos « hace 2
  años ».
- **Añadir fotos desde el móvil**: escanea el código QR que aparece en la tele, elige tus fotos
  y listo. Las fotos se reducen antes de enviarlas: rápido incluso con Wi-Fi débil.
- **Álbum compartido de iCloud**: pega el enlace, el marco se sincroniza cada 30 minutos.
- **Sin teclado**: sin un Wi-Fi conocido, el marco crea su propia red y muestra un código QR;
  eliges el Wi-Fi de casa desde el móvil.
- **Mando de la tele** (HDMI-CEC): foto siguiente y anterior, pausa, código QR.
- **Mensaje en el marco** (« ¡Feliz cumpleaños, abuela! »), en banda o a pantalla completa,
  entre dos fechas.
- **Hora y tiempo** discretos, reposo programado por la noche (la tele se apaga y se vuelve a
  encender).
- **Favoritas, fotos ocultas, elección de lo que se muestra** (álbum, envíos, periodo).
- **Actualización a distancia** en dos clics, firmada por ti, con vuelta automática a la versión
  anterior si algo falla; informe de diagnóstico que te pueden enviar.
- **7 idiomas**: página de gestión y pantallas del marco en francés, inglés, español, alemán,
  portugués, rumano y chino.
- **Privacidad**: todo se queda en el marco, sin cuenta ni servicio en línea obligatorio.

| Configuración del Wi-Fi | Mensaje de la familia |
|---|---|
| [![Pantalla de configuración del Wi-Fi](docs/images/hotspot.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/hotspot.jpg) | [![Mensaje en el marco](docs/images/message.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/message.jpg) |

| Página de gestión (móvil u ordenador) | |
|---|---|
| [![Ajustes](docs/images/admin-reglages.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-reglages.jpg) | [![Galería](docs/images/admin-galerie.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-galerie.jpg) |

## Material

| Elemento | Nota |
|---|---|
| Raspberry Pi Zero W (o Zero 2 W) | la Zero 2 W arranca unas 3 veces más rápido |
| Tarjeta microSD de 16 a 32 GB | preferiblemente clase A1 |
| Fuente de alimentación micro-USB 5 V, 2,5 A | una buena fuente evita bloqueos |
| Cable o adaptador mini-HDMI a HDMI | la Pi Zero tiene un puerto mini-HDMI |
| Un televisor o pantalla HDMI | HDMI-CEC (Anynet+, Simplink…) para el mando y el reposo |
| Un ordenador para la instalación | Windows (Git Bash), macOS o Linux |

Presupuesto: unos 30 €, sin contar la tele.

## Instalación en resumen

1. **Preparar la tarjeta** con [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   Raspberry Pi OS Lite (32 bits), nombre `cadre`, usuario `cadre`, Wi-Fi de casa, SSH con tu
   clave pública (también sirve para firmar las actualizaciones).
2. **Instalar el marco** desde tu ordenador:
   ```bash
   git clone https://github.com/54yhbw7nfw-spec/cadre-photo.git
   cd cadre-photo
   ./install.sh cadre@cadre.local     # pide una vez la contraseña del usuario
   ssh cadre@cadre.local sudo reboot
   ```
3. **Conectarlo a la tele**: al cabo de un minuto y medio, un código QR lleva a la página de
   gestión. Añade tus fotos y listo.

Detalles (en francés): [documentación técnica](docs/technique.md) ·
[actualización a distancia](docs/mise-a-jour.md) ·
[pliego de condiciones](docs/cahier-des-charges.md).

## Por dentro

Python 3 (pygame / SDL2 en KMSDRM para la imagen, Flask para la página de gestión, Pillow para
las fotos), NetworkManager, systemd. Todo cabe en 512 MB de RAM en un procesador de un núcleo de
2017, con transiciones fluidas a 60 imágenes/s.

Licencia: [CC0](LICENSE) (dominio público).
