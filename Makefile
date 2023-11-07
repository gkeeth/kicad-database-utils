test_command = python -m unittest

lint:
	ruff check .
format:
	ruff format .
test:
	$(test_command)
test_all:
	SLOW_TESTS=1 $(test_command)
.PHONY: test test_all
