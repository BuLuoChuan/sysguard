# SysGuard（系统管家）

面向 Linux 的系统管理与优化 GUI 工具，**零第三方依赖**（仅 Python 标准库
+ Tkinter）。GUI 以普通用户运行，所有 root 写操作统一经 `pkexec` 调用
特权入口 `sysguard-cli`，入口内部做命令白名单与磁盘守卫校验。

> **测试版（Beta）**：本软件尚未经过完整测试，可能存在缺陷或兼容性问题。
> 请仅在测试环境中使用；涉及磁盘、系统配置或网络的操作可能影响系统，
> 使用前请备份重要数据。请勿将此版本用于生产环境。

## 项目结构

```
sysguard/
├── lib/sysguard/            # Python 包（顶层包 sysguard）
│   ├── __init__.py          # 版本/名称
│   ├── __main__.py          # python3 -m sysguard 入口
│   ├── config.py            # 常量/依赖映射/主题
│   ├── core/                # 纯逻辑层（不依赖 GUI，可独立测试）
│   │   ├── shell.py         # 安全执行出口（run/pkexec/工具函数）
│   │   ├── privileged.py    # 特权入口：白名单 + 磁盘守卫（root）
│   │   ├── sysinfo.py process.py disk.py usb.py network.py
│   │   ├── mirror.py        # 镜像源检测/测速/切换（apt + rpm）
│   │   ├── cleanup.py memory.py optimize.py security.py
│   └── ui/                  # Tkinter 界面
│       ├── app.py           # 主窗口 + 侧边栏导航
│       ├── widgets.py       # 通用组件
│       └── pages/           # 10 个功能页
├── bin/sysguard             # /usr/bin 启动器
├── bin/sysguard-cli         # /usr/sbin 特权入口
├── data/sysguard.desktop    # 桌面启动器
├── data/com.sysguard.policy # polkit 授权策略
├── debian/                  # control.template/postinst/prerm/postrm
├── rpm/sysguard.spec        # RPM 打包定义（noarch）
├── arch/PKGBUILD            # Arch Linux 打包定义（arch=any）
├── install.sh               # 源码安装脚本（root，可卸载）
├── build.sh                 # 打包脚本（架构无关 all deb）
├── build-rpm.sh             # 打包脚本（noarch rpm）
├── MANUAL.md                # 用户手册
└── README.md                # 本文件
```

## 本地运行（不安装）

```bash
PYTHONPATH=lib python3 -m sysguard
```

## 安装

SysGuard 提供四种安装方式，全部**架构无关**（x86_64 / ARM64 通用）：

| 方式 | 适用系统 | 安装命令 | 卸载命令 |
| --- | --- | --- | --- |
| deb 包 | Debian / Ubuntu | `sudo dpkg -i sysguard_1.0.0_all.deb` | `sudo apt-get purge sysguard` |
| rpm 包 | Fedora / RHEL / CentOS / Rocky / Alma | `sudo dnf install ./sysguard-1.0.0-1.noarch.rpm` | `sudo rpm -e sysguard` |
| rpm 包 | openSUSE | `sudo zypper install ./sysguard-1.0.0-1.noarch.rpm` | `sudo rpm -e sysguard` |
| 源码脚本 | 任意发行版 | `sudo ./install.sh` | `sudo ./install.sh --uninstall` |
| PKGBUILD | Arch / Manjaro | `cd arch && makepkg -si` | `sudo pacman -R sysguard` |

> 安装后启动：终端执行 `sysguard`，或应用菜单点「系统管家 / SysGuard」。

### GitHub 测试版下载

在 [v1.0.0-beta.1 Release](https://github.com/BuLuoChuan/sysguard/releases/tag/v1.0.0-beta.1)
下载 deb、rpm 安装包、源码安装脚本和源码归档。下载后按下表选择对应安装
方式；本测试版尚未经过完整测试，请先阅读本说明并在测试环境中使用。

## 功能建议与反馈

欢迎提交你认为 SysGuard 还需要的功能。请先浏览[现有功能建议](https://github.com/BuLuoChuan/sysguard/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)，
避免重复提交；如已有相同建议，可以在原 issue 下补充场景或 👍 投票。

[提交功能建议](https://github.com/BuLuoChuan/sysguard/issues/new?template=feature_request.yml)
时，请说明要解决的问题、预期行为和使用场景。如果建议与特定 Linux 发行版
或桌面环境有关，也请注明名称和版本。

## 构建 deb

```bash
./build.sh 1.0.0
# 产出 build/sysguard_1.0.0_all.deb
```

纯 Python 脚本，无编译产物，架构无关，产出单个 `Architecture: all` 包，
x86_64 与 ARM64 通用。

## 构建 rpm

```bash
./build-rpm.sh 1.0.0
# 产出 build/sysguard-1.0.0-1.noarch.rpm
```

`BuildArch: noarch`（架构无关），同一份 rpm 可用于 x86_64 / aarch64 等
任意架构。在 Fedora/RHEL/CentOS/openSUSE 上需先 `dnf install rpm-build`；
在 Debian/Ubuntu 无 root 环境，脚本会自动探测便携 rpmbuild 完成构建。

## 源码安装（install.sh）

无 deb/rpm 管辖的环境（或临时从源码安装），以 root 运行安装脚本，文件布局
与 deb/rpm 完全一致：

```bash
sudo ./install.sh              # 安装
sudo ./install.sh --uninstall  # 卸载
```

## Arch Linux（PKGBUILD）

```bash
cd arch
makepkg -si
```

产出 `arch=('any')`（架构无关）包。上传 GitHub 后可将 PKGBUILD 的
`source` 改为发布的 tar.gz 地址以符合 AUR 惯例。

## 安装路径

| 文件 | 安装位置 |
| --- | --- |
| 源码包 | `/usr/lib/sysguard/sysguard/` |
| 启动器 | `/usr/bin/sysguard` |
| 特权入口 | `/usr/sbin/sysguard-cli` |
| 桌面入口 | `/usr/share/applications/sysguard.desktop` |
| polkit 策略 | `/usr/share/polkit-1/actions/com.sysguard.policy` |

## 安全设计

- **无 shell 拼接**：所有系统命令经 `subprocess` 列表参数执行；
- **命令白名单**：特权入口仅接受 `COMMANDS` 中登记的子命令；
- **磁盘守卫**：停转/唤醒前校验 `ROTA=1`（机械盘）、非系统盘、
  且身份经 `/dev/disk/by-id/` 确认，绝不触碰 SSD 与系统盘（`sda`、
  `nvme0n1`、`nvme1n1` 硬排除）；
- **成功判据**：停转以「STANDBY，或 LCC 增长且 C0 不变」双判据验证。

## 依赖

`python3 python3-tk smartmontools sg3-utils hdparm udisks2 util-linux
coreutils procps iproute2 systemd policykit-1`；推荐 `ufw e2fsprogs`。

## 许可

按使用需求自行调整，代码仅作演示/工具用途。