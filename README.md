# GL-MT6000 apfree-wifidog 编译仓库（GitHub Action 包）

目标：给 GL.iNet GL-MT6000 **原厂固件**编译 `luci-app-apfree-wifidog`
及核心程序 `apfree-wifidog`，并把**主包 + 本次编译产出的全部依赖 ipk**
一起上传到 Release。

## 0. 先说清楚的三个前提（别跳过）

1. **截图对应的原厂固件**：OpenWrt 21.02-SNAPSHOT、target
   `mediatek/mt7986`、内核 5.4.238、架构 `aarch64_cortex-a53`。
   本包的编译树特意选了同代的 `hanwckf/immortalwrt-mt798x`
   `openwrt-21.02` 分支（该分支本身支持 mt7986 / glinet_gl-mt6000，
   同为 21.02 + 内核 5.4），而不是官方 21.02（无 mt7986）或
   23.05/24.10（ABI 与防火墙时代都不同）。
2. **这不是 GL.iNet 原厂源码树**。原厂没有公开等价的 SDK，
   所以产出的 ipk 只能说是“同代 21.02、mt7986 架构下编译的”，
   装机前必须备份，装机后必须先验证 `wifidogx` 能否启动、
   LuCI 菜单是否出现，再投入使用。不要 `opkg upgrade` 全量升级。
3. **防火墙时代风险**：原厂 21.02 走 fw3/iptables；新版 apfree
   已转向 fw4/nftables 并停了 fw3 支持。本包用 21.02 同代 feed
   里的 apfree，workflow 里会把 feed 中 apfree 的版本与依赖打到
   日志里——如果日志里已经是只支持 fw4 的新版，第一次构建失败
   或装机后防火墙报错就是这个原因，不要硬装。

## 1. 建库用法（等你建好 GitHub 库后）

1. 新建一个空 GitHub 仓库（公开或私有均可，Action 跑在你自己的仓库里）。
2. 把本包里的全部文件按原路径复制到仓库根目录：
   - `.github/workflows/build-apfree-mt6000.yml`
   - `apfree-mt6000/apfree-mt6000.config`
   - `apfree-mt6000/collect_ipks.py`
   - `README.md`（本文件，可选）
3. Push 后到仓库的 **Actions** 页，选
   `Build apfree-wifidog for GL-MT6000`，点 **Run workflow**。
4. 构建成功后，到 **Releases** 页下载
   `mt6000-apfree-build-<编号>`：
   - `apfree-wifidog_*.ipk`：核心程序
   - `luci-app-apfree-wifidog_*.ipk`：LuCI 界面
   - 其余 `*.ipk`：本次编译产出的依赖库
   - `apfree-wifidog-mt6000-ipks.zip`：全部 ipk + 安装说明，一次下载
   - `PACKAGES.txt` / `INSTALL.md`：清单与装机步骤
5. 装机步骤见 Release 里的 `INSTALL.md`（核心是：备份 → scp 到
   `/tmp` → `opkg install *.ipk` 一次装上 → 验证 wifidogx 与 LuCI 菜单）。

## 2. 这个包里有什么

| 文件 | 作用 |
| --- | --- |
| `.github/workflows/build-apfree-mt6000.yml` | GitHub Action：克隆 21.02 树 → 更新 feeds → 加 luci-app → 只编译两个包 → 收集 ipk → 发 Release |
| `apfree-mt6000/apfree-mt6000.config` | 最小配置：只定 mt7986 + gl-mt6000 目标 + 两个主包，依赖交给 `make defconfig` 解析；**不要**照抄别的树生成的完整 .config（MT3000 run6 就是跨树完整 .config 被 `make defconfig` 以退出码 2 拒绝） |
| `apfree-mt6000/collect_ipks.py` | 收集脚本：主包缺失就失败，不发空 Release；把 `bin/packages` 下本次产出的全部 ipk、清单、安装说明、zip 一并放到 `output/` |

## 3. 关键实现点

- **只编包，不编固件**：`make package/apfree-wifidog/compile
  package/luci-app-apfree-wifidog/compile`，不跑全量 `make`。
  工具链仍需先编，整体通常在 1 小时内，远短于整机固件的 1–3 小时。
- **LuCI 包的放法**：上游 `luci-app-apfree-wifidog` 的 Makefile 写的是
  `include ../../luci.mk`（相对 `feeds/luci/applications/` 而言）。
  workflow 不赌 feed 索引能不能找到新加的包，而是把它放进
  `package/luci-app-apfree-wifidog/`，并把那行改成
  `include $(TOPDIR)/feeds/luci/luci.mk`，确定性更高。
  该 LuCI 包是 JS 界面（`resources/view/*.js` + `menu.d`），
  在原厂 21.02 的 LuCI 上是否完整显示，装机后以实际菜单为准。
- **依赖怎么算“全部”**：包编译时必须编的库都会落到
  `bin/packages/aarch64_cortex-a53/`，收集脚本把这批 ipk 全收，
  而不是只收两个主包。已在原厂固件里自带的库（如 libc）不会
  重复出现，属正常。
- **Release 优先于 Artifact**：Artifact 会过期，Release 不会，
  且下载页稳定，符合之前固件包的交付习惯。

## 4. 如果构建失败，先看这几处

- `Build packages only` 步只跑十几秒就挂：本地已复现的根因是
  **单包编译不会自动先编工具链**。直接跑包编译时，
  `package/libs/toolchain` 会去拷
  `staging_dir/toolchain-.../lib/ld-musl-*.so*`，而工具链没建起来、
  那个目录是空的，于是几十秒内以退出码 2 挂掉，根本没到 apfree
  源码那一步。本包已在包编译前加了
  `make tools/install toolchain/install` 一步，这一步在 runner 上
  会比较久（编 gcc/musl 工具链），不要删。
- 包编译时 ipset 报 `Invalid kernel source directory
  /lib/modules/.../source`，或 cryptodev-linux 报
  `No rule to make target '.../linux-5.4.284/.config'`：
  这是内核没编好。apfree 的依赖（ipset、cryptodev、kmod-ipt-*）
  需要内核源码，tools + toolchain 之后还必须先跑
  `make target/linux/compile`，本包已在包编译前加了这一步。
- 包目标路径：feed 里的包目标必须是
  `package/feeds/packages/<包名>/compile`，直接写
  `package/<包名>/compile` 会报 No rule to make target。
  本包已按此修正；自己放进 `package/` 的 LuCI 包则保持
  `package/luci-app-apfree-wifidog/compile`。
- 配置里必须开 `CONFIG_TARGET_MULTI_PROFILE=y`，否则单设备模式下
  gl-mt6000 的设备选择会被 `make defconfig` 丢掉。
- `Load package configuration` 步：两个主包有没有被 `make defconfig`
  选中（日志里 grep 的结果）。没选中就说明 feed / luci 包路径变了。
- `Update feeds` 步打出的 apfree 版本与 DEPENDS：确认是不是
  21.02 时代的版本、依赖里有没有 fw4/nft 专属项。
- `Build packages only` 步的 `V=s` 详细日志：定位到第一个
  报错的包，不要只看最后的退出码。
