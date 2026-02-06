.PHONY: setup check run harness demo

PYTHON := .venv/bin/python3
PIP := .venv/bin/pip

setup:
	python3 -m venv .venv
	$(PIP) install -r requirements.txt
	cp -n .env.example .env || true
	@echo "Set MOONSHOT_API_KEY in .env"

check:
	./scripts/check.sh

run:
	$(PYTHON) main.py

harness:
	$(PYTHON) scripts/harness_checks.py

demo:
	./scripts/demo.sh
