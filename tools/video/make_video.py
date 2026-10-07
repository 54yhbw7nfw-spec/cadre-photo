"""Mode d'emploi vidéo du cadre : diapositives commentées (voix neuronale) en MP4, par langue.

Prérequis (PC Windows) : ffmpeg, Pillow, edge-tts (pip install edge-tts, Internet), et les visuels
de la langue (fr, en, es, de, pt, ro, ru, ar, zh) :
  python tools/video/shots.py http://<ip du cadre> build/video/shots-<langue> <langue>
    captures de l'admin (dont admin-complet.png, page entière, découpée par section :
    « fichier#n » ou « #n-m ») ;
  écrans du cadre : tools/video/screens.py <sortie> <langue> lancé sur le Pi
    -> build/video/ecrans-<langue>
Usage : python tools/video/make_video.py build/video [langue]
  -> build/video/cadre-photo-mode-d-emploi.mp4 (français) ou …-<langue>.mp4
Textes : SLIDES ci-dessous en français, tools/video/locales/<langue>.json pour les autres
(titre, points clés, narration de chaque diapositive, dans le même ordre).
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
BG = (18, 18, 20)
TEXT = (235, 235, 235)
MUTED = (160, 160, 165)
ACCENT = (110, 170, 255)
FONTS = r"C:\Windows\Fonts"
# Voix neuronales Microsoft (edge-tts), une par langue.
VOICES = {"fr": "fr-FR-DeniseNeural", "en": "en-GB-SoniaNeural", "es": "es-ES-ElviraNeural",
          "de": "de-DE-KatjaNeural", "pt": "pt-PT-RaquelNeural", "ro": "ro-RO-AlinaNeural",
          "ru": "ru-RU-SvetlanaNeural", "ar": "ar-SA-ZariyahNeural", "zh": "zh-CN-XiaoxiaoNeural"}
RTL = {"ar"}  # titre et points clés alignés à droite, écrits de droite à gauche
# Polices (titre, texte) : Segoe UI n'a pas le chinois.
FACES = {"zh": ("msyhbd.ttc", "msyh.ttc")}
PAUSE = 0.9  # s de silence après chaque narration
LOCALES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
# Les données personnelles des captures (lien de l'album, réseaux Wi-Fi) sont floutées par
# shots.py, quelle que soit la langue.

# (titre, visuels « dossier/fichier », points clés à l'écran, narration)
SLIDES = [
    ("Cadre photo", ["screens/titre.png"], ["Mode d'emploi"],
     "Bienvenue. Cette vidéo explique comment utiliser le cadre photo : l'allumer, le "
     "connecter au Wi-Fi, ajouter des photos et le piloter avec la télécommande de la télé."),
    ("Brancher et allumer", ["screens/demarrage.png"],
     ["Câble HDMI vers la télé", "Puis l'alimentation : démarrage automatique",
      "Photos au bout d'1 min 30 environ"],
     "Branchez le cadre sur la télé avec le câble HDMI, puis branchez son alimentation. Il n'a "
     "pas de bouton : il démarre tout seul. Au bout d'une demi-minute, cet écran apparaît. "
     "Comptez environ une minute et demie avant les premières photos."),
    ("Wi-Fi de la maison", ["screens/qr.png"],
     ["Connexion automatique", "QR code affiché 30 secondes", "Il mène à la page de gestion"],
     "Si le cadre connaît le Wi-Fi de la maison, il s'y connecte tout seul, puis affiche "
     "pendant trente secondes ce QR code. Il mène à la page de gestion des photos."),
    ("Premier Wi-Fi", ["screens/hotspot.png"],
     ["Aucun réseau connu : le cadre crée le sien", "Scanner le QR code avec le téléphone",
      "Mot de passe affiché à l'écran"],
     "S'il ne connaît aucun réseau, par exemple chez quelqu'un d'autre, le cadre crée son "
     "propre Wi-Fi, appelé Cadre Photo Setup. Scannez ce QR code avec votre téléphone pour "
     "vous y connecter. Le mot de passe change à chaque démarrage et reste affiché à l'écran."),
    ("Choisir le Wi-Fi", ["shots/portail-wifi.png"],
     ["La page s'ouvre toute seule", "Choisir le réseau, taper son mot de passe",
      "« Se connecter »"],
     "La page de configuration s'ouvre alors toute seule sur le téléphone. Choisissez le "
     "Wi-Fi de la maison, tapez son mot de passe et touchez Se connecter. Le cadre rejoint la "
     "maison, et le QR code de la page de gestion s'affiche à la télé."),
    ("La page de gestion", ["shots/admin-complet.png#0"],
     ["QR code de la télé, ou http://cadre.local", "Transition, durée, ordre aléatoire",
      "Réglages par thème : diaporama, photos, écran", "9 langues : page et cadre"],
     "Pour gérer le cadre, scannez le QR code affiché à la télé, ou tapez cadre point local "
     "dans le navigateur d'un téléphone ou d'un ordinateur connecté au même Wi-Fi. En haut de "
     "la page se trouvent les réglages : la transition entre les photos, la durée "
     "d'affichage, l'ordre aléatoire, la date et le lieu sur les photos, et la mise en veille la "
     "nuit. Ils sont rangés par thème : le diaporama, ce qui s'affiche sur les photos, et "
     "l'écran. La langue de la page se choisit en haut à droite, et celle du cadre dans les "
     "réglages de l'écran."),
    ("Ajouter des photos", ["shots/admin-photos.png"],
     ["Glisser les photos, ou toucher pour les choisir", "Visibles en quelques secondes",
      "Sélectionner puis « Supprimer la sélection »"],
     "Pour ajouter des photos, glissez-les dans la zone en pointillés, ou touchez-la pour les "
     "choisir sur votre téléphone. Elles arrivent dans la galerie et dans le diaporama "
     "quelques secondes plus tard. Pour en retirer, sélectionnez-les, puis touchez Supprimer "
     "la sélection."),
    ("Album iCloud partagé", ["shots/admin-haut.png"],
     ["iPhone : album partagé, « Site web public »", "Coller le lien dans la page de gestion",
      "Vérifié toutes les 30 minutes", "Photos de l'album entourées d'orange"],
     "Vous pouvez aussi relier un album partagé iCloud. Sur l'iPhone, ouvrez l'album, touchez "
     "l'icône des personnes et activez Site web public. Copiez ensuite le lien et collez-le "
     "dans la page de gestion. Le cadre vérifie l'album toutes les trente minutes, et ses "
     "photos sont entourées d'orange dans la galerie."),
    ("Pendant le diaporama", ["screens/photo.png"],
     ["Lieu et date de prise de vue en bas à droite", "« Afficher la date », « Afficher le lieu »",
      "Lieu : photos d'iPhone et album iCloud (WhatsApp l'efface)"],
     "Pendant le diaporama, le lieu et la date de prise de vue s'affichent en bas à droite de "
     "chaque photo. Chacun se règle dans la page de gestion. Le lieu est connu pour les photos "
     "prises avec un téléphone et pour celles de l'album iCloud, mais pas pour les photos "
     "reçues par WhatsApp, qui efface cette information."),
    ("Souvenirs et nouveautés", ["screens/ecran.png"],
     ["« Il y a 2 ans » : photos prises ce jour-là", "Étincelle : photo arrivée depuis 24 h",
      "Heure et météo en bas à gauche"],
     "Le cadre fait revivre vos souvenirs : les photos prises le même jour, les années "
     "passées, reviennent souvent, avec la mention Il y a deux ans. Une étincelle bleue signale "
     "les photos arrivées depuis moins d'un jour. Et si vous le souhaitez, l'heure et la météo "
     "s'affichent en bas à gauche, avec une petite icône."),
    ("Favoris et photos masquées", ["shots/admin-complet.png#4:430"],
     ["Étoile : favori, revient plus souvent", "Œil : masquée du diaporama, mais gardée",
      "Choisir : album, envois, favoris, période"],
     "Dans la galerie, l'étoile marque une photo favorite : elle revient plus souvent. L'œil "
     "masque une photo du diaporama sans la supprimer. Dans les réglages, vous pouvez aussi "
     "choisir ce qui défile : l'album iCloud, les photos envoyées, les favoris, ou une période."),
    ("Un message sur le cadre", ["shots/admin-complet.png#1", "screens/bandeau.png"],
     ["Section « Message sur le cadre »", "Bandeau sur les photos, ou écran entre elles",
      "Jusqu'à une date, ou « Retirer »"],
     "Pour une occasion, vous pouvez afficher un message sur le cadre. Dans la section Message "
     "sur le cadre, tapez votre texte, choisissez un bandeau en haut des photos ou un écran "
     "entre les photos, et éventuellement une date de fin. Touchez Afficher. Le message "
     "disparaît tout seul après cette date, ou quand vous touchez Retirer."),
    ("La télécommande de la télé", ["screens/pause.png"],
     ["→  photo suivante", "←  photo précédente", "↑ ou ↓  pause / reprise",
      "OK  QR code de la page de gestion"],
     "Si la télé le permet, sa télécommande pilote le cadre. Flèche droite : photo suivante. "
     "Flèche gauche : photo précédente. Flèche du haut ou du bas : pause, et de nouveau pour "
     "reprendre. Touche OK : le QR code de la page de gestion."),
    ("Éteindre et redémarrer", ["shots/admin-complet.png#8-9",
                                 "screens/extinction.png"],
     ["Boutons en bas de la page de gestion", "Débrancher quand la diode verte est éteinte",
      "Mot de passe de la page, si besoin"],
     "En bas de la page de gestion se trouvent les boutons Redémarrer et Éteindre. Avant de "
     "débrancher le cadre, éteignez-le ainsi et attendez que sa diode verte s'éteigne. C'est "
     "aussi là que vous pouvez protéger la page par un mot de passe."),
    ("Mettre à jour le cadre", ["shots/admin-complet.png#6"],
     ["« Rechercher une mise à jour », puis « Installer »", "Ou un fichier « .cadre » reçu",
      "Vérifié avant, contrôlé après", "Problème : ancienne version remise"],
     "Pour mettre le cadre à jour, ouvrez la page de gestion, section Mise à jour, et touchez "
     "Rechercher une mise à jour. Si une nouvelle version existe, touchez Installer cette "
     "version. Vous pouvez aussi installer un fichier point cadre reçu par message. Le cadre "
     "vérifie qu'elle vient bien de la personne qui s'en occupe, l'installe, puis contrôle "
     "que tout fonctionne ; au moindre problème, il remet l'ancienne version tout seul. "
     "Comptez trois minutes, la page vous tient au courant."),
    ("Envoyer un rapport", ["shots/admin-complet.png#7"],
     ["Section « Diagnostic »", "Cocher, choisir la période", "« Télécharger le rapport »",
      "L'envoyer par message"],
     "En cas de problème, la section Diagnostic prépare un rapport pour la personne qui "
     "s'occupe du cadre. Laissez les cases cochées, choisissez la période, puis touchez "
     "Télécharger le rapport, et envoyez-lui le fichier par message. Les mots de passe n'y "
     "figurent pas."),
    ("En cas de souci", ["screens/demarrage.png"],
     ["Ne répond plus : débrancher, rebrancher", "Wi-Fi perdu : il recrée son réseau",
      "Écran noir : vérifier l'entrée HDMI de la télé"],
     "En cas de souci : si le cadre ne répond plus, débranchez-le puis rebranchez-le ; il "
     "redémarre aussi tout seul s'il se bloque. S'il perd le Wi-Fi plus de deux minutes, il "
     "recrée son réseau de configuration. Et si l'écran reste noir, vérifiez que la télé est "
     "sur la bonne entrée HDMI."),
    ("Bon diaporama !", ["screens/titre.png"], [],
     "Voilà, vous savez tout. Bon diaporama !"),
]


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def slides(lang):
    """Diapositives dans la langue : visuels de SLIDES, textes de locales/<langue>.json."""
    if lang == "fr":
        return SLIDES
    with open(os.path.join(LOCALES, lang + ".json"), encoding="utf-8") as f:
        texts = json.load(f)
    if len(texts) != len(SLIDES):
        raise SystemExit(f"{lang}.json : {len(texts)} diapositives, {len(SLIDES)} attendues")
    return [(title, visuals, bullets, narration)
            for (_, visuals, _, _), (title, bullets, narration) in zip(SLIDES, texts)]


CLOSING = "，。、：；！？）」』”’》%"  # jamais en début de ligne (chinois)
OPENING = "（「『“‘《"                # jamais en fin de ligne


def wrap(d, text, f, width, direction=None):
    """Lignes de text tenant dans width pixels : par mots, ou par caractères (chinois), sans
    ponctuation fermante en début de ligne ni ouvrante en fin de ligne."""
    by_char = any(ord(c) >= 0x2E80 for c in text)
    units = list(text) if by_char else text.split(" ")
    sep = "" if by_char else " "
    lines, line = [], ""
    for u in units:
        trial = (line + sep + u) if line else u
        if d.textlength(trial, font=f, direction=direction) > width and line and u not in CLOSING:
            carry = ""
            while line and line[-1] in OPENING:
                carry, line = line[-1] + carry, line[:-1]
            lines.append(line)
            line = (carry + u).lstrip()
        else:
            line = trial
    return lines + [line]


def fit(img, box_w, box_h):
    img = img.convert("RGB")
    scale = min(box_w / img.width, box_h / img.height)
    return img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                      Image.LANCZOS)


def framed(img):
    """Visuel posé sur une carte arrondie avec une ombre douce."""
    pad = 10
    card = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *card.size), radius=18, fill=255)
    card.paste((52, 52, 58), mask=mask)
    card.paste(img, (pad, pad))
    shadow = Image.new("RGBA", (card.width + 60, card.height + 60), (0, 0, 0, 0))
    smask = Image.new("L", shadow.size, 0)
    ImageDraw.Draw(smask).rounded_rectangle((30, 40, card.width + 30, card.height + 40),
                                            radius=18, fill=150)
    shadow.paste((0, 0, 0), mask=smask.filter(ImageFilter.GaussianBlur(18)))
    shadow.alpha_composite(card, (30, 30))
    return shadow


def cards(img):
    """Sections (cartes blanches) d'une capture de l'admin : [(haut, bas), ...] de haut en bas."""
    px, spans, top = img.load(), [], None
    for y in range(img.height):
        on_card = px[115, y][0] > 250
        if on_card and top is None:
            top = y
        elif not on_card and top is not None:
            spans.append((top, y))
            top = None
    return spans


def load_visual(base, name, lang):
    """« dossier/fichier.png », « …png#n » (n-ième section de l'admin, à partir de 0) ou
    « …png#n-m » (sections n à m) : pas de coordonnées à refaire quand la page change.
    Dossiers de la langue : shots -> shots-<langue>, screens -> ecrans-<langue>."""
    name, _, sections = name.partition("#")
    folder, _, file = name.partition("/")
    folder = {"shots": "shots-", "screens": "ecrans-"}[folder] + lang
    img = Image.open(os.path.join(base, folder, file)).convert("RGB")
    if sections:
        sections, _, maxh = sections.partition(":")  # « #4:420 » : 420 px au plus
        first, _, last = sections.partition("-")
        spans = cards(img)
        top, bottom = spans[int(first)][0], spans[int(last or first)][1]
        if maxh:
            bottom = min(bottom, top + int(maxh))
        img = img.crop((90, top - 8, 1190, bottom + 8))
    return img


def render_slide(base, lang, title, visuals, bullets, path):
    title_face, text_face = FACES.get(lang, ("seguisb.ttf", "segoeui.ttf"))
    rtl = lang in RTL
    direction = "rtl" if rtl else None
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    if rtl:
        d.text((W - 90, 70), title, font=font(title_face, 64), fill=TEXT, anchor="ra",
               direction=direction)
        d.rectangle((W - 210, 178, W - 90, 184), fill=ACCENT)
    else:
        d.text((90, 70), title, font=font(title_face, 64), fill=TEXT)
        d.rectangle((90, 178, 210, 184), fill=ACCENT)
    area_w = 1180 if bullets else W - 180
    area_h = H - 290
    pics = [load_visual(base, v, lang) for v in visuals]
    if len(pics) == 1:
        cards = [framed(fit(pics[0], area_w, area_h))]
    else:  # deux visuels empilés
        cards = [framed(fit(p, area_w, area_h // 2 - 20)) for p in pics]
    total = sum(c.height for c in cards) - 30 * (len(cards) - 1)
    y = 200 + (area_h - total) // 2 - 30
    for c in cards:
        x = 60 + (area_w - c.width) // 2 + 30
        img.alpha_composite(c, (max(0, x), max(170, y)))
        y += c.height - 30
    if bullets:
        f = font(text_face, 40)
        y = 300
        for b in bullets:
            # Puce à gauche, ou à droite pour l'arabe (texte aligné sur elle).
            dot = 1821 if rtl else 1335
            d.ellipse((dot, y + 20, dot + 14, y + 34), fill=ACCENT)
            # Guillemets collés à leur mot (espace insécable : pas de coupure de ligne).
            b = b.replace("« ", "« ").replace(" »", " »")
            for ln in wrap(d, b, f, 470, direction):
                if rtl:
                    d.text((1800, y), ln, font=f, fill=TEXT, anchor="ra", direction=direction)
                else:
                    d.text((1370, y), ln, font=f, fill=TEXT)
                y += 54
            y += 34
    img.convert("RGB").save(path)


def speak(text, path, lang):
    """Voix neuronale de Microsoft (celle de la lecture à voix haute d'Edge) : MP3, refait
    seulement si le texte ou la voix ont changé (texte gardé à côté, en .txt)."""
    said = os.path.splitext(path)[0] + ".txt"
    key = VOICES[lang] + "\n" + text
    try:
        with open(said, encoding="utf-8") as f:
            if f.read() == key and os.path.exists(path):
                return
    except OSError:
        pass
    subprocess.run([sys.executable, "-m", "edge_tts", "--voice", VOICES[lang], "--text", text,
                    "--write-media", path], check=True)
    with open(said, "w", encoding="utf-8") as f:
        f.write(key)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(out.stdout)


def main(base, lang="fr"):
    sys.stdout.reconfigure(encoding="utf-8")  # titres roumains, chinois : console Windows
    work = os.path.join(base, "slides-" + lang)
    os.makedirs(work, exist_ok=True)
    segments = []
    for i, (title, visuals, bullets, narration) in enumerate(slides(lang), 1):
        png, voice, mp4 = (os.path.abspath(os.path.join(work, f"{i:02d}.{e}"))
                         for e in ("png", "mp3", "mp4"))
        render_slide(base, lang, title, visuals, bullets, png)
        speak(narration, voice, lang)
        dur = duration(voice) + PAUSE
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png, "-i", voice,
            # Pas de fondu d'ouverture sur la 1re : son image sert d'aperçu aux lecteurs
            # (GitHub montre la première image de la vidéo).
            "-vf", ("" if i == 1 else "fade=t=in:st=0:d=0.4,")
            + f"fade=t=out:st={dur - 0.4:.2f}:d=0.4,format=yuv420p",
            "-af", f"apad=whole_dur={dur:.2f}", "-t", f"{dur:.2f}", "-r", "25",
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-ar", "48000", mp4],
            check=True)
        segments.append(mp4)
        print(f"{i:02d} {title} : {dur:.1f} s")
    listing = os.path.join(work, "liste.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.writelines(f"file '{s}'\n" for s in segments)
    out = os.path.abspath(os.path.join(
        base, "cadre-photo-mode-d-emploi" + ("" if lang == "fr" else "-" + lang) + ".mp4"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", "-movflags", "+faststart", out], check=True)
    print("vidéo :", out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
