.PHONY: install-dev-python install-python fmt-ci-python fmt-python lint-python run-tests generate-openapi check-openapi install-precommit run-precommit check-local-state

install-python: 
	@pip install -r ./backend/requirements.txt

install-dev-python:
	@pip install -r ./backend/requirements-dev.txt

install-frontend-deps:
	cd frontend && npm install

install-precommit:
	pre-commit install

run-precommit:
	pre-commit run --all-files

fmt-python:
	black . $(ARGS) --target-version py311

fmt-ci-python:
	black --check . --target-version py311

lint-python:
	flake8 .

check-local-state:
	semgrep --config .semgrep/no-local-state.yml --error backend/app/

run-pytest:
	pytest

generate-openapi:
	python3 backend/scripts/generate_openapi.py

check-openapi:
	python3 backend/scripts/generate_openapi.py --check

docker-build:
	docker build -t gc-signin-ci-build ./backend
