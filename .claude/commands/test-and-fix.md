---
description: "Run tests and fix any failures"
---

Follow these steps in order:

1. Run the test suite:
   ```bash
   pytest -v --tb=short
   ```

2. If tests fail:
   - Review the failure output carefully
   - Identify the root cause
   - Fix the issue in the code
   - Re-run tests to verify the fix

3. Check code quality:
   ```bash
   ruff check .
   ruff format .
   ```

4. If there are linting errors:
   - Review and fix each issue
   - Run ruff again to verify

5. Run full test suite with coverage:
   ```bash
   pytest --cov=shit --cov=shitvault --cov=shitpost_ai --cov-report=term-missing
   ```

6. Report results:
   - Number of tests passed/failed
   - Coverage percentage
   - Any remaining issues

If you encounter persistent failures, stop and ask for guidance.
