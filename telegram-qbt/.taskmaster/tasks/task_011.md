# Task ID: 11

**Title:** Add pytest configuration

**Status:** done

**Dependencies:** None

**Priority:** low

**Description:** Add [tool.pytest.ini_options] to pyproject.toml with: testpaths = ['tests'], python_files = ['test_*.py'], python_functions = ['test_*'], addopts = '-q --tb=short'. Verify all 162 existing tests still pass with the new config.

**Details:**

Currently there is no pytest configuration in pyproject.toml. Tests are run with 'python -m pytest tests/ -q'. Adding formal pytest config enables running bare 'pytest' from the project root and sets consistent options. The pyproject.toml already exists (810 bytes) with package metadata.

**Test Strategy:**

Run 'python -m pytest' from the telegram-qbt directory and confirm all 162 tests pass with the new configuration. Verify 'pytest' (without python -m) also works.
