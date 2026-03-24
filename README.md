# IPL 2026 Fantasy Draft Conductor

Full-stack draft app with real-time sync, admin panel, and viewer page.

## URLs
- `/`          → Viewer page (login as viewer or admin)
- `/admin.html` → Dedicated admin panel
- `/api/draft`  → Draft data (JSON)
- `/api/health` → Health check

## Local Development

```bash
npm install
node server.js
# Open http://localhost:3000
```

## Configuration (Environment Variables)

| Variable        | Default              | Description              |
|----------------|----------------------|--------------------------|
| `PORT`          | 3000                 | Server port              |
| `JWT_SECRET`    | (change this!)       | JWT signing secret       |
| `ADMIN_PASSWORD`| ipl2026admin         | Admin login password     |

## Deploy to Render

1. Push this folder to a GitHub repo
2. Render Dashboard → New → **Web Service**
3. Connect your GitHub repo
4. Settings:
   - **Runtime**: Docker  ← uses the Dockerfile automatically
   - **Build Command**: *(leave blank — Docker handles it)*
   - **Start Command**: *(leave blank)*
5. Add Environment Variables:
   - `ADMIN_PASSWORD` = your chosen password
   - `JWT_SECRET` = any long random string
6. Click Deploy

Your app will be live at `https://your-app.onrender.com`

## Deploy to Railway

1. Install Railway CLI: `npm i -g @railway/cli`
2. `railway login`
3. `railway init` (in this folder)
4. `railway up`
5. Set env vars in Railway dashboard

## Admin Panel

Open `https://your-app.onrender.com/admin.html`

Features:
- Live draft with pick/skip/undo
- Full draft order table
- Team roster viewer
- Team name editor
- Player pool management (add/remove/import CSV)
- Export picks as CSV
- Reset draft
- Share viewer URL

## Viewer Page

Open `https://your-app.onrender.com`

Choose **Viewer** — no password needed.
Real-time updates via WebSocket. Works on mobile.
