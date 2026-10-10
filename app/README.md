# 医学知识库 APP

Flutter 客户端，连接云端 `https://luck.021209.xyz`（PostgreSQL + Flask）。

## 本地构建

```
flutter pub get
flutter build apk --release
# 产物: build/app/outputs/flutter-apk/app-release.apk
```

## CI 构建与发版

push 到 main 后 GitHub Actions 自动构建并发布 Release（`build-<run_number>` tag，asset `app-release.apk`）。

**每次更新必须同步版本号**（约定）：

1. **发版前先升 pubspec `version:`**（语义化 `1.x.y`，决定 APK 的 versionName/显示版本）
2. push → CI 构建 → Release `build-<run_number>`
   - `versionCode` = run_number（CI 自动注入，单调递增保证可覆盖安装）
   - `versionName` = pubspec 语义版本（用户所见版本）
   - `appBuild` = run_number（APP 内更新检查用，CI 自动注入）
3. 下载新 APK → `/opt/medkb/app-release.apk`
4. `echo '<run_number>|v<语义版本> <变更说明>' > /opt/medkb/VERSION`
5. `curl http://127.0.0.1:8899/api/version` 验证

## 功能

- 目录浏览（导图/知识点/题库章节，关键词过滤）
- 全局搜索（题目/考点/章节）
- 刷题（学科×系统×题型×来源筛选，单选/多选判分，错题自动收录）
- 背卡（学科分组翻面卡）
- 今日（到期复习/错题本/收藏夹 + 学习统计）
- 间隔重复 SM-2 简化算法，进度云端同步
