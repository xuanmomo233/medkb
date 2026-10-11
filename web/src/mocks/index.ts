// 自动加载所有 *.mock.ts（仅在 VITE_MOCK=1 时被 main.tsx 引入）
import.meta.glob('./*.mock.ts', { eager: true })
