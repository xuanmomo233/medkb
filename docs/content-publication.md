# 章节内容发布流程

网页、App 和 AI 都读取 chapters。正文、前置元数据和独立教材页图索引使用同一 manifest 和同一数据库事务发布。

1. 在线上容器运行 scripts/publish_chapters.py capture --output baseline.json.gz，下载并复用这份基线。
2. 本地设置 PYTHONPATH=backend，运行 backend/scripts/publish_chapters.py prepare --baseline baseline.json.gz --kb kb --id 批次名 --output manifest.json。
3. 图片变更在 manifest 的 textbook_pages 中明确列出 source_key 和 page，按书目、页码排序。正文和所有有效 frontmatter 完整保存。
4. 上传 manifest，在共享发布锁内运行 apply --manifest manifest.json --backup before.json.gz --output receipt.json。各输出必须是新路径。
5. 发布器检查前置正文和页码 SHA、目标正文 SHA、活跃教材及页图资产；单事务更新正文和页码，保存批次与清单 SHA，提交后用独立会话读回。
6. 连接中断先运行 check --manifest manifest.json。相同批次只接受同一清单；重试不会重复执行。回退也使用当前 SHA 构造新清单。

修改 Citation 不再改变图片画廊。历史缺少真实核验人/时间的记录单列为 legacy_unattributed，仍属于待补历史归属；新写入缺核验信息属于错误。待核验记录残留归属的原值保存到 citation_metadata_history 后再纠正。

# App 发布流程

tools/release_app.py 从明确源码目录构建，核对线上 build 与旧 APK SHA，要求版本单调递增，并检查新旧签名证书、v1/v2 签名及 APK 内嵌版本，输出 APK 和 JSON 回执。密钥只用于本机构建，不进入源码包和服务器。

上传 APK 后，在 /opt/medkb-v2/.qa-recall-publication.lock 内替换下载接口文件、修改 MEDKB_VERSION 并重建容器以刷新文件挂载；独立核对 /api/version、/app.apk 全文件 SHA、健康状态和保留的挂载。没有真机连接时，不宣称覆盖安装已验证。
