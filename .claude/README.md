# Claude Code Configuration

This directory contains configuration for optimal development with [Claude Code](https://claude.ai/code).

## 📁 Structure

```
.claude/
├── README.md                    # This file
├── settings.json                # Shared team settings (permissions, hooks)
├── settings.local.json          # Your local settings (gitignored)
├── QUICK_REFERENCE.md           # Quick reference for Claude
├── PROJECT_CONTEXT.md           # Context for remote sessions
└── skills/
    └── first-principles/
        └── SKILL.md             # First principles thinking
```

## 🎯 Key Files

### CLAUDE.md (Root)
Main project instructions for Claude Code. Contains:
- Safety rules (production operations require approval)
- Project overview and architecture
- Development workflow and best practices
- Code style conventions
- Testing guidelines
- Common patterns and troubleshooting

### settings.json
Shared permissions and hooks for the team:
- **Allowed commands**: Tests, linting, git operations, safe CLI commands
- **Denied commands**: Production operations, dangerous database operations
- **Hooks**: Auto-formatting with `ruff` after file edits

### QUICK_REFERENCE.md
Fast lookup for common tasks:
- Safety rules (what NOT to run)
- Architecture overview
- Key directories and files
- Common commands
- Database table reference
- Configuration flow

### PROJECT_CONTEXT.md
Context document for Claude web/phone sessions. Copy this into remote sessions to give Claude full project context.

## 🎨 Skills

### `/first-principles`
Applies first principles thinking to a problem:
- Breaks down to fundamental truths
- Questions every assumption
- Rebuilds solution from ground up

**Use when:**
- Conventional solutions feel wrong
- Costs seem fixed but you want to challenge that
- You hear "that's how it's always done"
- You need breakthrough vs. incremental improvement

## 🔧 Local Customization

Create `.claude/settings.local.json` (gitignored) for personal settings:

```json
{
  "permissions": {
    "allow": [
      "Bash(your_custom_command:*)"
    ]
  }
}
```

## 📚 Best Practices from Boris Cherny

This setup follows best practices from [Boris Cherny](https://twitter.com/bcherny) (creator of Claude Code):

1. **Shared CLAUDE.md**: Team-wide learnings (add mistakes Claude makes)
2. **Verification loops**: Tests + linting before every commit (2-3x quality)
3. **Skills**: Specialized workflows for common tasks
4. **PostToolUse hooks**: Auto-format Python files with ruff
5. **Pre-allowed commands**: Common safe commands (tests, git, etc.)
6. **Project context files**: Quick reference and remote session context

## 🔐 Safety Features

**Permissions system**:
- ✅ **Allow**: Tests, linting, git, safe CLI commands, dry runs
- ❌ **Deny**: Production operations, destructive commands

**Safety rules in CLAUDE.md**:
- All production operations require explicit user approval
- Clear distinction between safe (read-only) and dangerous commands
- Dry run mode available for testing

**Hooks**:
- Auto-formatting on file save (ruff)
- Prevents committing poorly formatted code

## 💡 Tips

1. **Start every session**: Check CLAUDE.md for safety rules
2. **Use skills**: Invoke with `/skill-name` for specialized workflows
3. **Update CLAUDE.md**: Add mistakes Claude makes so it learns
4. **Remote sessions**: Copy PROJECT_CONTEXT.md for full context
5. **Changelog**: Every PR must update CHANGELOG.md

## 🔗 Additional Resources

- [Claude Code Documentation](https://code.claude.com/docs)
- [Boris Cherny's Setup Guide](https://twitter.com/bcherny)
- [Project README](../README.md)
- [Main CLAUDE.md](../CLAUDE.md)
- [CHANGELOG.md](../CHANGELOG.md)
