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

学习计划使用持久化任务清单，同一题号关联多个章节也只生成一个任务；普通作答或交卷会同步完成任务。调整计划和重新排期沿用历史作答，未完成任务顺延，截止日期不代表全部完成。网页和 App 的计划入口均只加载待完成任务。

普通刷题和日程练习进入时隐藏历史答案，可使用“本次重练”清除当前会话作答，永久记录保留。今日日程在有效作答或背卡学习后自动完成；日程内可前后切换题目与背卡。日程每日生成一次，完成后的复习题更新下次复习时间。

`question_merges` 和 `question_relations` 预留人工确认的重复题映射与同类题关系。当前迁移只建立空表，不自动比较、合并或分类现有题目；解析下方的同类题推荐只读取已明确维护的关系，没有关系时显示空状态。跨题号的内容重复将在允许分类后处理。
