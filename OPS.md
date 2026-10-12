# MedKB 运维手册（VPS 使用方法 + 项目工作流程）

> 本文件描述线上环境的结构、常用运维命令、发版流程。**仓库必须保持 private**（含数据库凭据、邀请码；文档中不重复记录密钥，需要时用 `systemctl cat medkb.service` 查看）。

## 1. 架构总览

```
用户浏览器/App
    │
    ▼  https://luck.021209.xyz  (Cloudflare → 1Panel + OpenResty)
    │  站点配置: /opt/1panel/www/conf.d/medkb.conf
    │  80→301 https; 443 反代 → 127.0.0.1:8899
    ▼
medkb-api (docker compose, deploy/Dockerfile, uvicorn :8000)
    ├── /              → /app/web/dist（React SPA，服务端 sanitize 后的 HTML）
    ├── /app.apk       → /data/app-release.apk （App 更新下载，/api/version 带 sha256）
    ├── /api/version   → MEDKB_VERSION 环境变量（"build|更新说明"）
    ├── /api/*         → FastAPI（X-Token / Bearer，Argon2 + token 哈希）
    ├── /img/<name>    → /opt/medkb/img/*.webp（导图页图，只读挂载）
    └── 数据层
        ├── PostgreSQL  dbname=medkb_v2（MEDKB_DATABASE_URL，见 deploy/.env）
        └── /opt/medkb/kb.db（236MB SQLite 备份/本地开发用，勿删）
```

> **2026-10 安全整改**：旧栈 `server_cloud.py`（Flask）已从仓库删除，systemd `medkb.service` 废弃。
> `server/` 下数据脚本（`wcyk_sync.py` 等）的 DB 连接改为环境变量 `PG_DSN`，**VPS 上的 cron
> 调用前需 `export PG_DSN='dbname=medkb user=... password=... host=127.0.0.1'`**（口令写进 cron
> 环境/root-only 的 env 文件，勿再入库）。

本机还有另一个项目（ArcartX 云平台，nginx `conf.d/default.conf` → :5173），与本项目无关，勿动。

## 2. SSH 登录

```powershell
ssh axs-vps        # 别名已配好：103.231.58.64:352, root, D:\Desktop\axs.pem
```

- **注意**：`luck.021209.xyz` 的 22 端口不通，必须走别名（352 端口）。
- 传文件：`scp 本地文件 axs-vps:/opt/medkb/`

## 3. 服务管理（新栈 docker）

```bash
cd /opt/medkb-v2/deploy        # 或你放置 deploy/ 的目录
docker compose up -d --build   # 改代码后重建
docker compose logs -f api     # 实时日志
docker compose restart api
```

- 静态资源（apk、img、kb）走 bind mount，落盘即生效不用重启。
- 环境变量在 `deploy/.env`（MEDKB_DATABASE_URL / MEDKB_GLM_API_KEY / MEDKB_INVITE_CODE / MEDKB_VERSION / MEDKB_EXPOSE_DOCS），改后 `docker compose up -d`。
- ~~旧栈 `medkb.service`(systemd + Flask) 已废弃，保持 disabled~~。

## 4. 线上文件布局 `/opt/medkb/`

| 文件/目录 | 作用 |
|---|---|
| `server_cloud.py` | ~~生产服务端（Flask）~~ 已删除下线，勿恢复 |
| `server.py` | 本地开发服务端（SQLite） |
| `app.html` | 旧网页端（已下线，仅存档参考） |
| `app-release.apk` | App 安装包，通过 /app.apk 下载 |
| `VERSION` | `构建号\|更新说明`，App 启动时轮询 /api/version 提示更新 |
| `kb.db` | SQLite 数据库（备份；生产用 PostgreSQL） |
| `img/page_*.webp` | 导图页图（文件名=印刷页码） |
| `uimg/` | 用户上传图片 |
| `kb/` | 知识库静态资源 |
| 其余 `*.py` | 历史数据清洗/迁移脚本（一次性工具，可不管） |

## 5. 发版流程

### 5.1 服务端 / 网页端（新栈）

```powershell
git push 后到 VPS 拉代码重建：
ssh axs-vps "cd /opt/medkb-v2 && git pull && cd deploy && docker compose up -d --build"
# 首次非 root 部署前执行一次（上传目录属主交给容器内 uid 10001）：
ssh axs-vps "chown -R 10001:10001 /opt/medkb/uimg /opt/medkb/imgcache"
```

### 5.2 App（Flutter，走 CI 构建）

1. 改 `app/` 代码 → 推送到 GitHub → `build-apk.yml` 自动构建
   - 签名密钥从 Secrets 注入（`MEDKB_KEYSTORE_B64`/`MEDKB_KEY_ALIAS`/`MEDKB_KEY_PASSWORD`/`MEDKB_STORE_PASSWORD`）
   - 本地手动构建：`app/android/app/key.properties`（gitignored，勿入库）
2. CI 绿后下载产物：
   ```powershell
   gh run download <run_id> -n app-release -D D:\IDEA\project\.devin-tmp\apk
   ```
3. 上传 + 更新版本号：
   ```powershell
   scp app-release.apk axs-vps:/opt/medkb/app-release.apk
   ssh axs-vps "echo '97|更新说明' > /opt/medkb/VERSION"
   ```
4. 验证：
   ```powershell
   curl.exe -s https://luck.021209.xyz/api/version   # build 应为新号
   curl.exe -sI https://luck.021209.xyz/app.apk       # 200 + apk content-type
   ```

### 5.3 数据库

- 生产新栈：PostgreSQL `medkb_v2`（docker `panel` 网络内的 postgresql 容器），凭据在 `deploy/.env`。
- 旧库 `medkb` 仍被 `wcyk_sync.py` 每周增量写入；DSN 走 `PG_DSN` 环境变量。
- 旧库 `medkb`（本机 127.0.0.1）。连库：`ssh axs-vps` 后用 `psql`，DSN 见 cron/root 环境配置。

### 5.4 新栈部署注意

- 容器内 uvicorn 以非 root 用户 `medkb`(uid 10001) 运行。**升级部署前在 VPS 执行一次**：
  `ssh axs-vps "chown -R 10001:10001 /opt/medkb/uimg /opt/medkb/imgcache"`
  （`/data/kb`、`/data/img`、apk 为只读挂载，无需改属主）
- 生产默认关闭 `/docs`、`/openapi.json`；排障时在 `deploy/.env` 加 `MEDKB_EXPOSE_DOCS=1` 再重启。
- `kb.db` 是 SQLite 镜像，本地 `server.py` 开发用；数据修正脚本历史上直接改库，**改前先备份**：`cp kb.db kb.db.bak` 或 `pg_dump`。

## 6. Git / CI

- 远端：`github.com/xuanmomo233/medkb`（**private，保持私有**）
- 本机 git 直连经常 TLS 断 → 备用方案：`gh api repos/xuanmomo233/medkb/contents/<path>` PUT 单文件提交（先 GET 拿 sha）
- CI：`.github/workflows/build-apk.yml` — push 到 main 自动构建 APK
- 历史：`ff9d7b7` 是清史重建后的初始提交（旧签名密钥已移除）；**密钥本身未换**，若未来用户量变大建议走 Play App Signing 换钥。

## 7. 常见排查

| 现象 | 查法 |
|---|---|
| 网页白屏 | 浏览器 F12 console；Edge 无头验证：`msedge --headless=new --dump-dom <url>` |
| API 全 401 | token 过期→正常；检查 X-Token 头 |
| 改 app.html 没生效 | 用户端强刷 Ctrl+F5（服务端无缓存头时浏览器可能缓存） |
| API 500 | `journalctl -u medkb -f` 看 Python traceback |
| App 不提示更新 | /api/version 的 build 号是否递增；App 内"检查更新" |

## 8. 内容维护工作流（题库/导图/背卡）

数据流：**源文件（`知识点/*.md`）→ 清洗脚本 → SQLite/PG → API → 前端**

- 导图页图：`img/page_N.webp` 文件名=印刷页码（修过 +1 偏移）
- 章节/导图结构：库内 `chapters` 表（kind='mm' 导图）
- 分类原则：按**实际考点**归章，不按题干病名；导图为准，10版教材次之，旧题库答案存疑展示分歧
- 卡片 part 曾按生成批次错贴标签，已人工重排（内科/外科/生化/生理/病理/诊断全部守恒校验过）
- 一次性修数据脚本放 `/opt/medkb/*.py` 和 `D:\IDEA\project\.devin-tmp\`
