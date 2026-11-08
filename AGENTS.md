# Working on engineering-change-agents

## Fast feedback

| What | Command | Time |
|---|---|---|
| Lint and format, Python and web | `make check` | ~10 s |
| All tests | `make test` | ~10 s (first run trains the surrogate, ~15 s) |
| Development experiments | `make develop` | ~45 s |

## Invariants

1. **The agents never see the truth.** Only `evaluate.py` and `experiments.py` read `data/truth/`; nothing on the
   agent side imports `eca.world.physics`. `tests/test_world_and_isolation.py` checks it.
2. **Code decides, models read and write.** The recommendation comes from `_policy()`; the model extracts and
   summarises. The `model decides` ablation exists to show the cost of the alternative.
3. **The surrogate decides only inside its interval and its envelope.** Everything else goes to a full simulation.
   A model reaches production only through the promotion gates in `config/eca.toml [lim]`.
4. **Every figure has a source.** The reviewer checks summaries against the provenance ledger.
5. **People release.** Change orders need the configured roles, signed by different people. No solution calls a tool
   marked for approval.
6. **The standards are checked, not described.** A new solution declares a `SPEC` and must pass `eca conformance`.
7. **Settings in config.** Rates, prices, gates, thresholds, configurations and ablations live in
   `config/eca.toml`; standards in `config/standards.toml`; the dashboard's visual constants in
   `web/src/theme/tokens.ts`.
8. **Generated reports.** `reports/results.json`, `reports/RESULTS.md`, the README block and `web/public/data` come
   from `make report`.

## The held-out rule

The held-out requests and the systems they depend on are pinned in `config/heldout.sha256`, recorded before any agent
code existed. `eca heldout` refuses to run if they changed and refuses a second run without `--again`, which is
logged. When the held-out run shows a problem, publish it, fix it with a test on development data, and do not rerun
the held-out set to improve the number.
