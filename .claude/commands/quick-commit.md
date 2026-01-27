---
description: "Stage all changes and commit with a descriptive message"
---

Here are the current changes:
```
${{ git status --short }}
```

Here is the diff:
```
${{ git diff --stat }}
```

Recent commit messages for style reference:
```
${{ git log --oneline -5 }}
```

Follow these steps in order:

1. Review the changes above
2. Run quick verification:
   - `pytest -v --tb=short` (run tests)
   - `ruff check .` (check linting)
3. Stage all changes with `git add .`
4. Create a commit with a clear, descriptive message following conventional commits format
5. If there are any issues at any step, stop and report them

**Note**: This does NOT push to remote. Use `/commit-push-pr` for full PR workflow.
