---
description: "Review uncommitted changes and suggest improvements"
---

Here are the current uncommitted changes:
```
${{ git status --short }}
```

Here is the diff:
```
${{ git diff }}
```

Please review these changes and:

1. **Code Quality**:
   - Check for proper error handling
   - Verify type hints are present
   - Look for potential bugs or edge cases
   - Suggest improvements for readability

2. **Testing**:
   - Identify what new tests are needed
   - Check if existing tests need updates
   - Suggest test cases for edge conditions

3. **Documentation**:
   - Check if docstrings are present and clear
   - Verify CHANGELOG.md needs updating
   - Suggest README updates if needed

4. **Safety**:
   - Look for production operations without approval checks
   - Check for hardcoded credentials or secrets
   - Verify proper logging is in place

5. **Best Practices**:
   - Check if code follows project conventions
   - Verify proper use of centralized utilities (config, logging, etc.)
   - Look for violations of modular architecture

After the review, run:
- `pytest -v` to verify tests pass
- `ruff check .` to check for linting issues
