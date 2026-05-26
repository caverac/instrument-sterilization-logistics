# Contributing to instrument-sterilization-logistics

Thanks for your interest in contributing! This document covers the setup, workflow, and code quality standards for the project.

## Prerequisites

- [mise](https://mise.jdx.dev/) (manages Node 25, Python 3.14, uv)
- [Yarn 4](https://yarnpkg.com/) (bundled via Corepack)

## Setup

```bash
mise install
corepack enable
yarn install
uv sync --all-groups
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

The last command installs git hooks that run automatically on every commit. This is **required** before making any changes.

## Development workflow

1. Create a branch from `main`
2. Make your changes
3. Commit using [Conventional Commits](#commit-messages)
4. Open a pull request against `main`
5. CI must pass before merging

## Pre-commit hooks

Every commit is checked automatically by [pre-commit](https://pre-commit.com/). The hooks enforce all of the project's code quality standards so that issues are caught locally before reaching CI.

### Python hooks

| Hook       | What it does                      |
| ---------- | --------------------------------- |
| black      | Formats code (line length 120)    |
| isort      | Sorts imports (black-compatible)  |
| flake8     | Lints for style and common errors |
| pylint     | Static analysis                   |
| pydocstyle | Enforces NumPy-style docstrings   |
| mypy       | Strict type checking              |

### JS/TS hooks

| Hook     | What it does                     |
| -------- | -------------------------------- |
| prettier | Formats code                     |
| eslint   | Lints with zero warnings allowed |
| tsc      | TypeScript type checking         |

### Commit message hook

| Hook       | What it does                                     |
| ---------- | ------------------------------------------------ |
| commitlint | Validates Conventional Commit format (see below) |

If a hook fails, fix the issue and re-stage your changes. Black and isort auto-fix files in place, so you just need to `git add` the corrected files and commit again.

## Commit messages

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
type(scope): description
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

Examples:

```
feat(ingest): add CensiTrac adapter
fix(routing): handle empty candidate facility set
docs: clarify preference-card learning loop
```

Commit messages drive automated releases — `feat` triggers a minor version bump, `fix` triggers a patch. A `BREAKING CHANGE` footer triggers a major bump.

## Code quality standards

This project enforces strict code quality. All of the following must pass in CI before a PR can be merged:

- **Zero lint warnings** across both Python and JS/TS
- **Strict mypy** with no untyped definitions
- **NumPy-style docstrings** on all public modules
- **120-character line length** for Python (configured in black, isort, pylint)

Test coverage thresholds will be enforced per-package once packages exist; see each package's `pyproject.toml` or `package.json`.

## Running checks manually

```bash
# Python (once packages exist)
uv run black --check packages/
uv run isort --check-only packages/
uv run flake8 packages/
uv run pylint packages/
uv run pydocstyle packages/
uv run mypy packages/
uv run python -m pytest packages/ -v

# JS/TS
yarn lint
yarn format
yarn typecheck

# Full build
yarn build
```

## Project structure

See [`notebooks/notes/logs/20260525-idea.md`](notebooks/notes/logs/20260525-idea.md) §12 for the planned package layout. The repo currently contains the monorepo boilerplate (linters, CI, hooks); package skeletons land as the M1–M3 build order in §13 of the design doc progresses.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
