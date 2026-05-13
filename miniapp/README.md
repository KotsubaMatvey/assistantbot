# Assistant Bot Mini App

Vite + React + TypeScript Telegram Mini App for the second brain control surface.

## What is included

- assistant-first dashboard with status, compact, new, agenda, today, tasks and context actions;
- animated pixel assistant foundation that sends safe routing payloads to the bot;
- typed client-side event bus and rule engine for UI state transitions;
- memory timeline mock for future live data;
- market watch dashboard for BTC, BTC.D, S&P 500, Nasdaq and Dow Jones;
- shopping composer with multiplier-aware examples;
- pantry, budget and price alert quick actions;

## Local development

```bash
npm install
npm run dev
```

Telegram-specific actions fall back to showing the payload that would be sent through
`Telegram.WebApp.sendData`.

## Telegram setup

1. Deploy this folder as a Vite static app.
2. Set `TG_MINI_APP_URL=https://your-domain.example/`.
3. Restart the bot.
4. Run `/mini_app` in Telegram.

The backend accepts `WebAppData` payloads for second brain command routing, basket comparison
and the pixel helper. The helper is intentionally safe: it routes to existing bot commands
instead of running arbitrary tools.

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
