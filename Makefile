PY := .venv/bin/python
.PHONY: setup build lint test bench demo scan model
setup:
	python3 -m venv .venv
	$(PY) -m pip install -r requirements-dev.txt
	npm ci --prefix apps/web
build:
	npm run build --prefix apps/web
lint:
	.venv/bin/ruff check src scripts tests
	.venv/bin/ruff format --check src scripts tests
	npm run lint --prefix apps/web
test:
	$(PY) scripts/local.py test
bench:
	$(PY) scripts/local.py bench
	$(PY) scripts/render_readme.py
demo: setup build
	$(PY) scripts/local.py serve
scan:
	$(PY) -m pip_audit -r requirements-dev.txt -r requirements-browser.txt --progress-spinner off
	npm audit --prefix apps/web --audit-level=low
model:
	$(PY) -m pip install -r requirements-model.txt
	$(PY) scripts/model_setup.py
	PYTHONPATH=src $(PY) scripts/model_eval.py
