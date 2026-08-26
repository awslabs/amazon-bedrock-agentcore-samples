import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    /**
     * **The dev server proxies `/api` to the deployed conversation API**, so `npm run dev` runs
     * against real infrastructure with no local backend and no CORS configuration to maintain.
     *
     * More importantly, it is what makes the httpOnly cookie work in development. A cookie set by
     * `execute-api.amazonaws.com` with `SameSite=Strict` is not sent to `localhost:5173` — a
     * different site — so calling the API directly from the dev server would appear to sign in and
     * then be unauthenticated on every request afterwards. Proxying makes the browser see one origin.
     *
     * `VITE_API_TARGET` names the deployed stage; the deploy script reads it from SSM.
     */
    proxy: {
      '/api': {
        target:
          process.env.VITE_API_TARGET ?? 'https://example.execute-api.us-east-1.amazonaws.com',
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/api/, '/v1'),
      },
    },
  },
});
