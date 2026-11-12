# 仙剑奇侠传 iOS 版（SDLPAL）编译方案

用 SDLPAL 开源引擎把 `xjqxrqb` 里的原版游戏数据变成 iOS 原生 App。
不是模拟器，是原生 ARM 代码，支持 MIDI 音乐和高分辨率。

---

## 数据校验结果（2026-11-12）

`xjqxrqb` 目录：**完整可用的仙剑98柔情版数据**

```
15 个 MKF 全部结构合法（偏移表、chunk 边界、末尾偏移 == 文件大小）
sss.mkf   5 块      map.mkf  226 块    gop.mkf   226 块
mgo.mkf 637 块      sounds.mkf 505 块  rng.mkf    12 块
mus.mkf  88 块      data.mkf   15 块    fbp.mkf    78 块
abc.mkf 154 块      ball.mkf  252 块    fire.mkf   55 块
rgm.mkf  92 块      pat.mkf     9 块    f.mkf      19 块

无 YJ_1 压缩块 → 未压缩数据（SDLPAL 会按 DOS 版数据读取，可正常运行）
6 个 AVI 过场动画全部 RIFF/AVI 合法
M.msg 为 BIG5 编码文本（正常）
```

MKF 格式（来自 `sdlpal/palcommon.c`）：

```
dword[0] = 偏移表大小（也等于 chunk0 起始偏移）
count    = (dword[0] - 4) / 4
chunk i  = [dword[i], dword[i+1])
```

---

## 编译方式：GitHub Actions（不需要 Mac）

### 1. 建仓库

在 GitHub 新建一个空仓库（公开仓库的 macOS runner 免费），例如 `pal-ios`。

### 2. 上传这个 workflow

把本目录下的 `.github/workflows/build.yml` 按原路径上传到仓库：

```
你的仓库/
└── .github/
    └── workflows/
        └── build.yml
```

### 3. 运行

- 打开仓库 → **Actions** 标签 → 左侧 **Build SDLPAL iOS** → **Run workflow**；
- 约 5～15 分钟；
- 成功后在该次运行的页面底部 **Artifacts** 下载 `SDLPAL-ipa`。

### 4. 安装到 iPhone

```
1. 解压得到 SDLPAL.ipa
2. LiveContainer → 「+」→ 导入 SDLPAL.ipa → 安装
   （或 SideStore → My Apps → 「+」）
3. 打开 App 一次（会提示缺少游戏数据），然后退出
```

### 5. 放入游戏数据

App 的 Info.plist 已开启 `UIFileSharingEnabled`，所以：

```
「文件」App → 我的 iPhone → SDLPAL
→ 把 xjqxrqb 里的文件全部拷进去（约 240 MB，含 AVI）
```

必需文件：

```
SSS.MKF  M.MSG  MAP.MKF  GOP.MKF  RNG.MKF  F.MKF  FBP.MKF
ABC.MKF  BALL.MKF  DATA.MKF  FIRE.MKF  MGO.MKF  PAT.MKF
MUS.MKF  SOUNDS.MKF  0.RPG  WORD.DAT
可选：1～6.AVI（过场动画）
```

### 6. 玩

再次打开 App → 直接进游戏。

---

## 已知可能需要调整的点

| 问题 | 处理 |
|---|---|
| `IPHONEOS_DEPLOYMENT_TARGET=6.1` 报错 | workflow 里已覆盖为 15.0 |
| CocoaPods 装不上（老 podspec） | 把 `pod install` 的输出贴出来，改 Podfile 或跳过该 pod |
| SDL 子模块没拉下来 | `submodules: recursive` 已加 |
| 构建成功但启动闪退 | 大概率是 armv7 残留或签名问题，看 build.log |

---

## 文件位置

```
test/pal-ios/.github/workflows/build.yml   ← 要上传到 GitHub 的文件
test/xjqxrqb/                              ← 游戏数据（240 MB）
test/_sdlpal/sdlpal-master/                ← 已下载的 SDLPAL 源码（本地参考）
test/_palcheck.py                          ← 数据校验脚本
```
