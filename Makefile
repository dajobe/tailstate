.PHONY: sync test test-cov fmt ruff typecheck lint verify install-git-hook

UV ?= uv

GIT_HOOK_SRC := bin/git-hooks/pre-commit

sync:
	$(UV) sync

test:
	$(UV) run pytest

test-cov:
	$(UV) run pytest --cov=src/tailstate --cov-report=term-missing

fmt:
	$(UV) run black src tests

ruff:
	$(UV) run ruff check src tests

typecheck:
	$(UV) run mypy src tests

# Same checks as ./bin/pre-submit full (Black reformats files).
lint: fmt ruff typecheck test

# Types + ruff + tests only (no formatting writes).
verify: ruff typecheck test

# Install ./bin/git-hooks/pre-commit as .git/hooks/pre-commit (not committed).
install-git-hook: $(GIT_HOOK_SRC)
	install -m 0755 "$(CURDIR)/$(GIT_HOOK_SRC)" "$$(git rev-parse --git-dir)/hooks/pre-commit"
	@echo "Installed $$(git rev-parse --git-dir)/hooks/pre-commit"
