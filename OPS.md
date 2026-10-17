# MedKB 运维手册

部署路径、容器挂载和健康接口于 2026-10-16 实机核对。以下远端命令使用 Linux shell，本机命令使用 PowerShell 7。

## 运行结构

浏览器 / App → `https://luck.021209.xyz` → 反向代理 → `127.0.0.1:8899` → Docker `medkb-api:8000` → PostgreSQL `medkb_v2`。

| 位置 | 用途 |
|---|---|
| `/opt/medkb-v2/src/` | 生产构建源码；当前不是 Git checkout，不能在这里直接 `git pull` |
| `/opt/medkb-v2/src/deploy/docker-compose.yml` | 当前运行的 Compose 配置 |
| `/opt/medkb-v2/src/deploy/.env` | 生产环境变量，仅保存在服务器 |
| `/opt/medkb/img` → `/data/img` | 导图图片，只读挂载 |
| `/opt/medkb/app-release.apk` → `/data/app-release.apk` | 当前安装包，只读挂载 |
| `/opt/medkb/uimg` → `/data/uimg` | 用户上传，可写 |
| `/opt/medkb/imgcache` → `/data/imgcache` | 按需生成的图片缓存，可写 |
| 镜像内 `/app/web` | 网页构建产物，由 FastAPI 提供 |

旧 Flask 服务、systemd `medkb.service`、`VERSION` 文件和 `kb.db` 已不属于当前部署。不要用旧栈命令管理服务。

## 连接与检查

本机使用已配置的 SSH 别名，不在文档记录私钥或数据库口令：

```powershell
ssh axs-vps
```

登录服务器后执行：

```sh
docker compose --project-directory /opt/medkb-v2/src/deploy ps
docker compose --project-directory /opt/medkb-v2/src/deploy logs --tail 100 api
curl --fail --silent --show-error http://127.0.0.1:8899/api/health
```

`/api/health` 会执行数据库查询；正常返回 `{"status":"ok"}`，数据库异常返回 503。仅首页返回 200 不能证明数据库可用。

## 服务端与网页发布

1. 在本地完成 README 中的三端检查，并检查待发布差异。
2. 将确认的源码同步至 `/opt/medkb-v2/src/`。当前通过文件同步发布，不依赖远端 Git。上传时排除 `.env`、签名文件、依赖缓存、测试缓存和本地构建产物；保留服务器的 `deploy/.env`。
3. 构建新镜像，先运行数据库迁移，再启动服务：

```sh
docker compose --project-directory /opt/medkb-v2/src/deploy build api
docker compose --project-directory /opt/medkb-v2/src/deploy run --rm api alembic upgrade head
docker compose --project-directory /opt/medkb-v2/src/deploy up -d api
docker compose --project-directory /opt/medkb-v2/src/deploy logs --tail 100 api
curl --fail --silent --show-error http://127.0.0.1:8899/api/health
curl --fail --silent --show-error https://luck.021209.xyz/api/health
docker compose --project-directory /opt/medkb-v2/src/deploy exec api python scripts/verify_content_publication.py
```

前端已编译进镜像，修改 React 源码后需要重建。首次配置上传目录时，把 `/opt/medkb/uimg` 和 `/opt/medkb/imgcache` 的属主设为容器用户 UID/GID `10001:10001`。

环境变量由 Compose 的 `.env` 注入。常用配置为 `MEDKB_DATABASE_URL`、`MEDKB_INVITE_CODE`、`MEDKB_GLM_API_KEY`、`MEDKB_VERSION`。变更环境变量后运行 `docker compose ... up -d api` 使容器重新创建，单纯 `restart` 不会重新读取配置。

生产默认不开放 API 文档。临时排查可设置 `MEDKB_EXPOSE_DOCS=1` 并重新创建容器，用完后关闭。

## Android 发布

1. 修改 `app/pubspec.yaml` 的语义版本。main 推送后，发布工作流先运行三端检查，再生成 GitHub Release `build-N`。`N` 是发布工作流的 `run_number`。
2. 下载该 Release 的签名 APK，上传至 `/opt/medkb/app-release.apk`。不要上传 debug 包。
3. 在服务器 `deploy/.env` 中修改 `MEDKB_VERSION='N|v语义版本 更新说明'`，构建号必须与 APK 一致且大于已发布版本。
4. APK 是单文件 bind mount；上传若替换了文件 inode，运行中的容器可能仍引用旧文件。因此替换 APK 后重新创建容器：

```sh
docker compose --project-directory /opt/medkb-v2/src/deploy up -d --force-recreate api
curl --fail --silent --show-error http://127.0.0.1:8899/api/version
sha256sum /opt/medkb/app-release.apk
curl --fail --silent --show-error --head https://luck.021209.xyz/app.apk
```

确认 `/api/version` 的 `build`、`note` 与本次发布一致，`apk_sha256` 与落盘文件 SHA256 一致，并在已安装旧版本的设备上验证覆盖升级。完整构建说明见 [app/README.md](app/README.md)。

## 数据与内容发布

- 应用数据保存在 PostgreSQL `medkb_v2`，部署镜像不应重建或覆盖生产数据。
- `backend/scripts/init_db.py` 仅用于空库初始化。已有数据库使用 Alembic；`20261016_01` 增加教材书目和内容出处表，`20261016_02` 将本地可核验的人卫第十版教材目录扩展到 13 本。
- 旧格式题库同步仍使用 `PG_DSN`。`wcyk_sync.py` 写入旧格式字段，不能仅将 DSN 改成新库就用于 v2；导入新库前需转换、去重和验证。
- 保留现有同步任务使用的 `.pgenv`、`sync_state.json`、题库原始数据和同步脚本。不要在排障输出中打印 `.pgenv` 或 `.env`。
- 数据库是网页、App 与 AI 的运行时唯一内容源。章节、题目或卡片保存后，AI 后续检索立即读取当前数据库内容，不需要同步 Markdown 或重建文件索引。
- `20261017_01` 增加固定计划任务、任务章节关联和空的题目关系表。上线前先执行 `alembic upgrade head`；旧计划首次访问时会建立任务快照并沿用历史作答。迁移不填充重复题或同类题关系，也不删除题目或作答记录。
- `20261017_02` 增加每日日程快照，防止空日程重复生成。日程完成由作答及背卡学习同步；既有当日日程保留，并核对当天实际作答状态。
- 医学内容按人民卫生出版社第十版相应教材核验。题库旧答案、导图和教材出现冲突时，保留来源区别并明确差异，不能把导图或旧题答案当作教材结论。

2026-10-15 按要求清理了旧备份和临时回滚材料。本轮未新增备份策略，不能假定历史编辑批次仍可回滚。

## 常见排查

| 现象 | 检查位置 |
|---|---|
| 网页白屏 | 浏览器控制台、网络请求、镜像内 `/app/web` 的构建产物 |
| API 500 / 健康接口 503 | `docker compose ... logs --tail 100 api`、数据库连接与网络 |
| API 401 | 登录是否过期，客户端是否携带 `X-Token` 或 Bearer token |
| App 不提示更新 | `/api/version` 构建号、容器实际环境变量、APK 与接口 SHA256 |
| 上传失败 | `uimg` / `imgcache` 挂载、空间和 UID 10001 的写权限 |
| AI 引用旧内容 | 确认修改的是当前数据库记录；检查出处状态和容器是否运行新镜像 |

其他项目共享此 VPS。操作限于上述路径、容器及本项目配置。
