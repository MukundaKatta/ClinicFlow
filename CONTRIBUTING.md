# Contributing to ClinicFlow

Thank you for your interest in contributing to ClinicFlow! This document provides guidelines for contributing to this project.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a feature branch from `main`

```bash
git checkout -b feature/your-feature-name
```

4. Install development dependencies:

```bash
make dev
```

## Development Workflow

### Running Tests

```bash
make test
```

### Linting

```bash
make lint
```

### Type Checking

```bash
make typecheck
```

### Formatting

```bash
make fmt
```

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions
- Use type annotations for all function signatures
- Write docstrings for public methods (NumPy style)
- Keep functions focused and concise

## Pull Request Process

1. Ensure all tests pass (`make test`)
2. Run the linter (`make lint`) and type checker (`make typecheck`)
3. Update documentation if you changed public APIs
4. Write clear commit messages following [Conventional Commits](https://www.conventionalcommits.org/)
5. Open a PR against `main` with a description of the changes

## Reporting Issues

- Use GitHub Issues to report bugs or request features
- Include steps to reproduce for bug reports
- Provide expected vs. actual behavior

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
