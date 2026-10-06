"""Écrans du cadre pour le mode d'emploi vidéo, produits par le code du diaporama (sur le Pi).

Usage (sur le Pi) : cd /opt/cadre && SDL_VIDEODRIVER=dummy python3 /chemin/screens.py <sortie>
Les méthodes de dessin de Display sont appelées sans écran : texture() renvoie la Surface.
"""
import json
import os
import socket
import sys

import pygame

from cadre import config, display, places, splash

# Le Mont Blanc depuis l'aiguille du Midi (album iCloud du cadre de test).
TITLE_PHOTO = "20240808-094711_7300f94c98.jpg"


def main(out):
    os.makedirs(out, exist_ok=True)
    pygame.font.init()
    socket.gethostname = lambda: "cadre"  # nom habituel, pas celui du Pi de test
    d = display.Display.__new__(display.Display)  # sans fenêtre ni rendu GPU
    d.texture = lambda surf: surf
    d.date_font = pygame.font.Font(None, 34)
    W, H = display.W, display.H

    def save(name, surf):
        pygame.image.save(surf, os.path.join(out, name))

    splash.background(W, H).save(os.path.join(out, "demarrage.png"))
    splash.background(W, H, "Extinction...",
                      "Attendez que la diode verte du cadre s'éteigne avant de le débrancher.") \
        .save(os.path.join(out, "extinction.png"))
    save("connexion.png", d.message_texture(["Connexion au Wi-Fi..."]))
    save("hotspot.png", d.hotspot_texture({"ap_ssid": "CadrePhoto-Setup",
                                           "ap_password": "k7m2qx9p4t", "ip": "10.42.0.1"}))
    d.qr_key, d.qr_until, d.info_until = None, 1e12, 0
    # Adresse d'exemple (pas celle du Pi).
    key, build = d.network_screen({"mode": "connected", "ip": "192.168.1.20"})
    save("qr.png", build())

    # Photo avec sa date, puis la même en pause (cartouche comme Display.show).
    # Une photo de l'album iCloud (vraie date de prise de vue) avec un lieu, sinon en largeur.
    with open(config.ICLOUD_FILE) as f:
        names = sorted(json.load(f)["photos"].values())
    located = places.load()
    names.sort(key=lambda n: n not in located)
    for name in names:
        photo = display.load_photo(os.path.join(config.PHOTOS_DIR, name))
        if name in located or photo.get_width() >= W:
            break
    screen = pygame.Surface((W, H))
    screen.blit(photo, ((W - photo.get_width()) // 2, (H - photo.get_height()) // 2))
    d.draw_date(screen, name, located.get(name))
    save("photo.png", screen)
    banner = screen.copy()
    d.draw_banner(banner, "Bon anniversaire Mamie ! Gros bisous de toute la famille")
    save("bandeau.png", banner)
    save("message.png", d.message_card("Bon anniversaire Mamie ! Gros bisous de toute la famille"))

    # Écran complet : souvenir avec son lieu, pictogramme « nouveau », heure et météo
    # (coin composé comme Display.update_corner, sans rendu GPU).
    full = pygame.Surface((W, H))
    full.blit(photo, ((W - photo.get_width()) // 2, (H - photo.get_height()) // 2))
    d.draw_date(full, name, located.get(name), True, "Il y a 2 ans")
    d.draw_badge(full)
    parts = [d.date_font.render("16:08", True, display.TEXT), display.weather_icon("partly", True),
             d.date_font.render("18 °C", True, display.TEXT)]
    w = sum(p.get_width() for p in parts) + 10 * (len(parts) - 1) + 24
    h = max(p.get_height() for p in parts) + 10
    box = pygame.Surface((w, h), pygame.SRCALPHA)
    box.fill((0, 0, 0, 140))
    x = 12
    for part in parts:
        box.blit(part, (x, (h - part.get_height()) // 2))
        x += part.get_width() + 10
    full.blit(box, (16, H - h - 16))
    save("ecran.png", full)
    img = d.date_font.render("Pause", True, display.TEXT)
    box = pygame.Surface((img.get_width() + 24, img.get_height() + 12), pygame.SRCALPHA)
    box.fill((0, 0, 0, 160))
    box.blit(img, (12, 6))
    screen.blit(box, (16, 16))
    save("pause.png", screen)

    # Photo de titre (première et dernière diapositives) : le Mont Blanc, autre que la photo
    # des autres écrans ; à défaut, la même.
    title = TITLE_PHOTO if TITLE_PHOTO in names else name
    tphoto = display.load_photo(os.path.join(config.PHOTOS_DIR, title))
    screen = pygame.Surface((W, H))
    screen.blit(tphoto, ((W - tphoto.get_width()) // 2, (H - tphoto.get_height()) // 2))
    d.draw_date(screen, title, located.get(title))
    save("titre.png", screen)
    print("écrans dans", out, "- photo :", name, "- titre :", title)


if __name__ == "__main__":
    main(sys.argv[1])
