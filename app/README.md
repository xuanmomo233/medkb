# 医学知识库 APP

Flutter 客户端，连接云端 `https://luck.021209.xyz`（PostgreSQL + FastAPI）。

## 本地构建

在 `app/` 下使用 Flutter stable，与 CI 保持一致。先执行检查：

```powershell
flutter pub get
flutter analyze --no-fatal-infos
flutter test
```

分析错误和警告会阻断 CI，提示级建议不阻断。现有测试主要覆盖笔记解析与编辑，尚不能代替设备上的登录、离线及覆盖升级验证。

```
flutter pub get
flutter build apk --release
# 产物: build/app/outputs/flutter-apk/app-release.apk
```

## CI 构建与发版

push 到 main 后 GitHub Actions 先执行后端、网页和 Flutter 检查，全部通过后自动构建并发布 Release（`build-<run_number>` tag，asset `app-release.apk`）。CI 不自动上传 VPS。

**每次更新必须同步版本号**（约定）：

1. **发版前先升 pubspec `version:`**（语义化 `1.x.y`，决定 APK 的 versionName/显示版本）
2. push → CI 构建 → Release `build-<run_number>`
   - `versionCode` = run_number（CI 自动注入，单调递增保证可覆盖安装）
   - `versionName` = pubspec 语义版本（用户所见版本）
   - `appBuild` = run_number（APP 内更新检查用，CI 自动注入）
3. 下载新 APK → `/opt/medkb/app-release.apk`
4. 修改 VPS `/opt/medkb-v2/src/deploy/.env` 中的 `MEDKB_VERSION='<run_number>|v<语义版本> <变更说明>'`。
5. 运行 `docker compose --project-directory /opt/medkb-v2/src/deploy up -d --force-recreate api`，重新加载环境变量与 APK 单文件挂载。
6. 验证 `/api/version` 的构建号和 SHA256，以及旧版本设备上的覆盖升级。详细步骤见 [运维手册](../OPS.md)。

## 功能

- 今日：打卡/连续天数、学习计划、到期复习、薄弱点、统计
- 目录与搜索：导图/知识点/题库章节，题目/考点/章节全局搜索
- 刷题：多级筛选（题库组×题库×科目×系统×章节×题型）、练习/背诵/速刷/模考，错题本、模考记录与成绩报告
- 背卡：按学科/部分分组的翻面卡，间隔重复评分（SM-2），收藏与计划
- AI 陪学：对话、出题、判题，支持图片/文件
- 笔记与公开评论（点赞）；管理员可在 APP 内编辑题目解析/标签
- 离线：GET 响应按账号命名空间缓存，仅网络类错误才回退缓存并显示「离线数据」角标
- 技术栈：Flutter + Material 3，API v2（`/api/*`，认证头 `X-Token`），代码结构 `lib/{api,models,endpoints,nav,theme}.dart`、`lib/widgets/`、`lib/pages/`
