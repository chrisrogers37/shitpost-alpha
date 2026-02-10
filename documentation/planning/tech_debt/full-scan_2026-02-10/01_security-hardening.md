# Plan 01: Security Hardening

**Status**: 🔧 IN PROGRESS
**Started**: 2026-02-10

**PR Title**: `fix: patch SQL injection, HTML injection, bare excepts, and credential logging`
**Risk Level**: Medium (changes touch notification dispatch and error handling paths)
**Effort**: 1-2 days
**Findings Addressed**: #1, #2, #7, #8

---

## Finding #1: SQL Injection in `update_subscription()`

### Location

`notifications/db.py:159-196`

### Problem

The `update_subscription()` function builds SQL dynamically from `**kwargs` keys without validating that the keys are actual column names. An attacker who controls the kwargs (e.g., through a crafted Telegram callback) could inject arbitrary SQL column expressions.

### Current Code (VULNERABLE)

```python
# notifications/db.py:174-190
def update_subscription(chat_id: str, **kwargs: Any) -> bool:
    try:
        if not kwargs:
            return True

        set_clauses = []
        params: Dict[str, Any] = {"chat_id": str(chat_id)}

        for key, value in kwargs.items():
            if key == "alert_preferences" and isinstance(value, dict):
                value = json.dumps(value)
            set_clauses.append(f"{key} = :{key}")  # <-- INJECTION POINT
            params[key] = value

        set_clauses.append("updated_at = NOW()")

        with get_session() as session:
            query = text(f"""
                UPDATE telegram_subscriptions
                SET {", ".join(set_clauses)}
                WHERE chat_id = :chat_id
            """)
            session.execute(query, params)
```

The line `set_clauses.append(f"{key} = :{key}")` interpolates the key directly into SQL. If `key` contains something like `is_active = true, consecutive_errors`, the SQL structure is corrupted.

### Fix

Add a whitelist of allowed column names and reject any key not in the whitelist.

```python
# notifications/db.py — FIXED version

# Add this constant near the top of the file (after imports):
_UPDATABLE_COLUMNS = frozenset({
    "chat_type",
    "username",
    "first_name",
    "last_name",
    "title",
    "is_active",
    "subscribed_at",
    "unsubscribed_at",
    "alert_preferences",
    "last_alert_at",
    "alerts_sent_count",
    "consecutive_errors",
    "last_error",
    "last_interaction_at",
})


def update_subscription(chat_id: str, **kwargs: Any) -> bool:
    try:
        if not kwargs:
            return True

        set_clauses = []
        params: Dict[str, Any] = {"chat_id": str(chat_id)}

        for key, value in kwargs.items():
            if key not in _UPDATABLE_COLUMNS:
                raise ValueError(f"Invalid column name for subscription update: {key}")
            if key == "alert_preferences" and isinstance(value, dict):
                value = json.dumps(value)
            set_clauses.append(f"{key} = :{key}")
            params[key] = value

        if not set_clauses:
            return True

        set_clauses.append("updated_at = NOW()")

        with get_session() as session:
            query = text(f"""
                UPDATE telegram_subscriptions
                SET {", ".join(set_clauses)}
                WHERE chat_id = :chat_id
            """)
            session.execute(query, params)
        logger.info(f"Updated Telegram subscription for chat_id {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating subscription for chat_id {chat_id}: {e}")
        return False
```

### Test

Add a test that verifies invalid column names are rejected:

```python
# shit_tests/notifications/test_db.py

def test_update_subscription_rejects_invalid_columns(mock_session):
    """Verify SQL injection via kwargs is blocked with ValueError."""
    from notifications.db import update_subscription, _UPDATABLE_COLUMNS

    # Invalid column names should cause update_subscription to return False
    # (ValueError is raised internally and caught by the except block)
    result = update_subscription("12345", **{"is_active = true; DROP TABLE": "x"})
    assert result is False

    # Valid columns should still be in the whitelist
    assert "is_active" in _UPDATABLE_COLUMNS
    assert "chat_type" in _UPDATABLE_COLUMNS
```

---

## Finding #2: HTML Injection in Email Alerts

### Location

`notifications/dispatcher.py:378-434` — `format_alert_message_html()`

### Problem

User-generated content is interpolated directly into an HTML template without escaping at **4 injection points**. If a post contains `<script>` tags or malicious HTML, it will be rendered in the email.

### Current Code (VULNERABLE)

```python
# notifications/dispatcher.py — 4 unescaped injection points:
#   Line 407: {sentiment}                    # <-- UNESCAPED (from alert data)
#   Line 410: {assets_str}                   # <-- UNESCAPED (from DB/LLM)
#   Line 416: {alert.get("text", "")[:300]}  # <-- UNESCAPED (user post content)
#   Line 425: {thesis[:500]}                 # <-- UNESCAPED (LLM output)
```

### Fix

Import `html.escape` and apply it to all user-generated values before interpolation.

```python
# notifications/dispatcher.py — FIXED version

import html  # Add to imports at top of file

def format_alert_message_html(alert: Dict[str, Any]) -> str:
    confidence_pct = f"{alert.get('confidence', 0):.0%}"
    assets_str = html.escape(", ".join(alert.get("assets", [])[:5]))
    sentiment = html.escape(alert.get("sentiment", "neutral").upper())
    thesis = html.escape(alert.get("thesis", "No thesis provided."))
    post_text = html.escape(alert.get("text", "")[:300])

    # ... rest of the function uses these escaped values in the template
    # Replace:
    #   {alert.get("text", "")[:300]}  →  {post_text}
    #   {thesis[:500]}                 →  {thesis[:500]}
    #   {sentiment}                    →  {sentiment}  (already escaped above)
    #   {assets_str}                   →  {assets_str}  (already escaped above)
```

**Key change**: Wrap ALL user-derived values with `html.escape()` before they enter the f-string template. The variables `sentiment`, `confidence_pct`, `assets_str`, `post_text`, and `thesis` should all be escaped.

### Test

```python
# shit_tests/notifications/test_dispatcher.py

def test_html_alert_escapes_script_tags():
    """Verify HTML injection is prevented in email alerts."""
    from notifications.dispatcher import format_alert_message_html

    malicious_alert = {
        "confidence": 0.85,
        "assets": ["<b>FAKE</b>", "AAPL"],
        "sentiment": "bullish",
        "thesis": '<script>alert("xss")</script>',
        "text": '<img src=x onerror="steal()">',
    }

    result = format_alert_message_html(malicious_alert)

    # All 4 injection points must be escaped
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert 'onerror="steal()"' not in result
    assert "&lt;img" in result
    assert "<b>FAKE</b>" not in result
    assert "&lt;b&gt;" in result
```

---

## Finding #7: Bare `except:` Clauses

### Locations

| File | Line | Context |
|------|------|---------|
| `shit/llm/llm_client.py` | 207 | `_extract_json()` — catches everything including `KeyboardInterrupt` |
| `shit/s3/s3_models.py` | 77 | `S3KeyInfo.date_path` property |
| `shit/s3/s3_models.py` | 88 | `S3KeyInfo.post_id` property |
| `shit/market_data/cli.py` | 99 | SQLite fallback in `update_all_prices()` |

### Problem

Bare `except:` catches `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit` — all of which should propagate. It also silently swallows errors that should be logged.

### Fix — Each Location

**`shit/llm/llm_client.py:195-210`**

```python
# BEFORE (line 207)
        except:
            pass

# AFTER
        except (json.JSONDecodeError, ValueError):
            pass
```

**`shit/s3/s3_models.py:70-79`**

```python
# BEFORE (line 77)
        except:
            pass

# AFTER
        except (IndexError, ValueError):
            pass
```

**`shit/s3/s3_models.py:81-90`**

```python
# BEFORE (line 88)
        except:
            pass

# AFTER
        except (IndexError, ValueError):
            pass
```

**`shit/market_data/cli.py:96-106`**

```python
# BEFORE (line 99)
            except:
                # Fallback for SQLite

# AFTER
            except Exception:
                # Fallback for SQLite (jsonb_array_elements_text not supported)
```

Note: `except Exception:` (with `Exception`) is acceptable here because we're catching database driver errors that may vary. The key difference is it won't catch `SystemExit` or `KeyboardInterrupt`.

### Test

Run `ruff check . --select E722` to verify no bare `except:` remains.

```bash
ruff check . --select E722
# Expected: no violations
```

---

## Finding #8: Database URL Printed to Stdout

### Location

`shitty_ui/data.py:65,88`

### Problem

The database connection URL (which may contain credentials) is printed to stdout at module import time:

```python
# shitty_ui/data.py:65
print(f"🔍 Dashboard using settings DATABASE_URL: {DATABASE_URL[:50]}...")

# shitty_ui/data.py:88
print(f"🔍 Using PostgreSQL sync URL: {sync_url[:50]}...")
```

Even though these are truncated to 50 characters, that's enough to expose `postgresql://username:password@host...`.

### Fix

Replace `print()` with `logger.debug()` and mask the URL:

```python
# Add at top of file (replace the print statements):
import logging

logger = logging.getLogger(__name__)

# Replace line 65:
logger.debug("Dashboard using settings-based DATABASE_URL")

# Replace line 88:
logger.debug("Using PostgreSQL sync URL")

# Replace line 128 (in execute_query error handler):
# print(f"❌ Database query error: {e}")
logger.error(f"Database query error: {e}")

# Replace line 129 (in execute_query error handler):
# print(f"🔍 DATABASE_URL: {DATABASE_URL[:50]}...")
logger.debug("Query failed against configured database")
```

**Rule**: NEVER log connection strings, even partially. Log only the fact that a connection was configured, not the URL.

### Test

```bash
# Verify no print statements remain that contain DATABASE_URL
grep -n "print.*DATABASE_URL" shitty_ui/data.py
# Expected: no output
```

---

## Verification Checklist

After implementing all fixes in this plan:

- [ ] `ruff check . --select E722` returns zero bare except violations
- [ ] `grep -rn "except:" --include="*.py" shit/ shitty_ui/ notifications/` returns zero results (excluding comments)
- [ ] `grep -n "print.*DATABASE_URL" shitty_ui/data.py` returns zero results
- [ ] `python -c "from notifications.db import _UPDATABLE_COLUMNS; print(len(_UPDATABLE_COLUMNS))"` prints 14
- [ ] All existing tests pass: `pytest shit_tests/ -v`
- [ ] New tests for SQL injection and HTML injection pass
- [ ] No credentials appear in log output when dashboard starts

---

## What NOT To Do

1. **Do NOT replace all raw SQL in `notifications/db.py` with ORM queries in this PR.** That's a separate concern (Plan 03). This PR only adds the column whitelist.
2. **Do NOT add blanket `except Exception as e: logger.error(e)` everywhere.** Each `except` should catch the specific exception types that can actually occur.
3. **Do NOT remove the error handlers entirely.** The goal is to make them safer, not to remove error handling.
4. **Do NOT change the function signatures.** `update_subscription()` should still accept `**kwargs` — we're just validating the keys.
