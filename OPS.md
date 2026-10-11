# MedKB 运维手册（VPS 使用方法 + 项目工作流程）

> 本文件描述线上环境的结构、常用运维命令、发版流程。**仓库必须保持 private**（含数据库凭据、邀请码；文档中不重复记录密钥，需要时用 `systemctl cat medkb.service` 查看）。

## 1. 架构总览

```
用户浏览器/App
    │
    ▼  https://luck.021209.xyz  (1Panel + OpenResty, Docker 内)
    │  站点配置: /opt/1panel/www/conf.d/medkb.conf
    │  80→301 https; 443 反代 → 127.0.0.1:8899
    ▼
medkb.service (systemd, python3 /opt/medkb/server_cloud.py, 端口 8899)
    ├── /              → app.html            （网页端单文件应用）
    ├── /app.apk       → app-release.apk     （App 更新下载）
    ├── /api/version   → VERSION 文件        （"build|更新说明"）
    ├── /api/*         → Flask API（Token 认证 X-Token）
    ├── /img/<name>    → /opt/medkb/img/*.webp（导图页图）
    └── 数据层
        ├── PostgreSQL  dbname=medkb（生产主库，PG_DSN 见 service 环境变量）
        └── /opt/medkb/kb.db（236MB SQLite 备份/本地开发用）
```

本机还有另一个项目（ArcartX 云平台，nginx `conf.d/default.conf` → :5173），与本项目无关，勿动。

## 2. SSH 登录

```powershell
ssh axs-vps        # 别名已配好：103.231.58.64:352, root, D:\Desktop\axs.pem
```

- **注意**：`luck.021209.xyz` 的 22 端口不通，必须走别名（352 端口）。
- 传文件：`scp 本地文件 axs-vps:/opt/medkb/`

## 3. 服务管理

```bash
systemctl restart medkb        # 改 server_cloud.py 后必须重启
systemctl status medkb
journalctl -u medkb -f         # 实时日志（含请求日志）
journalctl -u medkb --since '-30min'
```

- `app.html` / `app-release.apk` / `VERSION` 是**静态文件，改完即生效，不用重启**。
- 环境变量（PG_DSN、邀请码 KB_INVITE、端口）在 service 单元里，改后要 `systemctl daemon-reload && systemctl restart medkb`。

## 4. 线上文件布局 `/opt/medkb/`

| 文件/目录 | 作用 |
|---|---|
| `server_cloud.py` | 生产服务端（Flask，单文件） |
| `server.py` | 本地开发服务端（SQLite） |
| `app.html` | 网页端（单文件，全部前端） |
| `app-release.apk` | App 安装包，通过 /app.apk 下载 |
| `VERSION` | `构建号\|更新说明`，App 启动时轮询 /api/version 提示更新 |
| `kb.db` | SQLite 数据库（备份；生产用 PostgreSQL） |
| `img/page_*.webp` | 导图页图（文件名=印刷页码） |
| `uimg/` | 用户上传图片 |
| `kb/` | 知识库静态资源 |
| 其余 `*.py` | 历史数据清洗/迁移脚本（一次性工具，可不管） |

## 5. 发版流程

### 5.1 服务端 / 网页端（即时生效）

```powershell
# 本地改 server/app.html 或 server/server_cloud.py 后：
scp app.html axs-vps:/opt/medkb/app.html
scp server_cloud.py axs-vps:/opt/medkb/server_cloud.py
ssh axs-vps "systemctl restart medkb"     # 仅改了 .py 才需要
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

- 生产：PostgreSQL `medkb`（本机 127.0.0.1）。连库：`ssh axs-vps` 后用 `psql`，DSN 见 `systemctl cat medkb.service`。
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
