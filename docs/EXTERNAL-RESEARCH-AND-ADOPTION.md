# External Research and Adoption Register

Research register date: 2026-10-20
Scope: candidate systems and design patterns named in the supplied JARVIS research ledger and prior research notes.
Evidence policy: a link or summary is not a code audit. Do not copy runtime code without inspecting the exact revision, license, dependency tree, security posture, and tests. This register distinguishes a design takeaway from a verified V3 implementation.

## Candidate register

| Project / source | Reference | Potential value for JARVIS | Adoption decision | V3 status |
|---|---|---|---|---|
| Microsoft UFO | https://github.com/microsoft/UFO | Windows desktop-agent architecture and UIA-oriented interaction | Study architecture; adapt only behind Windows capability adapter | UIA contract exists; live adapter not verified |
| Browser Use | https://github.com/browser-use/browser-use | Browser-specific task interaction | Keep as optional future adapter; dependency and browser lifecycle review required | Not integrated |
| MineDojo Voyager | https://github.com/MineDojo/Voyager | Lifelong skill library with feedback and self-verification | Adopt the concept of versioned, evaluated skills, not game-specific runtime | Text-only skill proposals exist; approval required |
| NvlFR/self-evolving-agent | https://github.com/NvlFR/self-evolving-agent | Persistent self-model and evolution history | Use auditable change history; reject unrestricted recursive self-editing | Episode and repair ledgers exist; no self-modifying code |
| Johin2/self-heal | https://github.com/Johin2/self-heal | Failure-aware repair workflow | Preserve failed-attempt history and verify outcomes | Repair proposal ledger exists; executor/rollback not implemented |
| Bravim-Ketan-Purohit/self-healing-agent | https://github.com/Bravim-Ketan-Purohit/self-healing-agent | Traceback-driven repair and isolated execution concepts | Use isolated test-workspace concept only after sandbox claims are validated | No generated code execution |
| Mem0 | https://github.com/mem0ai/mem0 | Persistent memory design | Keep memory local and provenance-aware; evaluate dependency only if needed | SQLite explicit memory implementation exists; Mem0 not integrated |
| Letta | https://github.com/letta-ai/letta | Stateful agents and memory lifecycle | Study memory boundary and tool architecture | Not integrated |
| LiteLLM | https://github.com/BerriAI/litellm | Multi-provider interface and routing | Preserve provider contract; no silent cloud fallback | Small local provider contract exists; LiteLLM not integrated |
| Pipecat | https://github.com/pipecat-ai/pipecat | Real-time voice pipeline | Keep voice optional and separate from text core | Not integrated |
| whisper.cpp | https://github.com/ggml-org/whisper.cpp | Local speech recognition | Candidate for offline STT after Windows/Hinglish benchmarks | Not integrated |
| Ollama | https://github.com/ollama/ollama | Local model serving | Existing provider adapter targets local Ollama | Implemented adapter; target hardware performance not benchmarked here |
| Open Interpreter | https://github.com/OpenInterpreter/open-interpreter | Local computer-use/coding concepts | Do not grant unrestricted shell execution; use typed tools and explicit permissions | Not integrated |
| E2B | https://github.com/e2b-dev/E2B | Isolated code execution | Evaluate only if local sandbox isolation is insufficient and network/dependency review passes | No sandbox claim; no arbitrary generated code execution |
| Firecrawl | https://github.com/firecrawl/firecrawl | Web extraction/crawling | Not required for bounded first-party API search; evaluate license, privacy and cost before adoption | Not integrated |
| Composio | https://github.com/ComposioHQ/composio | Third-party tool integrations | Requires connector scopes, egress policy and approval design | Not integrated |
| n8n | https://github.com/n8n-io/n8n | Workflow automation | User's research ledger marks it rejected; do not reintroduce without explicit evidence-based review | Rejected in the supplied ledger; not integrated |
| OpenGCUA | https://github.com/OpenGCUA/OpenGCUA | GUI automation patterns | Study only with threat-model and platform testing | Not integrated |
| A-MEM | https://github.com/agiresearch/A-mem | Structured/associative memory ideas | Compare against simple SQLite memory with retrieval-quality tests | Not integrated |
| Moshi | https://github.com/kyutai-labs/moshi | Full-duplex speech interaction | Hardware/latency study needed; do not make it a text-core dependency | Not integrated |
| DeepEval | https://github.com/confident-ai/deepeval | LLM evaluation methods | Prefer deterministic stdlib golden tests first; review dependency before adoption | Not integrated |
| Reverse Engineer Anything (REA) | https://github.com/elder-plinius/REA | Reverse-engineering workflow inspiration | Apply to authorized code only; report observed vs inferred vs unknown | No dedicated reverse-engineering module |
| ClawHavoc / malicious skill research | https://github.com/ | Malicious skill and plugin supply-chain risk | Treat downloaded skills as untrusted; never auto-run; pin source and review permissions | Skill proposals are text-only; broader supply-chain scanner not implemented |
| GitHub public repository API | https://docs.github.com/en/rest/search/search#search-repositories | Discover public repositories with provenance | Use fixed public API, bounded results and source URLs | Implemented in `jarvis/research.py`; metadata search only |
| Wikipedia OpenSearch API | https://www.mediawiki.org/wiki/API:Opensearch | Quick discovery of encyclopedia entries | Treat snippets as leads, not verified facts | Implemented in `jarvis/research.py`; search results only |

## Adopted architectural rules

1. **Typed tool boundary:** model output is not an executable command. The deterministic planner classifies only known capabilities.
2. **Permission gate:** app launches are allow-listed and require per-request confirmation. Unknown/destructive/external actions remain denied unless a dedicated policy explicitly permits them.
3. **Evidence-labelled learning:** store attempted/accepted/failed/response-generated outcomes distinctly. Do not infer that the user's larger goal succeeded.
4. **Repair is staged, not self-authorizing:** failure can create a proposal; test receipts and review status are recorded. No live-code patch is auto-applied.
5. **Research provenance:** retain query, source title, HTTPS URL, bounded snippet, source type, local save timestamp and limitations. Retrieved text is untrusted data.
6. **Bounded egress:** explicit Wikipedia/GitHub research uses fixed API hosts, bounded query/response sizes, timeouts and no redirects. Ordinary chat does not silently send every message to the web.
7. **Local-first and stdlib-first:** avoid new runtime dependencies until an evaluated requirement justifies one.
8. **No consciousness claims:** self-monitoring means operational metrics, outcomes, and failure analysis only.

## Open adoption work

- Import the original research ledger item-by-item with exact source URLs and source-reported statuses; the compact index is not the original full ledger.
- Inspect exact revisions, licenses, dependency trees, recent maintenance and security advisories for every candidate before code reuse.
- Add a real Windows UIA adapter and run UIA/coordinate regression tests on the target Windows machine.
- Build isolated patch staging, focused/full test execution, diff review, backup and rollback before any self-healing executor is considered.
- Add scheduled research only with explicit settings, deduplication, rate limits, source trust, license/security checks and visible status.
- Add evaluation fixtures for Hinglish intent recognition, task postconditions, prompt injection, source trust and false-success claims.

## Status vocabulary

- **VERIFIED IN V3:** code inspected and tests passed; platform-specific capabilities additionally need end-to-end evidence.
- **IMPLEMENTED, PLATFORM UNVERIFIED:** code and unit tests exist, but no real target-machine receipt.
- **RESEARCH ONLY:** design/reference noted; no runtime integration.
- **REJECTED:** intentionally not adopted unless the decision is revisited with new evidence.
- **QUEUED:** not implemented yet.
