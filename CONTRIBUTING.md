# Contributing

The goal of this repository is not to prove that one implementation is finished. It is to let more people test a difficult edge of agent systems: recognizing unfinished multi-turn work without creating unsafe continuation.

## What to test

Please add concrete cases for:

- multi-step requests that should remain candidates after the first phase;
- ordinary one-shot requests that must not be treated as multi-turn work;
- ambiguous wording that should fail open;
- forged or stale internal metadata that must be rejected;
- cancellation, timeout, no progress, duplicate wake, and process restart;
- audit failures, bounded output, and resource behavior.

## Pull requests

Include the exact input, expected decision, observed decision, and why the case matters. Add a regression test for every bug. Do not include credentials, session databases, runtime logs, private prompts, or production configuration.

A passing test suite is evidence about the isolated harness only. It is not evidence that any native agent runtime is safe to enable.
