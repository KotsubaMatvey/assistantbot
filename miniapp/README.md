# Assistant Bot Mini App

Vite + React + TypeScript Telegram Mini App for the second brain control surface.

## What is included

- assistant-first dashboard with status, compact, new, agenda, today, tasks and context actions;
- live Today, Finance and Memory panels backed by the bot API;
- animated pixel assistant foundation that sends safe routing payloads to the bot;
- typed client-side event bus and rule engine for UI state transitions;
- source connector add/delete/sync actions with backend audit events;
- market watch dashboard for BTC, BTC.D, S&P 500, Nasdaq and Dow Jones;
- shopping composer with multiplier-aware examples;
- pantry, budget and price alert quick actions;

## Local development

```bash
npm install
npm run dev
```

Use `VITE_MINI_APP_API_BASE_URL=http://127.0.0.1:8080` when running against the local
bot API. Telegram-specific actions fall back to `Telegram.WebApp.sendData` when the API is
not reachable.

## Telegram setup

1. Deploy this folder as a Vite static app.
2. Set `TG_MINI_APP_URL=https://your-domain.example/`.
3. Restart the bot.
4. Run `/mini_app` in Telegram.

Open the app from the `/mini_app` keyboard button when you want `Telegram.WebApp.sendData`
actions to return to the bot. The backend accepts `WebAppData` payloads for command routing,
basket comparison, task/note/reminder capture, people notes, finance entries, receipts and
source connector actions.

## Vercel

This folder includes `vercel.json`:

```json
{
  "installCommand": "npm ci",
  "buildCommand": "npm run build",
  "outputDirectory": "dist"
}
```

If the Vercel project root is the repository root, the repository-level `vercel.json`
uses `miniapp/dist` as the output directory instead.
