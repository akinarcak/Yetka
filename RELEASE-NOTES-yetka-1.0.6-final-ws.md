# Yetka 1.0.6 final WS

- Scoped the notification WebSocket superuser exception to `/ws/notifications/site-msg/` so service-account WebSockets remain protected.
- Added Turkish locale fallback for the refreshed Lina UI and removed the obsolete License route/corporate links.
- Added production Koko certificate bootstrap for bare-metal/systemd deployments.
- Verified core health, four active services, 13 permanent wrapper tests, dashboard WebSocket, and Luna UI on the test server.
- A real asset session remains pending because the shared test workspace currently contains zero assets.

See [`docs/PRODUCTION-DEPLOY-CHECKLIST.md`](docs/PRODUCTION-DEPLOY-CHECKLIST.md) for rollout and rollback steps.
