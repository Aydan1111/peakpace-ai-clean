# PeakPace AI — Frontend

Dark-themed React SPA for the PeakPace AI racing intelligence backend.

## Setup

```bash
npm install
```

## Development

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `https://peakpace-ai.onrender.com` | Backend API base URL |

Copy `.env.example` to `.env` and customise if needed.

## Production Build

```bash
npm run build
```

Output goes to `dist/`.

## Deploy to Vercel

1. Push this repo to GitHub.
2. Import the repo in [vercel.com/new](https://vercel.com/new).
3. Set **Root Directory** to `frontend`.
4. Vercel auto-detects Vite — no extra config needed.
5. Add environment variable `VITE_API_BASE_URL` in project settings if you want to override the default backend URL.
6. Deploy.
