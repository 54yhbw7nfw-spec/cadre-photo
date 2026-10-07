# Cadre photo

[Français](README.md) · [English](README.en.md) · [Español](README.es.md) · [Deutsch](README.de.md) · **Português** · [Română](README.ro.md) · [中文](README.zh.md)

**Transforme qualquer televisor numa moldura de fotografias de família, com um Raspberry Pi de 20 €.**

As suas fotografias passam em ecrã inteiro, com transições suaves, e com a data e o local onde
foram tiradas. A família adiciona fotografias a partir do telemóvel, sem aplicação nem conta, ou
partilha-as num álbum do iCloud que a moldura acompanha sozinha. Pensada para ser instalada em
casa de um familiar e depois esquecida: liga-se ao Wi-Fi com um código QR, controla-se com o
comando da televisão e atualiza-se à distância.



Uploading cadre-photo-mode-d-emploi-pt.mp4…



## O que faz

[![A moldura no ecrã: recordação, local, hora e meteorologia](docs/images/ecran.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/ecran.jpg)

- **Apresentação em ecrã inteiro**: desvanecer, deslizar, cortina; fotografias verticais e
  horizontais bem enquadradas; data, local (« Sallanches, France ») e recordações « há 2 anos ».
- **Fotografias adicionadas a partir do telemóvel**: leia o código QR mostrado na televisão,
  escolha as fotografias e pronto. São reduzidas antes do envio: rápido, mesmo com Wi-Fi fraco.
- **Álbum partilhado do iCloud**: cole a ligação, a moldura sincroniza a cada 30 minutos.
- **Sem teclado**: sem um Wi-Fi conhecido, a moldura cria a sua própria rede e mostra um código
  QR; escolhe-se o Wi-Fi de casa no telemóvel.
- **Comando da televisão** (HDMI-CEC): fotografia seguinte e anterior, pausa, código QR.
- **Mensagem na moldura** (« Parabéns, avó! »), em faixa ou em ecrã inteiro, entre duas datas.
- **Hora e meteorologia** discretas, suspensão programada à noite (a televisão desliga-se e
  volta a ligar-se).
- **Favoritas, fotografias ocultas, escolha do que passa** (álbum, envios, período).
- **Atualização à distância** em dois cliques, assinada por si, com regresso automático à versão
  anterior se algo correr mal; relatório de diagnóstico que lhe podem enviar.
- **7 línguas**: página de gestão e ecrãs da moldura em francês, inglês, espanhol, alemão,
  português, romeno e chinês.
- **Privacidade**: tudo fica na moldura, sem conta nem serviço online obrigatório.

| Configuração do Wi-Fi | Mensagem da família |
|---|---|
| [![Ecrã de configuração do Wi-Fi](docs/images/hotspot.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/hotspot.jpg) | [![Mensagem na moldura](docs/images/message.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/message.jpg) |

| Página de gestão (telemóvel ou computador) | |
|---|---|
| [![Definições](docs/images/admin-reglages.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-reglages.jpg) | [![Galeria](docs/images/admin-galerie.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-galerie.jpg) |

## Material

| Componente | Nota |
|---|---|
| Raspberry Pi Zero W (ou Zero 2 W) | o Zero 2 W arranca cerca de 3 vezes mais depressa |
| Cartão microSD de 16 a 32 GB | de preferência classe A1 |
| Fonte de alimentação micro-USB 5 V, 2,5 A | uma boa fonte evita bloqueios |
| Cabo ou adaptador mini-HDMI para HDMI | o Pi Zero tem uma ficha mini-HDMI |
| Um televisor ou ecrã HDMI | HDMI-CEC (Anynet+, Simplink…) para o comando e a suspensão |
| Um computador para a instalação | Windows (Git Bash), macOS ou Linux |

Orçamento: cerca de 30 €, sem contar com o televisor.

## Instalação em resumo

1. **Preparar o cartão** com o [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   Raspberry Pi OS Lite (32 bits), nome `cadre`, utilizador `cadre`, Wi-Fi de casa, SSH com a
   sua chave pública (também serve para assinar as atualizações).
2. **Instalar a moldura** a partir do computador:
   ```bash
   git clone https://github.com/54yhbw7nfw-spec/cadre-photo.git
   cd cadre-photo
   ./install.sh cadre@cadre.local     # pede uma vez a palavra-passe do utilizador
   ssh cadre@cadre.local sudo reboot
   ```
3. **Ligar à televisão**: ao fim de um minuto e meio, um código QR leva à página de gestão.
   Adicione as suas fotografias e pronto.

Pormenores (em francês): [documentação técnica](docs/technique.md) ·
[atualização à distância](docs/mise-a-jour.md) ·
[caderno de encargos](docs/cahier-des-charges.md).

## Por dentro

Python 3 (pygame / SDL2 em KMSDRM para a imagem, Flask para a página de gestão, Pillow para as
fotografias), NetworkManager, systemd. Tudo cabe em 512 MB de RAM num processador de um só
núcleo de 2017, com transições fluidas a 60 imagens/s.

Licença: [CC0](LICENSE) (domínio público).
