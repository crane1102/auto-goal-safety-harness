# Threat Model and Non-Goals

## Assets protected

Ordinary application availability, production agent state, session history, continuation queues, pending events, locks, credentials, and bounded local audit storage.

## Threats addressed

- forged internal metadata causing a goal to be resumed;
- stale state surviving process restart or repeated initialization;
- audit path symlink redirection;
- unbounded audit growth or concurrent corruption;
- exceptions, duplicate wakeups, cancellation, timeout, and no-progress paths blocking the host application;
- accidental coupling to Hermes native state.

## Non-goals

This project does not prove that a native GoalManager is safe, does not enable production goals, does not schedule work, and does not guarantee useful goal detection. Integration requires a separate review and a fresh safety contract.
