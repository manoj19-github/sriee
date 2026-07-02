# Testing Log — 110008 Open WebSocket v1

- Initial run: **99 passed, 1 failed** — WebSocket context exit left a cancelled child receive task unreconciled.
- Fix: deterministic cancellation/gather of both child tasks plus registry/broker cleanup.
- Final run: **100 passed in 2.33 seconds, 0 warnings**.

Covered authenticated welcome/ping, missing credentials, protocol mismatch, subscription bounds, frame-size limit, rate limit and connection cleanup.
