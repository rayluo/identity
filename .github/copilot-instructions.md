# Copilot Instructions for Identity Library

## Repository Overview

This is the **Identity** library repository, a Python authentication/authorization library that provides high-level APIs for Microsoft identity platform integration. The library is built on top of Microsoft's MSAL Python and is designed specifically for web applications.

### Key Facts
- **Language**: Python (3.8-3.12 supported)
- **Type**: Authentication/Authorization library
- **Target**: Web applications (Django, Flask, Quart)
- **Current Version**: 0.11.0
- **License**: MIT
- **Package Name**: `identity` (available on PyPI)

### Purpose
The library provides simplified APIs for:
- Microsoft Entra ID authentication
- Microsoft Entra External ID
- Azure AD B2C integration
- Web app sign-in/sign-out with automatic session renewal
- Access token acquisition for web APIs
- Incremental consent handling

## Build Instructions & Environment Setup

### Python Environment Setup
**ALWAYS configure the Python environment first before any operations:**
```bash
# The repository uses tox for environment management
# Configure Python environment using the configure_python_environment tool
# Or use tox which creates isolated environments automatically
```

### Installation & Dependencies
```bash
# 1. Install dependencies (REQUIRED before any other operations)
pip install -r requirements.txt

# This installs the package in editable mode with ALL dependencies including:
# - Django, Flask, Quart web frameworks
# - MSAL, requests for authentication
# - pytest, pytest-asyncio for testing
```


### Coding Style

For existing source code, do not make modification only for coding style.
For newly added code snippets or lines that need to be changed in the current task,
follow these guidelines:

- Follow PEP 8 guidelines for Python code.
- Use 4 spaces per indentation level.
- Keep lines ideally under 79 characters, don't exceed 100 characters,
  unless the line contains a long url which we don't want to split into two lines.
- Use docstrings to describe public classes and methods.
- Include type hints for function signatures, using Python 3.9 syntax.

### Running Tests
```bash
# Method 1: Direct pytest (after installing requirements.txt)
pytest

# Method 2: Using tox (RECOMMENDED - creates isolated environment)
tox -e py3

# Tests are located in tests/ directory:
# - test_django.py: Django integration tests
# - test_flask.py: Flask integration tests
# - test_quart.py: Quart integration tests

# Expected results: 9 tests pass with some deprecation warnings
```

### Building Documentation
```bash
# Install documentation dependencies
pip install -r docs/requirements.txt

# Build docs using Sphinx (from repository root)
sphinx-build docs docs/_build

# OR using tox (RECOMMENDED)
tox -e docs

# Documentation outputs to docs/_build/
```

### Type Checking
```bash
# Run type checking with mypy (NOTE: currently has known issues)
tox -e type

# Known issues: Missing type stubs for external libraries
# These errors are expected and do not block development
```

### Building Package
```bash
# Clean previous builds
rm -rf build dist

# Install build dependencies
pip install build

# Build source and wheel distributions
python -m build --sdist --wheel --outdir dist/ .
```

## Project Layout & Architecture

### Root Directory Structure
```
├── identity/                    # Main package source code
│   ├── __init__.py             # Package initialization
│   ├── version.py              # Version information (__version__ = "0.11.0")
│   ├── web.py                  # Core web framework-agnostic Auth class
│   ├── django.py               # Django-specific integrations
│   ├── flask.py                # Flask-specific integrations
│   ├── quart.py                # Quart-specific integrations
│   ├── pallet.py               # Shared utilities for Flask/Quart
│   └── templates/identity/     # HTML templates for login/error pages
├── tests/                      # Test suite
├── docs/                       # Sphinx documentation
├── .github/workflows/          # CI/CD pipeline
├── requirements.txt            # Development dependencies
├── setup.cfg                   # Package configuration
├── pyproject.toml              # Build system configuration
├── tox.ini                     # Testing environments
└── README.md                   # User documentation
```

### Key Configuration Files
- **setup.cfg**: Main package metadata and dependencies
- **pyproject.toml**: Build system (setuptools)
- **tox.ini**: Test environments and commands
- **requirements.txt**: Development dependencies with ALL web frameworks
- **.github/workflows/python-package.yml**: CI/CD pipeline

### Core Architecture
1. **web.py**: Contains the main `Auth` class that is web framework-agnostic
2. **Framework-specific modules**: django.py, flask.py, quart.py provide decorators and helpers
3. **pallet.py**: Shared code between Flask and Quart (both use Pallets ecosystem)
4. **Templates**: Built-in HTML templates for authentication flows

### Known Issues & TODOs
Based on code analysis, there are several TODOs in web.py:
- Line 231: "TODO: Reject a re-log-in with a different account?"
- Line 340: "TODO: Where shall token cache come from?"
- Line 433: "TODO: Support custom domain" for B2C

## CI/CD & Validation Pipeline

### GitHub Actions Workflow
Located in `.github/workflows/python-package.yml`:

**Triggers**: Push to any branch, labeled PRs to dev branch

**Test Matrix**: Python 3.8, 3.9, 3.10, 3.11, 3.12 on Ubuntu

**Pipeline Steps**:
1. Install dependencies (pip, flake8, pytest, requirements.txt)
2. ~~Linting with flake8~~ (currently commented out)
3. Run pytest test suite
4. **Release Pipeline** (conditional):
   - Triggers on tags or release-* branches
   - Builds source and wheel distributions
   - Publishes to TestPyPI (release branches) or PyPI (tags)

### Pre-commit Validation
When making changes, ensure:
1. **Tests pass**: `tox -e py3` or `pytest`
2. **Documentation builds**: `tox -e docs`
3. **Type checking** (optional due to known issues): `tox -e type`

### Dependencies by Framework
The package supports conditional installation:
- **Django**: `pip install "identity[django]"`
- **Flask**: `pip install "identity[flask]"`
- **Quart**: `pip install "identity[quart]"`
- **All (for docs)**: `pip install "identity[all_for_docs]"`

### Working with the Repository

**ALWAYS follow this sequence for development:**
1. Configure Python environment (already done if using tox)
2. Install requirements: `pip install -r requirements.txt`
3. Make your changes
4. Run tests: `tox -e py3` or `pytest`
5. Build docs if needed: `tox -e docs`
6. For releases: Update version in `identity/version.py`

**Package Installation Patterns**:
- Development: `pip install -r requirements.txt` (editable install with all frameworks)
- Production: `pip install "identity[framework]"` where framework is django/flask/quart

**Trust these instructions** - they have been validated against the actual repository structure and build process. Only search for additional information if these instructions are incomplete or incorrect for your specific task.

### Framework-Specific Notes
- **Django**: Uses Django's session system, provides `@login_required` decorator
- **Flask**: Requires Flask-Session, provides `@login_required` decorator
- **Quart**: Async framework, uses Quart-Session, provides `@login_required` decorator
- **All frameworks**: Share the core `Auth` class from web.py for authentication logic

The library is designed to minimize Microsoft identity platform integration complexity while supporting multiple Python web frameworks through a unified API.
