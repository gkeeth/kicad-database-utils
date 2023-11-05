lint:
	ruff check .
format:
	ruff format .
test:
	./run_tests.py
.PHONY: test
