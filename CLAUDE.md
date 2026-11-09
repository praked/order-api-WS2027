@AGENTS.md

## Claude Code

- Use plan mode for any change that touches more than one route.
- For features in specs/: delegate to the `planner`, then `implementer`, then `reviewer` subagents (.claude/agents/). Show me PLAN.md before implementing.
- Skills live in .agents/skills (linked as .claude/skills): `/add-endpoint`, `/bump-dependency`.
