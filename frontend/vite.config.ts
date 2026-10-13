import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// 构建/预构建目标（dev 与 build 共用，确保两端一致）。
// 注意：不要回退到 Vite 默认的 `"modules"`（= chrome87/edge88/es2020/firefox78/safari14）。
// 本机 pnpm store 里的 esbuild 实际为 0.28.2（目录名与 package.json 仍写着 0.21.5，
// 属安装文件被混合覆盖），0.28.2 已不支持 `safari14`，会抛出
//   "Transforming destructuring to the configured target environment is not supported yet"
// 导致依赖预构建（dev）与产物打包（build）双双失败。
// 依赖树修复（把 esbuild 重装回 ^0.21.3）后，该目标依然有效，可保留。
const BUILD_TARGET = ["chrome100", "edge100", "firefox100", "safari15"];

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    // 显式声明需要预构建的依赖，避免"首次被源码引用时才临时发现"触发依赖重优化：
    // 那一刻 browserHash 会变更，已打开页面继续请求旧 hash 的 dep 文件，就会收到
    // `504 (Outdated Optimize Dep)`。
    // katex 是按需引入的重依赖（仅公式组件使用），若不在启动时预构建，就会在首次
    // 打开含公式的页面时才重优化。新增按需引入的重依赖时，请一并加到这里。
    include: ["katex"],
    esbuildOptions: {
      // 依赖预构建不继承 build.target，必须单独指定（Vite 5.4 优化器默认即上述旧目标集）
      target: BUILD_TARGET,
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@components": path.resolve(__dirname, "./src/components"),
      "@pages": path.resolve(__dirname, "./src/pages"),
      "@hooks": path.resolve(__dirname, "./src/hooks"),
      "@store": path.resolve(__dirname, "./src/store"),
      "@api": path.resolve(__dirname, "./src/api"),
      "@types": path.resolve(__dirname, "./src/types"),
      "@utils": path.resolve(__dirname, "./src/utils"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true, // 标注实时协作等走 /api/v1/ws/* 的 WebSocket 升级
      },
      "/ws": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    target: BUILD_TARGET,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom", "react-router-dom"],
          ui: ["antd", "@ant-design/icons"],
          pdf: ["pdfjs-dist", "react-pdf"],
          graph: ["react-force-graph-2d", "react-force-graph-3d"],
          chart: ["echarts", "echarts-for-react"],
        },
      },
    },
  },
});
