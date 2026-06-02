import { defineConfig } from 'vitest/config';
import path from 'path';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

import { VITE_DEFAULT_PORT } from './src/constants/dev';

let base: string = '';
// 1. if NOTEBOOK_ID is set, use /notebook-sessions/${NOTEBOOK_ID}/ports/5173/ for dev server
if (process.env.NOTEBOOK_ID && process.env.NODE_ENV === 'development') {
    const notebookId = process.env.NOTEBOOK_ID;
    base = `/notebook-sessions/${notebookId}/ports/${VITE_DEFAULT_PORT}/`;
}
const proxyBase: string = base === '' ? '/' : base;

// https://vite.dev/config/
export default defineConfig({
    plugins: [
        {
            name: 'shiki-themes-subset',
            enforce: 'pre',
            resolveId(source, importer) {
                if (
                    source === './themes.mjs' &&
                    importer &&
                    importer.includes('shiki/dist/')
                ) {
                    return path.resolve(__dirname, './src/lib/shiki-themes.ts');
                }
            },
        },
        react(),
        tailwindcss(),
        {
            name: 'strip-base',
            apply: 'serve',
            configureServer({ middlewares }) {
                middlewares.use((req, _res, next) => {
                    if (base !== '' && !req.url?.startsWith(base)) {
                        req.url = base.slice(0, -1) + req.url;
                    }
                    next();
                });
            },
        },
    ],
    resolve: {
        alias: [
            { find: '@', replacement: path.resolve(__dirname, './src') },
            // Use Shiki's web bundle (56 languages) instead of the full bundle (235 languages).
            { find: /^shiki$/, replacement: 'shiki/bundle/web' },
        ],
    },
    base: base,
    build: {
        outDir: '../fastapi_server/static/',
        manifest: true,
    },
    server: {
        host: true,
        allowedHosts: ['localhost', '127.0.0.1', '.datarobot.com', '.drdev.io'],
        proxy: {
            [`${proxyBase}api/`]: {
                target: 'http://localhost:8080',
                changeOrigin: true,
                rewrite: path => path.replace(new RegExp(`^${proxyBase}`), ''),
            },
        },
    },
    test: {
        globals: true,
        environment: 'jsdom',
        include: ['**/*.test.ts', '**/*.test.tsx'],
        setupFiles: ['./tests/setupMocks.ts', './tests/setupTests.ts'],
        typecheck: {
            tsconfig: './tsconfig.test.json',
        },
    },
});
