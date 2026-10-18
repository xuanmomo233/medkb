# 心电复习卡图标

用户确认的图标：暖白主卡、薄荷绿后卡、心电波形、海青背景。

- `master.png`：已确认的完整图标，内置 image_gen 生成。
- `cards-transparent.png`：内置 image_gen 仅去除背景，供 Android 自适应图标使用；保留心电波形颜色。
- `prompts.txt`：完整生成和背景提取提示词。

执行 `python tools/export_pulse_icons.py` 导出网页 PNG/ICO、Flutter 资源以及 Android 各密度图标。
脚本只做尺寸、格式及平台安全区适配，不重绘设计。Android 前景不透明主体位于 30.5dp 半径内；网页 maskable 主体位于 38% 半径内。

网页侧栏和登录页共用 `/brand-pulse-192.png`；Android 8 以上使用分层自适应图标，旧版使用各密度 PNG；Android 13 主题图标使用独立的单色卡片与心电波形矢量。
