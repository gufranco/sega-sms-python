.PHONY: gate format format-check lint types yaml shell coverage package replay conformance

TESTS = $(shell find segasms conformance window -name '*.test.py' | sort)

gate: format-check lint types yaml shell coverage

format:
	ruff format .
	prettier --write .

format-check:
	ruff format --check .
	prettier --check .

lint:
	ruff check .

types:
	mypy

yaml:
	yamllint --strict .

shell:
	shellcheck --severity=style scripts/run scripts/play scripts/*.sh

coverage:
	coverage erase
	@failed=""; \
	for test in $(TESTS); do \
		coverage run --append "$$test" || failed="$$failed $$test"; \
	done; \
	coverage report || failed="$$failed coverage"; \
	if [ -n "$$failed" ]; then echo "failed:$$failed"; exit 1; fi

package:
	rm -rf dist
	uv build --wheel --out-dir dist
	python -m conformance.package dist/segasms-*.whl

replay:
	python -m conformance.corpus
	python -m conformance.speed

conformance:
	python -m conformance.documents --check
	python -m conformance.quotes
	python -m conformance.external
