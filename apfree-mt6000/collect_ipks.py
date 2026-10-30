#!/usr/bin/env python3
"""Collect apfree-wifidog + luci-app-apfree-wifidog ipk and all ipk
produced alongside them (their compiled dependencies) into output/.

Runs from the OpenWrt source root, after:
  make package/apfree-wifidog/compile package/luci-app-apfree-wifidog/compile

Why "all ipk under bin/packages" instead of parsing control Depends: ?
- ipk is an ar archive, not a plain tar, and dependency closure in OpenWrt
  is already materialised by the build: libraries that had to be compiled
  for these two packages land in bin/packages/<arch>/*/*.ipk.
- A package-only compile (not a full firmware make) keeps that set small:
  it should be the two main packages plus their library dependencies,
  not a whole firmware image's package set.
- If a main package is missing, fail loudly instead of publishing an
  empty or half release.

Outputs (under <openwrt>/output/):
  *.ipk, apfree-wifidog-mt6000-ipks.zip, PACKAGES.txt, INSTALL.md
"""
import glob
import os
import shutil
import sys
import zipfile

ROOT = os.getcwd()
PKG_DIR = os.path.join(ROOT, "bin", "packages")
OUT_DIR = os.path.join(ROOT, "output")

MAIN_PATTERNS = ["apfree-wifidog_*.ipk", "luci-app-apfree-wifidog_*.ipk"]


def main() -> int:
    if not os.path.isdir(PKG_DIR):
        print(f"ERROR: {PKG_DIR} not found, did the package compile run?", file=sys.stderr)
        return 1

    # All ipk produced by this package-only build, sorted for stable output.
    all_ipk = sorted(glob.glob(os.path.join(PKG_DIR, "**", "*.ipk"), recursive=True))
    if not all_ipk:
        print("ERROR: no ipk found under bin/packages", file=sys.stderr)
        return 1

    names = [os.path.basename(p) for p in all_ipk]
    for pat in MAIN_PATTERNS:
        prefix = pat.split("_")[0]
        if not any(n.startswith(prefix + "_") for n in names):
            print(f"ERROR: main package missing: {pat} (found: {names})", file=sys.stderr)
            return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    for src in all_ipk:
        shutil.copy2(src, os.path.join(OUT_DIR, os.path.basename(src)))

    # PACKAGES.txt: one ipk per line, as published.
    with open(os.path.join(OUT_DIR, "PACKAGES.txt"), "w", encoding="utf-8") as f:
        f.write("apfree-wifidog for GL-MT6000 (mediatek/mt7986, aarch64_cortex-a53)\n")
        f.write("ipk built by this run (main packages + compiled dependencies):\n\n")
        for n in names:
            f.write(n + "\n")

    install_md = """# 在 GL-MT6000 原厂固件上安装 apfree-wifidog

适用：GL.iNet GL-MT6000 原厂固件，OpenWrt 21.02、mediatek/mt7986。
先备份路由器配置（LuCI 系统 > 备份 / 闪存固件里生成备份）。

## 1. 把 ipk 传到路由器

把本 Release 里的 `apfree-wifidog-mt6000-ipks.zip` 解压后，
用 scp 传到路由器 /tmp，例如：

```
scp *.ipk root@192.168.8.1:/tmp/
```

原厂默认管理地址一般是 192.168.8.1，按你实际地址改。

## 2. 一次装上主包 + 依赖

在路由器 SSH 里执行（把 /tmp/*.ipk 一起交给 opkg，
让它在本地集合里解析依赖，不要一个一个装）：

```
cd /tmp
opkg install *.ipk
```

如果 opkg 报某个依赖在原厂固件里已有更新版本，不要强行
`--force-depends`，先停下来看报错的包名，再决定是跳过
那个依赖 ipk、还是先装主包测试。

## 3. 验证

```
# 核心程序是否在
ls -l /usr/bin/wifidogx /usr/bin/wdctlx
/etc/init.d/wifidogx status
# LuCI 里找 apfree-wifidog / wifidogx 菜单
```

注意：不要执行 `opkg upgrade` 全量升级原厂固件的包，
那会把原厂定制包也换掉，有变砖风险。

## 4. 防火墙说明

原厂 21.02 固件走 fw3/iptables 时代；新版 apfree 已转向
fw4/nftables。本次编译用的是 21.02 同代 feed 里的 apfree，
装机后若 wifidogx 启动报防火墙后端错误，先看它的日志，
不要直接改防火墙配置。
"""
    with open(os.path.join(OUT_DIR, "INSTALL.md"), "w", encoding="utf-8") as f:
        f.write(install_md)

    zip_path = os.path.join(OUT_DIR, "apfree-wifidog-mt6000-ipks.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.write(os.path.join(OUT_DIR, n), arcname=n)
        z.write(os.path.join(OUT_DIR, "PACKAGES.txt"), arcname="PACKAGES.txt")
        z.write(os.path.join(OUT_DIR, "INSTALL.md"), arcname="INSTALL.md")

    print(f"Collected {len(names)} ipk into {OUT_DIR}:")
    for n in names:
        print("  " + n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
