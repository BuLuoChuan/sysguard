Name:           sysguard
Version:        1.2.1
Release:        1
Summary:        Linux 系统管理与优化工具（GUI）

License:        GPL-3.0
URL:            https://github.com/BuLuoChuan/sysguard
BuildArch:      noarch

Requires:       python3
Requires:       smartmontools
Requires:       hdparm
Requires:       udisks2
Requires:       util-linux
Requires:       coreutils
Requires:       iproute2
Requires:       systemd
Requires:       polkit

# 依赖包名随 RPM 发行版家族略有差异，用 %if 条件适配
%if 0%{?fedora} || 0%{?rhel}
Requires:       python3-tkinter
Requires:       sg3_utils
Requires:       procps-ng
%endif
%if 0%{?suse_version}
Requires:       python3-tk
Requires:       sg3_utils
Requires:       procps
%endif

%description
SysGuard（系统管家）提供系统监控、进程与服务管理、磁盘检修（SMART/坏道）、
USB 挂载与机械硬盘停转、网络优化、垃圾清理、内存压缩与交换管理、系统优化
与安全审计。
GUI 以普通用户运行，所有需要 root 的操作统一经 pkexec 调用特权入口
sysguard-cli，入口内部做命令白名单与磁盘守卫校验，绝不触碰 SSD 与系统盘。

%prep
# 无源码归档：文件直接来自构建脚本注入的 %{sgroot}

%install
rm -rf "%{buildroot}"
mkdir -p "%{buildroot}/usr/lib/sysguard"
cp -a "%{sgroot}/lib/sysguard" "%{buildroot}/usr/lib/sysguard/"
find "%{buildroot}/usr/lib/sysguard" -name __pycache__ -type d -prune -exec rm -rf {} +
find "%{buildroot}/usr/lib/sysguard" -type d -exec chmod 0755 {} +
find "%{buildroot}/usr/lib/sysguard" -type f -exec chmod 0644 {} +
install -d -m 0755 "%{buildroot}/usr/bin" "%{buildroot}/usr/sbin"
install -m 0755 "%{sgroot}/bin/sysguard" "%{buildroot}/usr/bin/sysguard"
install -m 0755 "%{sgroot}/bin/sysguard-cli" "%{buildroot}/usr/sbin/sysguard-cli"
install -d -m 0755 "%{buildroot}/usr/share/applications"
install -m 0644 "%{sgroot}/data/sysguard.desktop" "%{buildroot}/usr/share/applications/sysguard.desktop"
install -d -m 0755 "%{buildroot}/usr/share/polkit-1/actions"
install -m 0644 "%{sgroot}/data/com.sysguard.policy" "%{buildroot}/usr/share/polkit-1/actions/com.sysguard.policy"

%files
/usr/lib/sysguard/sysguard/
/usr/bin/sysguard
/usr/sbin/sysguard-cli
/usr/share/applications/sysguard.desktop
/usr/share/polkit-1/actions/com.sysguard.policy

%post
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi

%postun
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi

%changelog
* Sat Nov 07 2026 SysGuard <root@localhost> - 1.2.1-1
- 进程管理：CPU/内存升降序排序，结束/停止/重启前二次确认，系统服务走 pkexec 密码
- 磁盘检修、磁盘空间、USB 设备各自提供页面，并按类别分组；SMART 中文专有名词与黄/红告警
- 中文环境一键切换语言环境（localectl 经 pkexec）
- 镜像源一键测网速/测延时/测稳定
- 系统优化说明中英文切换、内存压缩与交换增加功能说明
- 左侧导航按大类自动合并分类
* Sat Nov 07 2026 SysGuard <root@localhost> - 1.2.0-1
- 新增软件包修复、启动性能分析、磁盘空间深度分析、自启动项增强与定时任务审计
- 新增错误日志聚合与一键诊断报告、电源/电池健康与三档能效、网络诊断与 WiFi 节能
- 新增资源阈值告警、中文环境检测
* Wed Nov 04 2026 SysGuard <root@localhost> - 1.0.0-1
- 初始打包