# Hisense A9「儒雅」主题图标适配工具

把 ADW / Nova 格式的图标包（`appfilter.xml` + PNG）批量注入海信 A9 的
Vision 主题 APK（`com.hmct.theme.*`），让桌面适配更多第三方应用图标。

> **仓库源码只包含脚本、文档和少量预览图。**
> 不包含海信主题 APK、厂商资源、图标包素材、签名密钥或任何用户数据。
> 改版 APK 作为 Release 附件提供，仅限个人设备使用（见下方「发布版」）。

## 原理

海信 A9 的桌面是 `com.hmct.vision`（`/system/priv-app/Vision_Launcher`），
主题包是纯资源 APK。桌面解析第三方图标时逻辑等价于：

```text
if theme.predefined_app_pkg_list 包含 <package>:
    name     = <package>.lower().replace('.', '_')
    drawable = theme_resources.getIdentifier(name, "mipmap", <theme package>)
```

所以一个适配图标需要两样东西：

1. `res/mipmap-xhdpi/<包名小写_下划线>.png`
2. 包名出现在 `res/values/arrays.xml` 的 `predefined_app_pkg_list` 里

详细逆向分析见 [docs/theme-internals.md](docs/theme-internals.md)。

## 发布版

- Release 页面：<https://github.com/BlueEve04/Hisense-A9-BetterTheme/releases/latest>
- 附件 APK：`Hisense-A9-BetterTheme-7.01.001-mod5.apk`
- 包名：`com.hmct.theme.elegant.mod`，主题列表显示为「儒雅·增强」
- 安装后到主题 App 里选择「儒雅·增强」；如果之前装过旧版改版主题，先卸载再装
- **APK 内含海信主题原始资源和图标包素材，仅供个人设备本地使用，不在 MIT 许可范围内，请勿再分发**

## 快速开始

### 1. 准备

- Python 3 + Pillow（`py -m pip install pillow`）
- apktool 2.10+
- Android SDK build-tools（`zipalign`、`apksigner`）
- 你自己的签名密钥

### 2. 反编译主题

```bash
java -jar apktool.jar d theme.apk -o theme
```

### 3. 注入图标

```bash
py scripts/apply_icons.py \
  --theme-dir theme \
  --icons-dir icons \
  --appfilter appfilter.xml \
  --package-name com.example.theme.mod \
  --theme-name-zh "我的主题" \
  --theme-name-en "My Theme" \
  --version-code 2 --version-name 1.0.1
```

- `--icons-dir` 里放 `<drawable>.png`，文件名与 appfilter 的 `drawable` 对应。
- 也可以不用 appfilter，改用 CSV：`--mapping extra.csv`（格式见
  [examples/mapping.example.csv](examples/mapping.example.csv)）。

### 4. 打包 + 签名

密码只从环境变量读取，避免出现在命令历史和进程列表里：

```bash
export KS_PASS='***'
export KEY_PASS='***'

py scripts/build_apk.py \
  --theme-dir theme \
  --apktool apktool.jar \
  --build-tools "$ANDROID_HOME/build-tools/36.0.0" \
  --keystore my.jks --ks-alias mykey \
  --out theme-signed.apk
```

不传 `--keystore` 时只产出对齐后的未签名 APK。

### 5. 安装并切换

```bash
adb install -r theme-signed.apk
```

然后在主题 App 里选中新主题。如果改的是**已安装的系统主题包**，换签名后无法
覆盖安装；推荐改包名做成独立主题，或用 Magisk 覆盖系统 APK。

## 自制图标

```bash
py scripts/process_icon.py \
  --input art.png --output icons/myicon.png \
  --template iconback1.png --inner 120
```

白底图会自动转成透明，透明底图直接使用 alpha；裁切后居中套到圆角模板上。
详见 [docs/icon-mapping.md](docs/icon-mapping.md)。

## 目录结构

```text
scripts/
  apply_icons.py     # appfilter/CSV -> 资源 + 数组 + 清单/版本
  process_icon.py    # 白底/透明底 -> 主题风格 156x156 图标
  build_apk.py       # apktool b + zipalign + apksigner
data/
  launcher_builtin_packages.txt   # 启动器组件级映射的包名（需排除）
docs/
  theme-internals.md # 逆向笔记：图标解析、主题切换、缓存坑
  icon-mapping.md    # 包名/图标命名/映射格式
  build-guide.md     # 完整构建与排错
examples/
  mapping.example.csv
previews/
  custom-icons-1.png, custom-icons-2.png
```

## 重要注意事项

- **不要**把 `data/launcher_builtin_packages.txt` 里的包名直接加进主题数组：
  启动器对它们使用组件级映射（例如电话和联系人共用
  `com.android.contacts`），按包名匹配会把多个图标串成一个。脚本会自动排除
  「内置但不在原主题数组中」的包。
- 桌面 `favorites.icon` 里的 BLOB 不一定会随主题切换回写；判断是否生效以
  屏幕/应用抽屉显示为准。
- 只改 `Settings.Secure pref_key_theme_package` 并重启桌面**不会**重建图标，
  必须走主题 App 的切换流程（或等价广播）。
- 图标建议 156×156 PNG；主题现有资源以 `mipmap-xhdpi` 为主。
- 改包名后资源包名会跟着变，`createPackageContext` 才能按新包名找到资源。

## 免责声明

本项目与海信（Hisense）无关，仅供个人学习和对自己有权使用的主题进行
本地化定制。请勿用本工具分发厂商主题 APK、图标包素材或任何受版权/商标
保护的内容。`previews/` 中的图标和 Release 附件 APK 仅作适配效果示例，版权归各自权利人所有；Release 附件不在 MIT 许可范围内。

## License

脚本与文档采用 MIT License，见 [LICENSE](LICENSE)。
