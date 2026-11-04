# 图标与包名映射

## 命名规则

主题里的图标资源名 = 包名转小写，`.` 换成 `_`：

| 应用 | 包名 | 资源名 |
|---|---|---|
| 微信 | `com.tencent.mm` | `com_tencent_mm` |
| 淘宝 | `com.taobao.taobao` | `com_taobao_taobao` |
| MT 管理器 Canary | `bin.mt.plus.canary` | `bin_mt_plus_canary` |
| Shizuku | `moe.shizuku.privileged.api` | `moe_shizuku_privileged_api` |

资源必须放在 `res/mipmap-xhdpi/`（或 `mipmap-nodpi/`，已有资源保持原目录），
文件名 `<资源名>.png`。

## 查包名

```bash
adb shell pm list packages | grep -i 关键词
adb shell pm list packages -3           # 只看第三方应用
adb shell pm path com.example.app       # 看 APK 路径
```

拿到 APK 后可以用 `aapt2 dump badging app.apk | grep application-label` 确认
应用名与启动 Activity。注意同一应用可能有多个渠道包/变体（例如
`bin.mt.plus` 和 `bin.mt.plus.canary`），包名必须与设备上安装的完全一致。

## appfilter.xml

ADW / Nova 图标包通常在 `assets/appfilter.xml` 或 `res/xml/appfilter.xml`：

```xml
<item component="ComponentInfo{com.tencent.mm/com.tencent.mm.ui.LauncherUI}"
      drawable="weixin.icon" />
```

`apply_icons.py` 只取 `ComponentInfo{...}` 里的包名和 `drawable` 属性；
同一个包出现多次时默认取第一条。图标文件名是 `<drawable>.png`。

## CSV 映射

适合自己补图标或覆盖图标包：

```csv
# package,drawable
com.tencent.mm,weixin.icon
bin.mt.plus.canary,mtguanliqi.icon
```

CSV 的优先级高于 appfilter；`#` 开头的行会被忽略。

## 一个包多个图标

桌面主题数组只支持**包级**映射，不支持 `package/activity` 级。如果某个包有
多个入口且需要不同图标（电话/联系人、设置各子页、相机/摄像机等），不要把它
加进主题数组；启动器自带组件级映射会处理。`data/launcher_builtin_packages.txt`
列出了这些包，脚本会自动跳过。

如果某个第三方包有多个 Activity 且图标包给了不同 drawable，脚本会取第一条并
打印提示。此时只能二选一，或者换用组件级方案（需要改桌面，不在本工具范围）。

## 自制图标

1. 准备正方形 PNG（白底或透明底都可以）。
2. 套用主题圆角边框模板：

   ```bash
   py scripts/process_icon.py \
     --input art.png --output icons/myicon.png \
     --template iconback1.png --inner 120
   ```

   - 白底图：`alpha = 255 - min(R, G, B)`，白底变透明，黑色线稿保留；
   - 透明底图：直接使用原 alpha；
   - 自动裁切到内容边界，等比缩放到 `--inner` 像素内并居中；
   - 输出 156×156。

3. 在 CSV 里登记包名与 drawable 名，再运行 `apply_icons.py`。

## 检查清单

- [ ] 包名与设备上 `pm list packages` 完全一致（大小写、后缀）
- [ ] 资源名只含 `[a-z0-9_]`
- [ ] 图标是 PNG，建议 156×156
- [ ] 包名已加入 `predefined_app_pkg_list`
- [ ] 没有误加组件级映射的系统包
- [ ] 装完后在主题 App 里重新应用了一次主题
