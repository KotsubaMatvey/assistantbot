# Assistant Bot Mini App

Static Telegram Mini App prototype for the bot control surface.

## What is included

- shopping composer with multiplier-aware examples;
- market watch dashboard for BTC, BTC.D, S&P 500, Nasdaq and Dow Jones;
- assistant controls inspired by OpenClaw operator commands: status, compact, new, agenda;
- memory timeline mock for future live data.

## Local preview

Open `miniapp/index.html` in a browser. Telegram-specific actions fall back to showing the
payload that would be sent through `Telegram.WebApp.sendData`.

## Telegram setup

1. Deploy this folder as static HTTPS content.
2. Set `TG_MINI_APP_URL=https://your-domain.example/`.
3. Restart the bot.
4. Run `/mini_app` in Telegram.

The backend currently exposes the button and manifest foundation. A future step can add a
`WebAppData` handler that maps Mini App payloads to existing bot commands.
