# SysGuard（系统管家）用户手册

SysGuard 是一款面向 Linux 的系统管理与优化图形工具，零第三方依赖
（仅 Python 标准库 + Tkinter）。提供系统监控、进程/服务、磁盘检修、
USB 挂载与机械硬盘停转、网络优化、垃圾清理、软件修复、内存压缩、
系统优化、启动分析、定时任务审计、电源电池、资源告警、日志诊断、
中文环境检测、镜像源切换与安全审计共十八个功能页面，并按七个大类
在左侧导航中自动分组。

> **测试版（Beta）**：本软件尚未经过完整测试，可能存在缺陷或兼容性问题。
> 请仅在测试环境中使用；涉及磁盘、系统配置或网络的操作可能影响系统，
> 使用前请备份重要数据。请勿将此版本用于生产环境。

---

## 1. 安装

SysGuard 提供四种安装方式（均架构无关，x86_64 / ARM64 通用）：

| 方式 | 适用系统 | 安装 | 卸载 |
| --- | --- | --- | --- |
| deb | Debian / Ubuntu | `sudo apt install ./sysguard_1.2.1_all.deb`（自动拉取依赖） | `sudo apt-get purge sysguard` |
| rpm | Fedora / RHEL / CentOS / Rocky / Alma / openSUSE | `sudo dnf install ./sysguard-1.2.1-1.noarch.rpm`（openSUSE 用 `zypper install`） | `sudo rpm -e sysguard` |
| 源码 | 任意发行版 | `sudo ./install.sh` | `sudo ./install.sh --uninstall` |
| PKGBUILD | Arch / Manjaro | `cd arch && makepkg -si` | `sudo pacman -R sysguard` |

### GitHub 测试版下载

在 [v1.2.1 Beta Release](https://github.com/BuLuoChuan/sysguard/releases/tag/v1.2.1-beta.1)
下载 deb、rpm、源码归档、源码安装脚本及 `SHA256SUMS`。本版本尚未经过完整测试，
请仅在测试环境使用，并在安装前核对校验和、备份重要数据。

### 依赖（安装 deb 时自动解析）

`python3`、`python3-tk`、`smartmontools`、`sg3-utils`、`hdparm`、
`udisks2`、`util-linux`、`coreutils`、`procps`、`iproute2`、
`systemd`、`policykit-1`；推荐 `ufw`、`e2fsprogs`。

### 安装 deb

SysGuard 为纯 Python 脚本，打包为**架构无关**的单个 `all` deb，x86_64
与 ARM64（如树莓派、RK3588）通用。

```bash
# 推荐：交给 apt 解析依赖并从软件源自动下载安装
sudo apt install ./sysguard_1.2.1_all.deb

# 或者先用 dpkg 安装，再补齐依赖：
sudo dpkg -i sysguard_1.2.1_all.deb
sudo apt-get -f install -y
```

> `dpkg -i` 本身**不会**自动下载依赖；`apt install ./xxx.deb` 才会自动
> 解析并从已配置的软件源拉取依赖（离线环境需事先备齐依赖包）。

### 安装 rpm（Fedora / RHEL / CentOS / openSUSE 等）

SysGuard 为纯 Python 脚本，打包为**架构无关**的 noarch RPM，同一份
`sysguard-1.2.1-1.noarch.rpm` 可安装在 x86_64、aarch64 等任意架构。

```bash
# Fedora / RHEL 8+ / CentOS / Rocky / Alma
sudo dnf install ./sysguard-1.2.1-1.noarch.rpm
# 或
sudo rpm -ivh sysguard-1.2.1-1.noarch.rpm

# openSUSE
sudo zypper install ./sysguard-1.2.1-1.noarch.rpm
```

卸载：`sudo rpm -e sysguard`（或 `dnf remove sysguard`）。

### 源码安装（install.sh）

在无法使用 deb/rpm 的环境，可直接从源码安装（文件布局与打包安装一致）：

```bash
sudo ./install.sh              # 安装
sudo ./install.sh --uninstall  # 卸载
```

### Arch Linux（PKGBUILD）

```bash
cd arch
makepkg -si
```

产出架构无关（arch=any）包并安装。

### 启动

- 应用菜单中点击「系统管家 / SysGuard」，或终端执行：

```bash
sysguard
```

### 卸载

```bash
sudo apt-get remove sysguard     # 卸载
sudo apt-get purge sysguard      # 彻底卸载（含清理本包写入的 sysctl 配置）
```

---

## 2. 权限模型（重要）

GUI 以**普通用户**运行，读取信息不需要密码。所有会**改变系统状态**的
操作（终止进程、启停服务、卸载/停转磁盘、启用 BBR、改 swappiness、
apt 清理、卸载内核、开关 ufw、粉碎文件、修复软件包、自启项开关与延时、
能效切换、WiFi 节能等）都会弹出 **pkexec 授权框**，输入管理员密码后，
由特权入口 `sysguard-cli` 以 root 身份执行。

特权入口内部做了**命令白名单 + 参数强校验 + 磁盘守卫**：
- 只允许集合内的子命令，其余一律拒绝；
- 所有系统命令以列表参数执行，绝不拼接 shell 字符串；
- 磁盘类操作先校验身份，**绝不触碰 SSD 与系统盘**。

> 若点击后无任何反应，请确认已安装 `policykit-1` 且当前用户为
> `sudo`/`wheel` 组成员。

---

## 3. 功能说明

### 3.1 系统概览
实时仪表盘：CPU/内存/交换占用、负载、运行时间、上下行速率、最高温度、
各挂载点磁盘使用率。每 2 秒自动刷新。

### 3.2 进程服务
- 查看进程（PID/用户/CPU/内存/RSS/命令行），支持关键字搜索；
- 支持按 **CPU / 内存 从高到低、从低到高** 四种方式排序（下拉选择）；
- 选中进程「结束进程」前弹出确认框（默认 TERM，必要时可切换 KILL）；
- 下半区为 systemd 服务列表，可对选中服务「启动/停止/重启」，
  执行前弹确认框；系统服务操作统一走 pkexec，弹出管理员密码确认。

### 3.3 磁盘检修（SMART）
- 列出磁盘容量、类型、接口、型号和挂载点；
- 「读取 SMART」经授权后加载各盘 SMART 属性；
- 「SMART 详情」以**中文专有名词**逐项展示（当前值/最差值/阈值/原始值），
  并分级着色：❌ 红色异常（坏扇区、不可纠正错误等）、
  ⚠️ 黄色警告（CRC 错误、重分配事件等）。

### 3.4 磁盘空间
- 列出真实挂载点（容量/已用/可用/占用率）；
- 扫描大目录、大文件并检测 inode 使用率。

### 3.5 USB 设备
- 列出 USB 存储设备；
- 挂载或卸载选中设备的分区；
- 对符合安全检查的机械硬盘发送停转或唤醒命令。

**停转安全规则（不可违反）：** 仅对「机械盘（ROTA=1）+ 非系统盘」开放停转；
系统盘（含 `/`、`/boot`、`/boot/efi`）与 SSD 一律拒绝；设备身份必须通过
`/dev/disk/by-id/` 白名单确认；停转前请先卸载该盘所有分区。停转结果经
**STANDBY 或 LCC 增长且 C0 不变** 双重判据验证。

### 3.6 网络优化与测试
- 接口信息（IPv4/IPv6/MAC/状态）；
- 实时上下行速率；
- 连通性/延迟 ping 测试；
- 一键启用 BBR 或恢复 CUBIC（写入 `/etc/sysctl.d/99-sysguard-bbr.conf`）；
- 查看路由表（`ip route`）；
- WiFi 电源管理：选择无线接口，一键「开启节能（省电）」或
  「关闭节能（高能）」（需 `iw` 工具，写操作需 pkexec 授权）；
- 查看当前 DNS 服务器。

### 3.7 垃圾清理
先估算各项目空间，再逐项确认清理：
APT 下载缓存、autoclean、不再需要的软件包（autoremove）、systemd
日志（journal 清理至 100M）、`/tmp` 临时文件、缩略图缓存、旧内核镜像。

> 清理动作均需 pkexec 授权。

### 3.8 软件包修复（依赖自愈）
- 检测损坏/半装（`dpkg --audit`）与版本锁定（hold）的包；
- 「修复损坏/半装依赖」执行 `dpkg --configure -a` + `apt --fix-broken install`；
- 「检测孤立依赖」经特权入口预演 `apt autoremove`，再一键自动移除。

> 面向 Debian/Ubuntu；修复操作需 pkexec 授权。

### 3.9 内存交换
- 内存/交换使用概况；
- `vm.swappiness` 读写（0–100，桌面建议 10–30，持久化到
  `/etc/sysctl.d/99-sysguard-swap.conf`）；
- zram 与 zswap 状态检测；
- 页内提供「功能说明」（可中英切换）：讲解 swappiness / zram / zswap
  的含义与适用场景。

### 3.10 系统优化（开机自启增强）
- 开机自启服务审计：列出 systemd 已启用单元，并**显示每个单元的功能说明**
  （Description），标注是否已被本软件设为「延时启动」；
- 对选中自启项可「启用 / 禁用」，或「延时启动」——输入延时秒数后由本软件
  生成 `sysguard-delay-<单元>.timer/.service` 在开机 N 秒后再拉起该服务；
  「取消延时」则恢复为普通开机自启；
- 已安装内核列表（标注运行中内核，可卸载旧内核）；
- 电源/交换优化建议，支持**中文 / English 一键切换**。

### 3.11 启动性能分析
- 总启动时间（`systemd-analyze time`：固件/引导/内核/用户态）；
- 启动耗时 Top 服务（`systemd-analyze blame`）；
- 关键启动链路（`systemd-analyze critical-chain`），定位拖慢启动的环节。

### 3.12 定时任务审计
- systemd timer 列表（下次触发时间、单元、激活目标）；
- 系统级 cron 任务（`/etc/crontab` 与 `/etc/cron.d/*` 的调度、用户、命令）。

### 3.13 电源与电池
- 电池健康（型号/电量/状态/健康度，经 `upower`）、供电状态（是否接电源）；
- 三档能效切换：高性能 / 平衡 / 省电（`power-profiles-daemon`）。
  若未安装守护进程，本页给出安装提示：`sudo apt install power-profiles-daemon`。

### 3.14 资源阈值告警
- 直观展示当前 CPU / 内存 / 交换 / 磁盘 / 温度；
- 可分别设定各指标阈值（默认 CPU/内存/交换/磁盘 90%、温度 80°C）；
- 「开始监测」后按设定间隔周期检测，超限时在界面提示并弹出系统弹窗；
- 页内「立即检查」可手动触发一次检测。

### 3.15 日志诊断
- 系统日志错误（`journalctl -p err`）与内核错误（`dmesg -l err`）聚合视图；
- 待重启更新检测（`/var/run/reboot-required`）；
- 「一键诊断报告」汇总系统信息/CPU/内存/磁盘/网络/错误日志，可导出为文本。

### 3.16 镜像源测速与切换
自动识别当前发行版与包管理器（apt / dnf / yum / zypper），并：
- 列出该发行版可用的镜像（官方 + 阿里云 / 清华 / 中科大 / 腾讯 / 网易等）；
- 「测网速」实测镜下载速度与可达性（标准库，无须第三方工具）；
- 「测延时」对镜像站点做多次 TCP 握手（443 端口），给出平均/最值延时；
- 「测稳定性」多次测速，统计成功率、平均/最值速度、抖动与平均延时；
- 「应用选中」一键切换镜像源——**切换前自动备份当前源**，可随时「还原备份」；
- 支持 apt（Debian/Ubuntu：覆盖 `/etc/apt/sources.list`）与 rpm 系
  （Fedora：fedora/updates 仓库；CentOS/Rocky/Alma：BaseOS/AppStream；
  openSUSE：OSS 仓库），生成 `.repo` 并停用其它冲突源。

> 切换与还原动作需 pkexec 授权；切换后建议用包管理器更新一次索引。

### 3.17 安全中心（不含防病毒）
- ufw 防火墙开关、放行/拒绝端口；
- 监听端口审计（协议/地址/端口/进程）；
- 可疑进程识别（高 CPU 或高内存）；
- 文件粉碎（`shred -u -z -n 3`，仅允许 `/home`、`/media`、`/mnt`、
  `/tmp` 下文件，禁止系统关键路径）。

### 3.18 中文环境
- 中文字体检测（`fc-list :lang=zh`）；
- 输入法框架检测（fcitx5 / fcitx / ibus 是否安装并运行）；
- 系统中文语言环境检测（当前 LANG 与中文 locale 是否已生成）；
- 字体/输入法缺失时给出对应**安装/配置指令**（文本展示，不代为执行）；
- **「一键切换语言环境」**：可一键切换为中文（zh_CN.UTF-8）或英文
  （en_US.UTF-8）——经 pkexec 授权后生成中文 locale 并写入系统 locale
  配置（`localectl set-locale`），重新登录后生效。

---

## 4. 恢复到默认值

- BBR：在「网络优化」页点「恢复默认(CUBIC)」；
- WiFi 节能：在「网络优化」页选接口后点「关闭节能（高能）」；
- 延时启动：在「系统优化」页选中该自启项点「取消延时」；
- 能效模式：在「电源电池」页切回「平衡」；
- swappiness：在「内存交换」页改回原值；
- ufw：在「安全中心」停用防火墙；
- 镜像源：在「镜像源」页点「还原备份」。

---

## 5. 常见问题

| 现象 | 处理 |
| --- | --- |
| 点击需要授权的按钮无反应 | 安装 `policykit-1`，确认用户属 `sudo` 组 |
| SMART 读不到/温度为 — | 该盘不支持 SMART 或需授权；点「读取 SMART」后仍有问题属正常（USB 桥接盘常如此） |
| 停转失败「未验证到 STANDBY」 | USB 桥接主控不支持，属正常；以 LCC/C0 判据为准 |
| 运行报缺 `python3-tk` | `sudo apt install python3-tk` |
| 想卸载旧内核被拒 | 系统禁止卸载当前运行内核 |
| 镜像测速显示「不可达」 | 该镜像暂不可访问或当前网络受限，换一个镜像再试 |
| rpm 系无法识别发行版 | 稍后手动运行 `dnf` / `yum` / `zypper` 一次以生成源 |

---

## 6. 免责声明

停转磁头、卸载内核、粉碎文件、清理日志等操作有**不可逆**风险，
请务必在操作前确认目标并备份重要数据。软件按「现状」提供，不承担
因误操作造成的数据或系统损失。