# REA-Inspired Source Inspection

Status: implemented as a bounded static-analysis helper; runtime behavior and Windows end-to-end integration are not implied.

## Why this exists

Reverse Engineer Anything (REA) follows a useful pattern: inspect artifacts, trace a specific feature through evidence, distinguish what was observed from what is inferred, then implement a compatible feature and test it. JARVIS v3 adopts that workflow discipline without importing REA's TypeScript/MCP/native-provider runtime into this standard-library-first Python app.

Official reference: https://github.com/morluto/rea (MIT license at the time reviewed). This file describes an adaptation of ideas and workflow, not copied REA source code.

## Implemented in V3

`jarvis/source_inspection.py` inventories Python source files beneath an explicitly supplied directory, hashes each readable file, parses syntax with Python's AST without importing or executing the inspected code, and records:
- class/function definitions and line ranges;
- import statements;
- statically named calls and their enclosing function;
- syntax/read/size-limit warnings;
- exact symbol definitions and statically named call sites for navigation.

The API is deterministic and has no network access, subprocess execution, code mutation, or third-party dependency. Symlinks and common generated/environment directories are excluded. File-count and file-size limits bound the work.

## Important limitations

Static call names are not a complete call graph. Aliases, reflection, dynamic dispatch, callbacks, decorators, runtime-generated code, and external side effects may be unresolved. A parse result is not proof that code works. JARVIS must cite the file/line evidence and label unresolved questions instead of guessing.

This helper is a foundation for JARVIS's own source self-awareness and investigation workflow. It does not itself reverse-engineer arbitrary binaries, inspect live browser sessions, or recreate an external app. REA's native providers have platform/tool requirements; those should remain optional integrations rather than silent dependencies of JARVIS startup.

## Validation

Run `python -m unittest discover -s tests`. The dedicated tests cover inventory and hashes, AST findings, symbol tracing, malformed source, invalid inputs, and bounded file size. CI must confirm the result before this feature is called verified.
