import { defineConfig } from 'vite';
// import inspect from 'vite-plugin-inspect';
import vue from '@vitejs/plugin-vue';
import vueJsx from '@vitejs/plugin-vue-jsx'
import frappeui from 'frappe-ui/vite'

export default defineConfig({
  plugins: [
    frappeui(),
    // inspect(),
    vue({
      script: {
        propsDestructure: true,
      },
    }),
    vueJsx(),
    {
      name: 'transform-index.html',
      transformIndexHtml(html, context) {
        if (!context.server) {
          return html.replace(
            /<\/body>/,
            `
            <script>
                if (window.frappe && frappe.boot) {
                    Object.keys(frappe.boot).forEach(key => {
                        window[key] = frappe.boot[key];
                    });
                }
            </script>
            </body>
            `
          )
        }
        return html
      },
    }
  ],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../frappe_hfhg/public/whatsapp',
    emptyOutDir: true,
    commonjsOptions: {
      include: [/tailwind.config.js/, /node_modules/],
    },
    sourcemap: true,
  },
  optimizeDeps: {
    include: [
      'feather-icons',
      'showdown',
      'frappe-ui',
      'tailwind.config.js',
      'engine.io-client',
      'prosemirror-state',
    ],
  },
});
