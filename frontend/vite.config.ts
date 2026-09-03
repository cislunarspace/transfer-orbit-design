import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1430,
    strictPort: true,
    host: "127.0.0.1",
    // fs.allow 放宽到仓库根：跨语言同步用例 JSON 在 tests/engine/fixtures/
    // （frontend 根之外），vitest 经 ?raw 读取（#470 评审）
    // fs.allow widened to the repo root: the cross-language parity-case JSON
    // lives in tests/engine/fixtures/ (outside the frontend root) and vitest
    // reads it via a ?raw import (#470 review).
    fs: {
      allow: [".."],
    },
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
