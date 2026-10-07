# Cadre photo

[Français](README.md) · [English](README.en.md) · [Español](README.es.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [Română](README.ro.md) · **中文**

**用一块 20 欧元的树莓派，把任何电视变成家庭电子相框。**

照片全屏轮播，过渡平滑，并显示拍摄日期和地点。家人可以直接用手机添加照片，无需安装应用、
无需注册账号；也可以把照片放进 iCloud 共享相簿，相框会自动同步。专为放在亲人家中、装好就
不用管而设计：扫二维码即可连接 Wi-Fi，用电视遥控器操作，并可远程更新。

▶ [观看介绍视频（中文）](docs/video/cadre-photo-mode-d-emploi-zh.mp4)

## 功能

[![相框画面：往年回忆、地点、时间和天气](docs/images/ecran.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/ecran.jpg)

- **全屏幻灯片**：淡入淡出、滑动、擦除等过渡效果；竖拍和横拍照片都能妥善适配屏幕；显示日
  期、地点（« Sallanches, France »）以及「2 年前」的往年回忆。
- **用手机添加照片**：扫描电视上显示的二维码，选择照片即可。照片在上传前会自动压缩，即使
  Wi-Fi 信号弱也很快。
- **iCloud 共享相簿**：粘贴链接，相框每 30 分钟同步一次。
- **无需键盘即可设置**：没有已知 Wi-Fi 时，相框会自己创建网络并显示二维码，用手机选择家里
  的 Wi-Fi 即可。
- **电视遥控器操作**（HDMI-CEC）：下一张、上一张、暂停、显示二维码。
- **相框留言**（「奶奶生日快乐！」），以横幅或全屏方式显示，可设定起止日期。
- **低调显示时间和天气**，夜间定时待机（电视自动关闭并重新开启）。
- **收藏、隐藏照片、选择轮播内容**（相簿、上传的照片、时间段）。
- **远程更新**：点击两下即可完成，由您本人签名，出现问题时自动恢复到上一版本；可生成诊断
  报告发送给您。
- **7 种语言**：管理页面和相框屏幕支持法语、英语、西班牙语、德语、葡萄牙语、罗马尼亚语和中文。
- **注重隐私**：所有内容都保存在相框中，无需账号，也不依赖任何在线服务。

| Wi-Fi 设置 | 家人留言 |
|---|---|
| [![Wi-Fi 设置画面](docs/images/hotspot.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/hotspot.jpg) | [![相框留言](docs/images/message.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/message.jpg) |

| 管理页面（手机或电脑） | |
|---|---|
| [![设置](docs/images/admin-reglages.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-reglages.jpg) | [![图库](docs/images/admin-galerie.jpg)](https://raw.githubusercontent.com/54yhbw7nfw-spec/cadre-photo/main/docs/images/admin-galerie.jpg) |

## 所需硬件

| 部件 | 说明 |
|---|---|
| Raspberry Pi Zero W（或 Zero 2 W） | Zero 2 W 启动速度约快 3 倍 |
| 16 至 32 GB microSD 卡 | 最好选择 A1 等级 |
| Micro-USB 5 V、2.5 A 电源 | 好的电源可避免死机 |
| Mini-HDMI 转 HDMI 线或转接头 | Pi Zero 使用 mini-HDMI 接口 |
| 一台电视或 HDMI 显示器 | 支持 HDMI-CEC（Anynet+、Simplink 等）即可使用遥控器和待机 |
| 一台用于安装的电脑 | Windows（Git Bash）、macOS 或 Linux |

预算：约 30 欧元（不含电视）。

## 安装步骤概要

1. 用 [Raspberry Pi Imager](https://www.raspberrypi.com/software/) **准备存储卡**：选择
   Raspberry Pi OS Lite（32 位），主机名 `cadre`，用户名 `cadre`，填写家中 Wi-Fi，并启用
   使用您公钥的 SSH（该密钥也用于为更新签名）。
2. 在电脑上**安装相框程序**：
   ```bash
   git clone https://github.com/54yhbw7nfw-spec/cadre-photo.git
   cd cadre-photo
   ./install.sh cadre@cadre.local     # 会询问一次用户密码
   ssh cadre@cadre.local sudo reboot
   ```
3. **连接电视**：大约一分半钟后，屏幕上的二维码会带您进入管理页面。添加照片，大功告成。

详细文档（法语）：[技术文档](docs/technique.md) ·
[远程更新](docs/mise-a-jour.md) ·
[需求说明](docs/cahier-des-charges.md)。

## 技术实现

Python 3（显示使用 pygame / SDL2 KMSDRM，管理页面使用 Flask，图片处理使用 Pillow）、
NetworkManager、systemd。整套程序在 2017 年的单核处理器和 512 MB 内存上运行，过渡动画流畅，
达到每秒 60 帧。

许可证：[CC0](LICENSE)（公有领域）。
