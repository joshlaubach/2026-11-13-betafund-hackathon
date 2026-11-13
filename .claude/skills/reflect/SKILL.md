---
name: reflect
description: End-of-session reflection. Lists what went wrong or took too long this session, proposes the smallest edit to a skill, agent, or CLAUDE.md that would have prevented each one, and waits for the user's OK before applying anything. Use at the end of every session.
---

# Reflect

Run at the end of a session, after updating `docs/progress.md`, `docs/decisions.md`, and `docs/known-issues.md`.

1. **List what went wrong or took too long.** Cover failed commands, rework, worker output sent back, wrong assumptions, and slow loops. For each item give the evidence from this session: the command, the error, the round count, or the file. Skip anything that went fine.
2. **Propose one fix per item:** the smallest edit to a skill, an agent, or `CLAUDE.md` that would have prevented it. Show the exact target file and the text to add or change, as a before-and-after or a short diff. If no edit would have helped, say so and propose nothing.
3. **Wait.** Present the list and the proposed edits, then stop. Apply only the edits the user approves, exactly as approved. Do not apply anything without an explicit OK.
