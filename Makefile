.PHONY: install test lint run

install:
	python -m pip install -e '.[dev]'

test:
	pytest

lint:
	ruff check .

run:
	uvicorn app.main:app --reload

