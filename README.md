# MedKB 医学知识库

西医综合备考工具，提供题库练习、模考、间隔复习卡片、知识点与导图、学习计划、笔记及 AI 陪学。医学内容以人民卫生出版社第十版相应教材为主要依据，出处未核实的内容不能标为已核验。

## 当前架构

| 目录 | 用途 |
|---|---|
| `backend/` | FastAPI + SQLAlchemy 异步后端，生产使用 PostgreSQL |
| `web/` | React + TypeScript 网页端，构建后由后端提供 |
| `app/` | Flutter Android 客户端 |
| `kb/` | Markdown 原始资料与校对材料，不作为线上 AI 的运行时内容源 |
| `server/` | 上游题库同步和旧格式导入辅助工具，不是生产 Web 服务 |
| `deploy/` | Docker 镜像及 Compose 配置 |
| `docs/editorial-current/` | 2026-10-15 内容清理结果 |

生产服务是 Docker 容器 `medkb-api`。网页、App 和 AI 陪学均读取 PostgreSQL 中的当前章节、题目、背卡和教材出处；管理员保存后立即成为三端共同使用的内容。Markdown 仅用于导入、比对和人工校对。

## 本地检查

分别在对应目录执行；Python 使用 3.12 或更高版本，Node.js 使用 22，Flutter 使用 stable（与 CI 一致）。

后端（`backend/`，建议使用虚拟环境）：

```powershell
python -m pip install '.[dev]'
python -m pytest -q -p no:cacheprovider
```

测试使用隔离的内存 SQLite，不需要生产数据库凭据。生产 PostgreSQL 的行为仍需单独进行集成验证。

网页（`web/`）：

```powershell
npm ci
npm run lint
npm test
npm run build
```

App（`app/`）：

```powershell
flutter pub get
flutter analyze --no-fatal-infos
flutter test
```

## 自动检查与发布

- `.github/workflows/quality.yml`：PR、非 main 分支推送和手动运行时检查三端，也供发布流程复用。Flutter 错误和警告阻断流程，提示级建议不阻断。
- `.github/workflows/build-apk.yml`：main 推送或手动运行时先检查三端，全部成功后构建并发布签名 APK。构建号继续使用该发布工作流的 `run_number`。
- CI 发布 GitHub Release，不会自动部署到 VPS。
- 密钥和生产 `.env` 不入库，签名配置通过 GitHub Secrets 或本地忽略文件提供。

部署步骤见 [运维手册](OPS.md)，网页开发见 [web/README.md](web/README.md)，App 构建见 [app/README.md](app/README.md)。下载地址：[Android 安装包](https://luck.021209.xyz/app.apk)。

## 内容维护

教材出处记录书名、出版社、版次、教材章节、小节、页码和核验状态。只有人工选择“已核验”的出处才会显示为已按教材核验；系统不会从旧文件名或导图页码猜测教材页码。维护规则见 [kb/README.md](kb/README.md)，现有清理结果见 [当前内容说明](docs/editorial-current/README.md)。
