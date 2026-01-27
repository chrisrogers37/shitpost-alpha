---
description: "Show database status and recent activity"
---

Run these commands to get database status:

```bash
# Show overall database statistics
python -m shitvault show-stats

# Show latest posts
python -m shitvault show-latest --limit 10
```

After running, summarize:

1. **Database Health**:
   - Total posts in database
   - Analyzed vs unanalyzed count
   - Bypassed posts count

2. **Recent Activity**:
   - Latest post timestamp
   - Recent post summaries
   - Analysis status

3. **Recommendations**:
   - Are there many unanalyzed posts?
   - Is the harvester running properly?
   - Any unusual patterns?
