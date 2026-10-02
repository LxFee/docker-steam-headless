# 中文输入（Debian / Xfce X11）

Debian 镜像包含 **Fcitx5、拼音、GTK2/GTK3 和 Qt5/Qt6 输入模块、Noto CJK 字体**。
在默认 `MODE=primary` 桌面会话中自动启动，使用桌面用户及同一 DISPLAY / D-Bus session。
不需要将系统语言改成中文；默认英文 UTF-8 locale 可以输入、显示中文。

## 使用

1. 构建本 Fork 的镜像（上游镜像不包含本次改动）：
   ```sh
   docker build -f Dockerfile.debian -t steam-headless:chinese .
   ```
   将现有部署的 image 改为该镜像并重新创建容器，保留原有 home 挂载。
2. 通过 noVNC 或 Moonlight 进入桌面，打开文本编辑器，按 **Ctrl+Space** 切换输入法。
   输入 `nihao`，按空格选择候选词。
3. 从应用菜单打开 **Fcitx 5 Configuration**，或在桌面终端运行 `fcitx5-configtool`，
   修改输入法、快捷键和拼音选项。若列表中没有 Pinyin，关闭 “Only Show Current Language” 后添加。

新用户默认使用 `keyboard-us` + `pinyin`。启动脚本仅在 `~/.config/fcitx5` 不存在时
创建默认 profile；已有目录、配置或符号链接均保持原样，升级不覆盖用户词库及配置。
已有目录但没有 profile 的用户请通过配置工具手动添加 Pinyin。
这些设置随持久化 home 保留，不放入每次启动复制的 home 模板。

## 关闭或使用其他输入法

给容器设置 `ENABLE_FCITX5=false` 可关闭本项目的自动启动及环境变量设置。
用户自行添加的 Xfce 自动启动项不受该开关影响。
若显式设置了不同的 `GTK_IM_MODULE`、`QT_IM_MODULE` 或 `XMODIFIERS`（包括空值），
脚本也会跳过 Fcitx5，保留原选择。默认只给桌面及其子进程设置：

```text
GTK_IM_MODULE=fcitx
QT_IM_MODULE=fcitx
XMODIFIERS=@im=fcitx
```

若之前自行安装过 IBus/Fcitx 等，请在 **Session and Startup** 中检查原有自动启动项，
避免两个输入法框架同时运行。脚本不会删除或改写这些项目。

## 排查与支持范围

- 在桌面终端运行 `pgrep -a fcitx5`、`fcitx5-diagnose`、`fcitx5-configtool`。
  查看 `~/.cache/log/desktop.log` 和 `desktop.err.log`。可用 `fc-match :lang=zh-cn` 检查字体。
- 远程输入推荐在客户端使用英文键盘，发送拼音字母，由容器端显示候选框；
  客户端中文 IME、浏览器快捷键拦截或 Moonlight 按键映射可能影响输入。
- GTK/Qt/XIM 原生 X11 程序是主要目标。Flatpak 的运行时模块和 D-Bus 沙箱权限、
  Steam 内嵌界面、Wine/Proton 和游戏自身的输入处理可能不同，不保证所有程序兼容。
  先在原生文本编辑器验证，再排查目标应用；不要为此开放全部沙箱权限。
- `MODE=secondary` 不启动本项目桌面，因此不会启动 Fcitx5，应由宿主桌面提供输入法。
- **Arch 仍为实验性、不支持的镜像，现有 Actions 已禁用其构建。**
  本次仅给 Debian 添加软件包和默认开关；共享脚本在 Arch 默认不启用，未扩展 Arch 支持。
- 当前验证为包索引检查及无显示服务器的脚本测试；完整镜像构建和远程桌面实测仍需执行。

本地静态验证：

```sh
bash -n overlay/usr/bin/configure-input-method.sh overlay/usr/bin/start-desktop.sh tests/input-method.sh
bash tests/input-method.sh
git diff --check
```
