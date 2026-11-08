PY ?= python3
export PYTHONPATH := src

.PHONY: check test world lim develop heldout report serve web conformance
check:        ## lint and format, Python and web
	ruff check src tests scripts && ruff format --check src tests scripts
	cd web && npx tsc --noEmit && npx eslint src test
test:         ## 36 Python tests and the dashboard tests
	$(PY) -m pytest -q
	cd web && npx vitest run
world:        ## rebuild the synthetic world (deterministic; the held-out pin must still match)
	$(PY) scripts/build_world.py
lim:          ## train, calibrate and register the crash surrogate
	$(PY) -m eca.cli lim-train
develop:      ## every configuration on the development requests
	$(PY) -m eca.cli develop
heldout:      ## the pinned held-out requests, once
	$(PY) -m eca.cli heldout
report:       ## reports/results.json, reports/RESULTS.md, the README block, the dashboard data
	$(PY) -m eca.cli report
conformance:  ## the architecture standards against every solution
	$(PY) -m eca.cli conformance
serve:        ## the API on :8000
	$(PY) -m eca.cli serve
web:          ## the dashboard on :5173
	cd web && npm ci && npm run dev
