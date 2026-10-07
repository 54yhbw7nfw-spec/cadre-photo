# Cadre photo

[Français](README.md) · [English](README.en.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [Română](README.ro.md) · [Русский](README.ru.md) · **العربية** · [中文](README.zh.md)

<div dir="rtl">

**حوّل أي تلفاز إلى إطار صور عائلي باستخدام Raspberry Pi بسعر 20 يورو.**

تُعرض صورك على كامل الشاشة، بانتقالات سلسة، مع تاريخ التقاطها ومكانه. يضيف أفراد العائلة
الصور من هواتفهم، دون تطبيق ودون حساب، أو يشاركونها في ألبوم iCloud يتابعه الإطار بنفسه.
صُمّم ليُركَّب في منزل أحد الأقارب ثم يُنسى: يتصل بشبكة Wi-Fi عبر رمز QR، ويُتحكَّم فيه بجهاز
التحكم الخاص بالتلفاز، ويُحدَّث عن بُعد.


https://github.com/user-attachments/assets/a815657f-cf16-4ae8-a317-740ab5731937




## ماذا يفعل

[![الإطار على الشاشة: ذكرى، مكان، ساعة وطقس](docs/images/ecran.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/ecran.jpg)

- **عرض شرائح على كامل الشاشة**: تلاشٍ وانزلاق ومسح؛ الصور العمودية والأفقية مؤطرة جيدًا؛
  التاريخ والمكان («Sallanches, France») وذكريات «منذ سنتين».
- **إضافة الصور من الهاتف**: امسح رمز QR الظاهر على التلفاز، واختر صورك، وانتهى الأمر. تُصغَّر
  الصور قبل الإرسال: سريع حتى مع Wi-Fi ضعيف.
- **ألبوم iCloud مشترك**: الصق الرابط، ويتزامن الإطار كل 30 دقيقة.
- **دون لوحة مفاتيح**: إذا لم يجد شبكة معروفة، ينشئ الإطار شبكته ويعرض رمز QR؛ وتُختار شبكة
  المنزل من الهاتف.
- **جهاز التحكم بالتلفاز** (HDMI-CEC): الصورة التالية والسابقة، إيقاف مؤقت، رمز QR.
- **رسالة على الإطار** («عيد ميلاد سعيد يا جدتي!») كشريط أو على كامل الشاشة، بين تاريخين.
- **الساعة والطقس** بشكل هادئ، وسكون ليلي مجدول (ينطفئ التلفاز ثم يعود للعمل).
- **المفضلة والصور المخفية واختيار ما يُعرض** (الألبوم، الصور المرسلة، فترة زمنية).
- **تحديث عن بُعد** بنقرتين، موقَّع منك، مع عودة تلقائية إلى الإصدار السابق عند حدوث مشكلة؛
  وتقرير تشخيص يمكن إرساله إليك.
- **9 لغات**: صفحة الإدارة وشاشات الإطار بالفرنسية والإنجليزية والإسبانية والألمانية
  والبرتغالية والرومانية والروسية والعربية والصينية.
- **الخصوصية**: يبقى كل شيء على الإطار، دون حساب أو خدمة عبر الإنترنت.

| إعداد Wi-Fi | رسالة من العائلة |
|---|---|
| [![شاشة إعداد Wi-Fi](docs/images/hotspot.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/hotspot.jpg) | [![رسالة على الإطار](docs/images/message.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/message.jpg) |

| صفحة الإدارة (هاتف أو حاسوب) | |
|---|---|
| [![الإعدادات](docs/images/admin-reglages.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-reglages.jpg) | [![المعرض](docs/images/admin-galerie.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-galerie.jpg) |

## المعدات

| القطعة | ملاحظة |
|---|---|
| Raspberry Pi Zero W (أو Zero 2 W) | يعمل Zero 2 W أسرع بنحو 3 مرات |
| بطاقة microSD سعة 16 إلى 32 غيغابايت | يُفضَّل الفئة A1 |
| مزود طاقة micro-USB بقوة 5 فولت و2.5 أمبير | مزود جيد يمنع الأعطال |
| كابل أو محوّل mini-HDMI إلى HDMI | يحتوي Pi Zero على منفذ mini-HDMI |
| تلفاز أو شاشة HDMI | ‏HDMI-CEC ‏(Anynet+ وSimplink…) لجهاز التحكم والسكون |
| حاسوب للتثبيت | Windows ‏(Git Bash) أو macOS أو Linux |

الميزانية: نحو 30 يورو دون التلفاز.

## التثبيت باختصار

1. **جهّز البطاقة** باستخدام [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   ‏Raspberry Pi OS Lite ‏(32 بت)، الاسم `cadre`، المستخدم `cadre`، شبكة Wi-Fi المنزل، وSSH
   بمفتاحك العام (ويُستخدم أيضًا لتوقيع التحديثات).
2. **ثبّت الإطار** من حاسوبك:

</div>

```bash
git clone https://github.com/54yhbw7nfw-spec/cadre-photo.git
cd cadre-photo
./install.sh cadre@cadre.local     # يطلب كلمة مرور المستخدم مرة واحدة
ssh cadre@cadre.local sudo reboot
```

<div dir="rtl">

3. **صِله بالتلفاز**: بعد دقيقة ونصف، يقودك رمز QR إلى صفحة الإدارة. أضف صورك وانتهى الأمر.

التفاصيل (بالفرنسية): [التوثيق التقني](docs/technique.md) ·
[التحديث عن بُعد](docs/mise-a-jour.md) ·
[دفتر الشروط](docs/cahier-des-charges.md).

## من الداخل

‏Python 3 ‏(pygame / SDL2 مع KMSDRM للعرض، وFlask لصفحة الإدارة، وPillow للصور)،
NetworkManager، systemd. يعمل كل ذلك بذاكرة 512 ميغابايت على معالج أحادي النواة من عام 2017،
مع انتقالات سلسة بمعدل 60 صورة في الثانية.

الترخيص: [CC0](LICENSE) (ملكية عامة).

</div>
