# Assistant Bot Mini App

Vite + React + TypeScript Telegram Mini App for the bot control surface.

## What is included

- shopping composer with multiplier-aware examples;
- market watch dashboard for BTC, BTC.D, S&P 500, Nasdaq and Dow Jones;
- assistant controls inspired by OpenClaw operator commands: status, compact, new, agenda;
- animated pixel assistant foundation that sends safe routing payloads to the bot;
- typed client-side event bus and rule engine for UI state transitions;
- pantry, budget and price alert quick actions;
- memory timeline mock for future live data.

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

The backend accepts `WebAppData` payloads for basket comparison, command routing and the
pixel helper. The helper is intentionally safe: it routes to existing bot commands instead
of running arbitrary tools.
