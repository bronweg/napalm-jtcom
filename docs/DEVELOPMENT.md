# Development Guide

## Prerequisites

- Python 3.11+
- Git

## Setup

```bash
git clone https://github.com/bronweg/napalm-jtcom.git
cd napalm-jtcom

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Upgrade packaging tools
pip install --upgrade pip setuptools wheel

# Install project + dev dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

Run a specific test file:

```bash
pytest tests/unit/test_parser_vlan.py -v
```

## Code Quality

```bash
# Lint
ruff check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/
```

## Project Structure

```
napalm-jtcom/
  src/napalm_jtcom/
    driver.py          # NAPALM NetworkDriver subclass
    client/            # HTTP session and request helpers
    parser/            # HTML → Python object parsers
    model/             # Typed dataclass models
    vendor/jtcom/      # JTCom-specific endpoint paths and field mappings
  tests/
    unit/              # Parser and session unit tests
    fixtures/          # HTML snapshots from real devices
  examples/            # Runnable usage examples
  docs/                # Developer documentation
```

## Adding a New Getter

1. Identify the CGI endpoint in `vendor/jtcom/endpoints.py`.
2. Capture an HTML fixture in `tests/fixtures/`.
3. Add a parser function in `parser/`.
4. Add a typed model in `model/` if needed.
5. Implement the getter in `driver.py` calling the session + parser.
6. Write tests in `tests/unit/`.

## Releasing

```bash
pip install build
python -m build
twine upload dist/*
```
