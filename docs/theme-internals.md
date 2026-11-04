# 海信 A9 主题/图标机制笔记

测试环境：Hisense A9（HLTE556N），Android 11 / API 30，density 360，
Magisk root。不同固件版本可能有差异，以下结论均已在真机验证。

## 组件与路径

| 组件 | 包名 | 路径 |
|---|---|---|
| 桌面 | `com.hmct.vision` | `/system/priv-app/Vision_Launcher/Vision_Launcher.apk` |
| 主题引擎 | `com.hmct.theme` | `/system/priv-app/Vision_ThemeOnline/Vision_ThemeOnline.apk` |
| 「儒雅」主题 | `com.hmct.theme.elegant` | `/system/priv-app/Vision_ThemeElegant/Vision_ThemeElegant.apk` |

主题包是**纯资源 APK**：`classes.dex` 只有一个显示主题名的 stub Activity，
没有业务代码。图标匹配逻辑全部在桌面和主题引擎里。

## 桌面如何找图标

桌面类 `com.hmct.vision.PredefinedIconList` 维护两份映射：

1. 内置的组件级列表（`res/xml/default_icons*.xml`），按
   `ComponentInfo{package/activity}` 精确匹配，值形如 `ic_predefined_phone`；
2. 主题包里的 `array/predefined_app_pkg_list`，只按**包名**匹配。

解析顺序（等价伪代码）：

```text
for pkg in theme.predefined_app_pkg_list:
    if pkg == component.packageName:
        return pkg.lower().replace('.', '_')     # mipmap 资源名

for item in launcher_builtin_component_list:
    if item.component == component:
        return item.icon_resource_name

return null                                      # 回退到应用原始图标
```

命中后，桌面通过 `createPackageContext(themePkg, CONTEXT_IGNORE_SECURITY)`
拿到主题包的 `Resources`，再 `getIdentifier(name, "mipmap", themePkg)` 取图。
因此：

- 资源**必须**编译进 `resources.arsc`，直接往 zip 里塞 PNG 无效；
- 资源类型必须是 `mipmap`；
- 包名必须出现在主题数组里；
- 资源名是**小写包名 + 下划线**，例如 `com.tencent.mm` →
  `com_tencent_mm`；
- 资源不必是 `public`，运行时按名字查找即可（已在真机验证）。

## 组件级映射的坑

启动器内置列表里有很多「一个包对应多个图标」的情况：

- `com.android.contacts` 同时承载电话、联系人、通话记录；
- `com.android.settings` 有设置、应用管理、WLAN、双卡等多个入口；
- `com.android.camera2`、`com.android.stk` 等也有多个 Activity。

主题数组是**包级**的，把这些包加进去会让同一包下所有入口都使用同一个图标。
`data/launcher_builtin_packages.txt` 收录了启动器组件级列表里的包名；脚本会
自动排除「在该列表中、但原主题数组里本来就没有」的包，保留原主题的组件级行为。

## 主题切换与图标缓存

桌面把工作区条目的图标位图存在 `favorites` 表的 `icon` BLOB 里
（`/data/user_de/0/com.hmct.vision/databases/launcher.db`）。因此：

- 只改 `Settings.Secure pref_key_theme_package` 并杀掉桌面进程，
  已存图标不会重建；
- 正常路径是主题 App 触发桌面的 `clearAndSwitchTheme` 流程：重新加载
  `predefined_app_pkg_list`、清空内存图标缓存、`forceReload()` 工作区；
- 主题引擎发出的等价广播是：

  ```bash
  adb shell am broadcast -a com.hmct.intent.switch_theme \
      --es selectedThemePkg <theme.package>
  ```

  （桌面 `LauncherModel` 接收，extra 名为 `selectedThemePkg`。）

注意 `getAndFrameShortcutIcon` 在**显示时**也会按主题取图，所以 BLOB 没变
不代表屏幕上没变；最终以屏幕/应用抽屉为准。

## 主题枚举与改包名侧载

主题引擎通过：

```text
queryIntentActivities(Intent("hmct.intent.action.THEME_LIST"))
```

枚举所有已安装 APK，不校验签名，也不要求包名以 `com.hmct.theme` 开头。
因此把主题改包名、用任意密钥签名后作为普通用户应用安装，会出现在主题列表里，
无需 root 就能切换。前提是：

- 保留 `hmct.intent.action.THEME_LIST` 的 Activity；
- 资源包名随 manifest 的 `package` 一起改（apktool 构建时会处理）；
- APK 能正常安装（API 30 需要 v2+ 签名）。

如果要用回原包名（`com.hmct.theme.elegant`）替换系统主题，则必须 root +
Magisk 覆盖 `/system/priv-app/...`，并且不同签名可能导致 PackageManager
拒绝或需要清理旧包记录；风险更高。

## 相关 Settings 键

| 键 | 含义 |
|---|---|
| `secure pref_key_theme_package` | 当前主题包名（复杂模式） |
| `secure pref_key_theme_package_simple` | 简易模式下的主题包名 |
| `secure pref_key_default_theme_package` | 默认主题包名 |
| `secure pref_key_set_hitheme_package` | HiTheme 开关；=1 时走在线主题 zip，不走主题 APK |

桌面启动时读取 `pref_key_theme_package`；若为空或对应应用被禁用，会回退到
`pref_key_default_theme_package`。

## 资源规格

- 现有第三方图标多在 `res/mipmap-xhdpi/`，156×156 PNG；
- 系统预置图标在 `res/mipmap-nodpi/`，常见 120×120；
- density 360 的设备会优先选中 xhdpi 资源；
- 建议新图标统一 156×156，保留透明通道；线稿+圆角边框与「儒雅」风格一致。

## 验证方法

不依赖桌面日志，可以写一个 `app_process` 小工具，用
`ActivityThread.systemMain()` 拿系统 Context，然后：

```text
ctx.createPackageContext(themePkg, 2).getResources()
  -> getIdentifier("predefined_app_pkg_list", "array", themePkg)
  -> getIdentifier("<pkg_lower>", "mipmap", themePkg)
```

能取到 ID 和 BitmapDrawable，就说明主题侧配置正确；剩下的问题通常在桌面
缓存/切换流程。
