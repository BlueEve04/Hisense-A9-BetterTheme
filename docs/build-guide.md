# 完整构建与排错

## 依赖

- Python 3.10+，`pip install pillow numpy`
- JDK 8+（apktool / apksigner 都能跑即可）
- apktool 2.10+
- Android SDK build-tools（`zipalign`、`apksigner`）
- 你自己的 JKS/PKCS12 签名密钥

> 不要使用厂商密钥，也不要把他人的主题重新签名后公开分发。

## 反编译

```bash
java -jar apktool.jar d theme.apk -o theme
```

确认输出里有：

```text
theme/AndroidManifest.xml
theme/res/values/arrays.xml
theme/res/mipmap-xhdpi/
theme/apktool.yml
```

## 注入图标

```bash
py scripts/apply_icons.py \
  --theme-dir theme \
  --icons-dir icons \
  --appfilter appfilter.xml \
  --mapping extra.csv \
  --package-name com.example.theme.mod \
  --theme-name-zh "我的主题" \
  --theme-name-en "My Theme" \
  --version-code 2 --version-name 1.0.1 \
  --dry-run
```

先跑 `--dry-run` 看清单，再去掉它实际写入。

会做这些事：

1. 按 `package.lower().replace('.', '_')` 复制/覆盖 `res/mipmap-xhdpi/*.png`；
2. 把新包名追加到 `predefined_app_pkg_list`；
3. 排除启动器组件级映射的包（见 `data/launcher_builtin_packages.txt`，
   只排除原主题数组里本来没有的）；
4. 可选修改 manifest 包名、`theme_name`、`apktool.yml` 版本号。

## 打包签名

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

脚本依次执行：

```text
java -jar apktool.jar b theme -o theme-signed-unsigned.apk
zipalign -f -p 4 ...
apksigner sign --ks ... --ks-pass env:KS_PASS --key-pass env:KEY_PASS ...
apksigner verify --print-certs ...
```

密码只走环境变量，不会出现在命令行里。

## 安装与切换

```bash
adb install -r theme-signed.apk
```

然后在主题 App 里选中新主题。**必须走主题切换流程**，桌面才会重建工作区
图标；只改设置或重启桌面不够。

开发时可以发等价广播（extra 名固定为 `selectedThemePkg`）：

```bash
adb shell am broadcast -a com.hmct.intent.switch_theme \
    --es selectedThemePkg com.example.theme.mod
```

## 常见问题

### 图标不显示

1. 包名是否与 `pm list packages` 完全一致（尤其渠道后缀、大小写）？
2. 资源名是否是 `<小写包名>_<下划线>`？
3. 包名是否在主题的 `predefined_app_pkg_list` 里？
4. 是否重新应用了主题？
5. 该包是否被启动器组件级映射接管？检查
   `data/launcher_builtin_packages.txt`。

### 电话/联系人/设置图标串了

说明把组件级映射的包加进了包级数组。把它从
`predefined_app_pkg_list` 里删掉，或重新跑脚本让它自动排除。

### 装不上

- 与已安装系统主题同包名、不同签名：改包名（`--package-name`）做成独立
  主题，或用 Magisk 覆盖系统 APK。
- Android 11+ 只签了 v1：`apksigner` 默认会带上 v2/v3，确认没有被显式关闭。

### 主题列表里看不到

主题 Activity 必须保留：

```xml
<intent-filter>
  <action android:name="hmct.intent.action.THEME_LIST"/>
  <category android:name="android.intent.category.DEFAULT"/>
</intent-filter>
```

并且 `theme_name` 字符串和 `themepreview` drawable 存在，主题引擎才能显示条目。

### 切换后只有部分图标更新

桌面 `favorites.icon` 的 BLOB 不一定会回写。以屏幕/应用抽屉为准；如果显示
仍旧不对，确认当前主题包名（`settings get secure pref_key_theme_package`）
和实际切换的包一致。

## 回滚

- 独立主题：在主题 App 切回原主题，再 `adb uninstall com.example.theme.mod`。
- Magisk 覆盖：删除模块目录并重启。
