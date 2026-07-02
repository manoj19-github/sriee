# Coding Log — 110008 Open WebSocket v1

Implemented pre-accept desktop authentication, protocol negotiation, welcome frame, live connection registry, bounded subscriptions/queues, frame-size and message-rate controls, ping/unsubscribe handling and deterministic cleanup.

The first suite exposed a disconnect cleanup race. Child receive/broker tasks are now retained, cancelled and gathered in `finally`; ASGI cancellation is handled as a normal disconnect.
