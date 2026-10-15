# MedKB 网页端

React + TypeScript + Vite，使用与 Flutter App 相同的 FastAPI 接口。源码入口为 `src/main.tsx`，页面路由在 `src/app/router.tsx`。

## 开发

在 `web/` 下使用 Node.js 22：

```powershell
npm ci
npm run dev
```

Vite 将 `/api`、`/img`、`/uimg` 请求代理到 `http://127.0.0.1:8000`，需要同时运行本地后端。仅演示页面时，可在启动前设置 `$env:VITE_MOCK = '1'`；模拟数据不代表线上数据，生产构建不得开启该变量。

## 检查与构建

```powershell
npm run lint
npm test
npm run build
```

`npm test` 使用 Node 内置测试运行器执行笔记 Markdown 编辑辅助函数测试；`build` 包含 TypeScript 检查及 Vite 构建。现有测试不等于浏览器端到端覆盖，登录、刷题和编辑发布等流程仍需集成验证。

CI 自动执行上述检查。生产部署通过 `deploy/Dockerfile` 构建网页并复制到镜像内 `/app/web`，详细步骤见 [运维手册](../OPS.md)。
