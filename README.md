# Auto-Goal Safety Harness

A standalone, dependency-light test project for experimenting with auto-goal behavior without modifying an agent runtime.

> **Safety contract:** it may have no effect; it must not harm ordinary system operation.

## What is included

The package contains the mechanisms tested today, not only a prompt or skill:

- conservative, explicit-input classification;
- fail-closed rejection of internal runtime markers;
- explicit simulation gate;
- isolated in-memory `SimulationStore`;
- bounded redacted audit writer;
- symlink rejection and `O_NOFOLLOW` protection where available;
- concurrency protection and bounded audit output;
- safe handling of cancellation, timeout, no-progress, duplicate wake, abnormal exit, and reinitialization;
- no historical-session reads, native GoalManager calls, queue/lock/continuation/pending-event writes, background workers, or infinite retries.

This is a user-layer safety harness, not a replacement or repair of a native GoalManager.

## Install and run

```bash
git clone https://github.com/crane1102/auto-goal-safety-harness.git
cd auto-goal-safety-harness
python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

No credentials, network service, Hermes installation, or production configuration is required.

## Boundary

The project is intentionally isolated. It only operates on text, explicitly supplied metadata, an in-memory simulation store, and an explicitly selected audit path. It does not read session history or alter any production agent directory. Keep production auto-goal disabled until independent testing establishes a safe integration contract.

See `docs/` for the threat model, inventory, validation report, and contribution rules.
