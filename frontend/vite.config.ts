import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// Custom plugin to enforce UTF-8 encoding headers for text, JS, CSS, and HTML files
const utf8HeadersPlugin = () => ({
  name: 'utf8-headers',
  configureServer(server: any) {
    // [إصلاح 2026-09-03] المعامل الأول غير مستعمل، و noUnusedParameters في tsconfig.node.json
    // كان يجعل `tsc -b` يفشل — أي أن `npm run build` كان متعطلاً أصلاً.
    // البادئة _ هي الاصطلاح الذي يقبله TypeScript لمعامل مقصود إهماله.
    server.middlewares.use((_req: any, res: any, next: any) => {
      const setHeader = res.setHeader;
      res.setHeader = function (name: string, value: any) {
        if (name.toLowerCase() === 'content-type' && typeof value === 'string') {
          if (
            (value.includes('javascript') ||
              value.includes('css') ||
              value.includes('html') ||
              value.includes('json')) &&
            !value.includes('charset')
          ) {
            value = `${value}; charset=utf-8`;
          }
        }
        return setHeader.call(this, name, value);
      };
      next();
    });
  },
});

const apiProxy = {
  '/api': {
    // العنوان قابل للضبط حتى يمكن تشغيل أكثر من خادم تطوير جنباً إلى جنب
    // (مراجعة/تصميم على منفذ، وعملك الجاري على آخر). الافتراضي لم يتغيّر.
    target: process.env.VITE_API_TARGET || 'http://localhost:8001',
    changeOrigin: true,
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss(), utf8HeadersPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: apiProxy,
  },
  // وضع العرض التجريبي (ops/demo.sh): يخدم نسخة البناء ويمرّر /api إلى الخادم الخلفي.
  // allowedHosts مفتوح لأن رابط النفق (trycloudflare.com وغيره) اسمه يتغيّر في كل مرة.
  preview: {
    host: '0.0.0.0',
    port: 3000,
    allowedHosts: true,
    proxy: apiProxy,
  },
})
