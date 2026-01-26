---
description: "Check recent logs for errors or issues"
---

Run these commands to check logs:

```bash
# Show recent logs from each service
echo "=== Orchestrator Logs ==="
tail -30 logs/orchestrator.log 2>/dev/null || echo "No orchestrator log found"

echo ""
echo "=== Harvester Logs ==="
tail -30 logs/harvester.log 2>/dev/null || echo "No harvester log found"

echo ""
echo "=== S3 Processor Logs ==="
tail -30 logs/s3_processor.log 2>/dev/null || echo "No s3_processor log found"

echo ""
echo "=== Analyzer Logs ==="
tail -30 logs/analyzer.log 2>/dev/null || echo "No analyzer log found"
```

After reviewing logs, summarize:

1. **Recent Errors**:
   - Any ERROR or CRITICAL level messages
   - Timestamps of issues
   - Affected services

2. **Warnings**:
   - Any WARNING level messages
   - Potential issues to address

3. **Activity Status**:
   - When was the last successful run?
   - Are services running as expected?
   - Any unusual patterns?

4. **Recommendations**:
   - Should any services be restarted?
   - Are there configuration issues?
   - Follow-up actions needed?
