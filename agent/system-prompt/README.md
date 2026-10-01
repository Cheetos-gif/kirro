Versioned system prompt. `current.md` holds only the active version string. See CHANGELOG.md and AGENTS.md
("How to modify the system prompt"). `assemble.py` builds the runtime prompt (layers 1-3); layers 4-5 are connector
data and tool results, produced by code at run time.
