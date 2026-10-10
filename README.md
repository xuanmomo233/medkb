# MedKB 医学知识库

西综考研题库 + 医学思维导图知识库全家桶。

```
medkb/
├── app/      Flutter 安卓 APP（刷题 / 背卡 / 知识点 / 今日复习）
├── server/   Flask 后端（PostgreSQL）+ 上游题库同步管线
└── kb/       医学知识库 Markdown 源文件（导图 + 题库抽取）
```

## app/ — 手机 APP

Flutter 应用，源码说明见 [app/README.md](app/README.md)。

- CI：push main 自动构建 release APK 并发布为 `build-N` release（`.github/workflows/build-apk.yml`）
- 版本：`app/pubspec.yaml` 语义版本 + `run_number` 作 versionCode；固定 `medkb.jks` 签名，可覆盖升级
- 下载地址：https://luck.021209.xyz/app.apk

## server/ — 后端

部署在 VPS `/opt/medkb/`（Flask + PostgreSQL `medkb` 库）。

| 文件 | 用途 |
|---|---|
| `server_cloud.py` | 生产后端：/api/quiz、/api/q_full、/api/facets、/api/mark、知识点/导图页图接口 |
| `server_local.py` | 本地 SQLite 版开发后端（kb.db） |
| `build_db.py` | 由题库 md/JSON 建库 |
| `wcyk_sync.py` + `wcyk_api.py` | 万川题库增量同步（AES 加密 token、按 qid 扫描），cron 每周日 03:00 |
| `reclassify_system.py` | 题目按导图章节三级重分类（学科·章·节） |
| `app.html` | 网页版前端（单文件） |

部署要点：systemd 服务 `medkb.service`；APK 部署为 `/opt/medkb/app-release.apk` + `VERSION` 文件。

> ⚠️ server_cloud.py 内含数据库口令与邀请码——**本仓库必须保持 private**。

## kb/ — 知识库

- `生理学/ 生物化学/ 病理学/ 内科学/ 外科学/ 知识点/` —— 思维导图 Markdown（含 `pdf页` 标注、`page_NNN` 锚点）
- `题库/` —— 题库按来源/章节抽取的 Markdown + INDEX
- `INDEX.md` / `SYSTEM_INDEX.md` —— 总目录
