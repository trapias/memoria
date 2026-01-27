# Contributing to MCP Memoria

Thank you for your interest in contributing! This guide explains how to set up a development environment and submit changes via pull request.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/memoria.git
   cd memoria
   ```
3. **Install** with dev dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate   # macOS/Linux
   pip install -e ".[dev]"
   ```
4. **Verify** your setup:
   ```bash
   pytest
   ruff check src/mcp_memoria
   mypy src/mcp_memoria
   ```

## Making Changes

1. Create a branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
2. Make your changes, keeping commits focused and atomic.
3. Follow the existing code style — `ruff` and `mypy` will catch most issues:
   ```bash
   ruff check src/mcp_memoria          # lint
   ruff check --fix src/mcp_memoria    # auto-fix
   mypy src/mcp_memoria                # type check
   ```
4. Add or update tests for any new functionality:
   ```bash
   pytest                              # full suite
   pytest tests/test_something.py -v   # single file
   pytest -k "test_name" -v            # single test
   ```
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/) format:
   ```
   feat: Add new feature
   fix: Correct bug in recall
   docs: Update README
   refactor: Simplify consolidation logic
   test: Add chunking integration tests
   ```

## Submitting a Pull Request

1. Push your branch to your fork:
   ```bash
   git push origin feat/my-feature
   ```
2. Open a pull request against `main` on [github.com/trapias/memoria](https://github.com/trapias/memoria).
3. In the PR description:
   - Summarize **what** changed and **why**
   - Reference any related issue (e.g. `Closes #42`)
   - Note any breaking changes or migration steps
4. Ensure all checks pass (tests, lint, type check).
5. A maintainer will review your PR. You may be asked to make adjustments — just push additional commits to the same branch.

## Reporting Issues

If you find a bug or have a feature request, please [open an issue](https://github.com/trapias/memoria/issues) with:

- A clear description of the problem or proposal
- Steps to reproduce (for bugs)
- Your environment (Python version, OS, Qdrant/Ollama versions)

## Code of Conduct

Be respectful and constructive. We follow common open-source etiquette — treat others as you'd like to be treated.

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).
