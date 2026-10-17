# 题库增量同步与 AI 整理

代码入口为 `backend/scripts/sync_questions.py`。本流程直接使用 v2 SQLAlchemy 模型，替代旧 `server/wcyk_sync.py` 对 `subjdir/bankgrp/srcfile/parent` 旧字段的写入。

## 数据流程

1. `scan` 使用独立的发现/回扫水位；`catalog` 遍历题库及章节，检查已有题目的修订和较小 ID 的漏题。
2. 原文进入 `sync_documents`，内容变化产生不可变的 `sync_revisions`；统计人数变化只更新最新原文，不反复创建内容提案。转换失败的原文也保存，并在 `status` 中列出。
3. `analyze` 召回当前题目、卡片、章节和已有已核验教材出处候选。AI 按现有分类给建议，并说明具体考点依据。召回分数只用于选候选，不生成关系。
4. `report` 导出原文来源、前后字段、人工校订冲突、严格重复/答案冲突候选、AI 建议、模型名及提示词版本。
5. 管理员填写复核清单，经 `publish --dry-run` 检查后提交。同类关系、卡片关联、严格重复映射和题目正文均在同一事务内写入；任一项失败则整份清单回滚。

同步任务本身只写暂存表。正式发布保留每个来源题记录和已有学习记录；重复关系使用 `question_merges`，同类关系使用 `question_relations`，源题关联使用 `card_questions`，已有前端和学习计划可直接读取。

## 配置与运行

在 `backend` 目录运行，依赖安装为 `python -m pip install -e '.[sync,dev]'`；Docker 镜像已包含同步依赖。

环境配置：`MEDKB_DATABASE_URL` 指向 v2 数据库，`MEDKB_WCYK_TOKEN` 为上游凭据，`MEDKB_GLM_API_KEY` 和 `MEDKB_GLM_MODELS` 沿用现有 AI 配置。分析依次尝试配置的模型，超时或返回无效候选时回退，并记录实际生成有效建议的模型。凭据不进入记录、报告或错误日志。

```text
python -m alembic upgrade head
python scripts/sync_questions.py scan --lane frontier --count 500
python scripts/sync_questions.py scan --lane backfill --start 1 --count 2000
python scripts/sync_questions.py catalog
python scripts/sync_questions.py probe --qid 235290
python scripts/sync_questions.py analyze --limit 50
python scripts/sync_questions.py report --output report-001.json --review-template review-001.json
python scripts/sync_questions.py publish review-001.json --actor 1 --dry-run
python scripts/sync_questions.py publish review-001.json --actor 1
python scripts/sync_questions.py status
```

`--start` 仅用于某个水位第一次建立。后续即使零新增或连续缺号也继续保存水位；网络、鉴权和无法识别的接口错误停在失败位置。五分钟租约防止相同范围重入，每个成功提交续期；进程异常退出后可在租约到期后重跑。

发现扫描默认从当前题库最大数字 qid 后开始；回扫默认从 1 开始，两者互不影响。完整目录扫描每个章节保留分页位置，完成后从第一页开始下一轮。不能只运行发现扫描，否则旧题修订和低 ID 漏题仍不会被检查。

上游适配器基于项目已有 `/api/q_bank`、`/api/chapter`、`/api/question` 接口。分页结构不认识、缺少总数或出现重复页时显示失败，不能把错误当成“没有更多题”。接入线上前应以真实接口抽查题库数量、章节分页、材料题主干及鉴权失败响应；离线用例不能证明远端所有接口结构。

2026-10-17 只读核对了公开接口：`q_bank` 的 `page/pageSize` 生效并返回列表；已存在题目未登录返回 `errno=100143`；不存在题目返回 `errno=1001, errmsg=题目不存在`。同步只把已确认的缺号响应当成缺号，鉴权错误立即停止。受凭据缺失影响，尚未核对登录后的章节题目分页与材料题返回结构。

可先使用 `import-json` 处理人工提供的原始记录，文件格式为：

```json
[
  {
    "raw": {"id": 123, "qBankId": 10, "chapterId": 20, "type": 1, "stem": "题干", "options": ["甲", "乙"], "answer": [0], "analysis": "解析"},
    "source_meta": {"bank_id": "10", "chapter_id": "20", "bank_title": "原题库名称", "chapter_title": "原章节名称"}
  }
]
```

## 人工复核

生成的模板默认 `action: review`，不能直接发布。逐项核对后改为 `publish` 或 `reject`，填写 `note`。`fields` 表示接受哪些上游字段变化；新增题必须确认全部来源内容字段和分类。

- `accept_classification`：采用分类建议；必要时提供同结构的 `classification_override`。分类必须匹配现有目录/系统及题库组；新分类目录需要先通过内容管理维护。
- `remember_classification`：把本次确认的上游题库/章节映射保存下来。只复用题库组、学科目录和系统，不复用单题考点标签。
- `duplicate_of`：选择报告中的严格重复候选。题型、材料主干、题干、选项顺序和答案都需一致，空答案题不提供严格重复映射。
- `relation_ids`：接受 AI 提出的同考点、变式或易混关系题号。
- `card_ids`：关联现有卡片。同步不会把整道原题自动当成卡片标题；卡片改写或拆分需走现有内容编辑流程。
- `citation_ids`：沿用候选教材定位，为该题新增“待核验”出处。章节已核验不等于新题已核验；仍需核对教材原页后通过现有出处管理标为已核验。
- `acknowledge_conflicts`：显式确认首次同步没有历史基线、答案冲突或双方都修改同一字段的情况。

首次绑定现有题号时，系统无法推断上游原文和人工改题的历史关系，因此要求复核确认。后续使用上一次已发布的上游版本作三方比较：上游没有变化的字段保留人工编辑，双方同时改动的字段列入冲突。

首次接入的题号若已存在，且题库名、题型、题干、选项、答案、解析、材料主干逐字段完全一致，只保存来源基线与原有题目快照，不修改题库、不调用 AI。首次接入存在内容差异时仍进入人工复核。

复核哈希绑定上游版本、本地正文和分析证据。题目在复核期间有修改、候选发生变化或上游有新版时，旧清单被拒绝。使用 `analyze --refresh-pending` 重新生成待审提案；旧哈希失效。相同发布清单重试不会重复创建题目和关联。

## 定时任务接入

合并并完成真实上游接口核对后，定时任务可以分别调用 `scan`、`catalog` 和 `analyze`；任务按 `sync_runs` 的状态、范围、计数及完成时间检查结果。AI 单题失败时记录错误类型和尝试次数，并继续分析其他题；下次优先处理尚未尝试的版本。`analyze` 遇到失败项会输出 `failures` 并返回退出码 2，已成功的提案保留；`status` 可查看仍待处理的分析失败。

线上旧 cron 使用旧数据库环境文件。2026-10-17 已用独立同步容器接入 v2 数据库、应用同步迁移，并将失效任务替换为每日 03:00 的新版任务。当前状态为 `waiting_credentials`，等待现场登录材料；尚未实际拉取或发布新题。同一批数据的原文和发布前后快照属于持续审计数据，应保留；它们不是临时下载缓存。

同日检查旧 cron 的依赖，`/opt/medkb/wcyk_sync.py` 存在，但 `/opt/medkb/wcyk_api.py` 和 `/opt/medkb/token.txt` 缺失；当前旧任务不能据 cron 记录认定为正常同步。新版接入应使用容器内此 CLI 和环境凭据。

同步可独立部署为 `deploy/Dockerfile.sync`，使用同一个 v2 数据库与 Docker 网络，不需要重启网页/API。`deploy/run-question-sync.sh` 安装到 `/opt/medkb-v2/question-sync/run.sh`，读取该目录 `.env`，使用 `medkb-question-sync:current` 镜像。凭据缺失时记录 `waiting_credentials`，不会误报同步成功；`status.json` 分别保留周期运行、登录探测和状态查询的结果。

建议每日 03:00 运行 `run.sh cycle`，完整目录检查后分析最多 50 个变更版本。原题来源、版本和待审提案持久化在数据库中；运行日志按模式保留当前一份。首次需运行 `run.sh probe` 验证登录及章节分页，再开启正常接入。Docker `--env-file` 文件使用实际值 `KEY=value`，不要额外包引号。

## 现场登录材料接入

旧 `server/wcyk_api.py` 的 `encode_token()` 会现场生成带时间戳的请求 Token，其输入仍是已登录会话的基础令牌。项目没有替代用户重新登录微信小程序的流程。

新版 `backend/scripts/configure_upstream.py` 接受基础令牌、登录后完整请求 URL、请求中的加密 Token、登录 JSON 或 HAR。它按同一协议提取基础令牌，并实际读取已知上游题目确认登录有效后，才原子更新 `MEDKB_WCYK_TOKEN`；失败保留原配置。HAR 只提取 `api.ixunke.cn/xizongcangqiong/api/` 的请求，材料和令牌不输出到日志。

```text
python scripts/configure_upstream.py --input-file /private/upstream-request.txt --env-file /config/.env
```

本地可把登录材料保存为 `server/token.txt`、`server/upstream-request.txt` 或 `server/upstream-login.har`；这三个路径已加入 Git 忽略。向服务器传输后，在同步镜像内执行该入口，再运行 `run.sh probe` 核对章节分页。令牌过期时重复此过程，无需修改同步业务代码。

上游返回实际登录错误 `100143` 或 HTTP 401 时，任务保留当前水位、返回退出码 78，并进入等待登录凭据状态。它不能用项目自己的登录凭据替代万川会话，也不能在没有用户登录的情况下生成基础令牌。
