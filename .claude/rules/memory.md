# Memory

Project memory lives in `C:\Users\DARSHAN\.claude\projects\P--NASA-SpaceApps\memory\`, indexed by `MEMORY.md`.

## Recall — Before Responding

Check memory when the message involves past decisions, preferences, the MISSIONFORGE specs, the implementation plan, or prior work. Skip when the topic is already fully in context.

To recall: read the MEMORY.md index, scan descriptions for relevance, load matching memory files. Don't load everything — be selective. Memories reflect what was true when written: verify file paths, functions and status against the repo before relying on them.

## Remember — After Responding

Run this decision tree after every substantive response:

1. **Does this exchange contain a user directive, reasoning conclusion, or durable fact?** If no to all, stop.
2. **Does an overlapping memory exist?** If yes, update it. If it contradicts, replace it. If no overlap, create a new file.
3. **Is it worth storing?** Multi-source synthesis or user-specific context that can't be recovered by search? Yes, save. Single-query public fact? Skip.

## Memory File Format

Save each memory as its own file in the memory directory:

```markdown
---
name: descriptive-name
description: one-line summary for relevance matching
metadata:
  type: user | feedback | project | reference
---

Content here. For feedback/project types, include:
**Why:** reason behind it
**How to apply:** when this matters
Link related memories with [[their-name]].
```

Convert relative dates to absolute dates (e.g. 2026-11-13).

## What NOT to Save

- Code patterns derivable from reading the codebase
- Git history (use git log)
- Debugging solutions (the fix is in the code)
- Ephemeral task details for the current session only
- Content already written verbatim in `src-files/` or `docs/` — point to it instead
- Secrets, API keys, tokens, or personal contact details

## Index Maintenance

After creating or updating a memory file, add or update its entry in MEMORY.md under the right type heading. Keep the index under 200 lines, one line per entry.
