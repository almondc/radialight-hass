# Home Assistant Dev Environment (Docker)

This folder contains a **local, isolated Home Assistant dev/test environment** for rapid integration testing. It does not touch your production Home Assistant config.

## Quick start

1) Copy the example env file:
- Copy `ha-dev/.env.example` → `ha-dev/.env`

2) Start the dev instance:
- Run: `docker compose up -d`

3) Open the UI:
- http://localhost:8124

4) Stop the dev instance:
- Run: `docker compose down`

## Where to place the custom integration

Put your integration here:
- `ha-dev/config/custom_components/radialight_cloud`

You can copy or symlink your local integration into that folder (do not point to any production config).

## Logs

Tail logs:
- Run: `docker compose logs -f --tail=200`

## Important warning

This dev environment is **isolated**. Do **NOT** mount or reference your production Home Assistant `config/` folder here.
