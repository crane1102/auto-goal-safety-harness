# Contributing

1. Keep changes inside this repository; do not add credentials, `.env` files, session databases, runtime logs, or agent configuration.
2. Preserve fail-open behavior: a harness failure must abandon the current decision rather than block the host application.
3. Do not add historical-session reads, native GoalManager calls, background daemons, infinite retries, or implicit scheduling.
4. Add a regression test for every behavior change.
5. Run both commands before submitting:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

6. Report resource, platform, and failure-mode observations honestly; do not call a green unit suite proof of native integration safety.
