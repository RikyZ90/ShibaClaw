# Project discovery and maintainer actions

Last verified: **2026-10-24**. This is a maintainer plan, not a record of submissions or changed GitHub settings. Repository metadata, contribution rules and directory contents can change; check them again before acting.

[README](../README.md) · [Contributing](../CONTRIBUTING.md) · [Contribution ideas](CONTRIBUTING_IDEAS.md) · [Comparison](COMPARISON.md)

## GitHub settings to update manually

The live [repository metadata](https://api.github.com/repos/RikyZ90/ShibaClaw) currently describes ShibaClaw as:

> 🐕 Self-hosted security-first AI agent · 28 providers · 11 chat channels · WebUI · 3-level memory · task-schedule · automation · skills · MCP

The homepage currently points to [DeepWiki](https://deepwiki.com/RikyZ90/ShibaClaw). These settings are independent of the README and `pyproject.toml`; editing this document does not apply them.

### Description

Use this exact description (120 characters):

```text
Self-hosted personal AI agent with a WebUI, memory, tools, MCP, sub-agents and automations. Connect local or cloud LLMs.
```

It describes the complete application, includes terms people can search for, and avoids provider/channel counts that require synchronization. Security controls remain prominent in the README and [security policy](../SECURITY.md), where their scope can be explained.

### Homepage

**Recommended now:** [https://github.com/RikyZ90/ShibaClaw#readme](https://github.com/RikyZ90/ShibaClaw#readme).

Keep DeepWiki as an additional code-exploration link. The maintained README is currently the clearest place to see the demo, installation paths, security information and documentation together.

The repository API reports `has_pages: true`, but the conventional [Pages URL](https://rikyz90.github.io/ShibaClaw/) returned **HTTP 404** during this audit. The checked default branch has no project landing-page entry point, `CNAME`, static-site configuration or Pages workflow; the live branch list contains only `main`. The public Pages API also returned 404, so the configured Pages source or a possible custom hostname could not be established. A feature flag alone does not establish that a usable site exists.

**Landing page:** the static page in [`site/`](../site/README.md) is published with the existing product demos, installation links, documentation, security and contribution links. The build copies an explicit set of public assets into `dist/pages/`; the GitHub Pages workflow checks the page and deploys only from `main`. Demo animations load on request, and static previews keep the initial page small.

Follow the [site maintenance guide](../site/README.md) to preview and maintain the published page at [rikyz90.github.io/ShibaClaw](https://rikyz90.github.io/ShibaClaw/). Its first GitHub Actions deployment succeeded, the page and assets returned HTTP 200, and the repository Homepage now points to it. A custom domain can wait until there is an owner and renewal plan.

### Topics: exactly 20

Replace the current topics with this set:

```text
ai-agent
ai-agents
self-hosted
personal-ai-assistant
ai-assistant
llm-agents
agent-framework
multi-agent
local-llm
ollama
openai-compatible
mcp
model-context-protocol
webui
workflow-automation
ai-automation
docker
rag
prompt-injection
security
```

The set is grounded in the repository:

| Topics | Evidence and intended meaning |
| --- | --- |
| `ai-agent`, `ai-agents`, `personal-ai-assistant`, `ai-assistant`, `llm-agents`, `agent-framework` | The runnable personal assistant, agent runtime and extension points described in the [README](../README.md) and [plugin guide](PLUGINS_DEVELOPMENT_GUIDE.md). The main positioning should still describe an application, rather than imply users must build one from an SDK. |
| `self-hosted`, `docker` | Local installation and the checked-in [Docker Compose configuration](../docker-compose.yml). |
| `multi-agent` | Delegated agents and [project verification](PROJECT_VERIFICATION.md). |
| `local-llm`, `ollama`, `openai-compatible` | Local provider entries in the [provider registry](../shibaclaw/thinkers/registry.py) and the [custom OpenAI-compatible provider](../shibaclaw/thinkers/custom_provider.py). Compatibility describes connecting to endpoints, not an assertion that ShibaClaw implements every OpenAI API. |
| `mcp`, `model-context-protocol` | The [MCP client tool integration](../shibaclaw/agent/tools/mcp.py). ShibaClaw should be submitted to MCP **client** collections, not presented as an MCP server. |
| `webui` | The built-in [WebUI](../shibaclaw/webui/server.py). |
| `workflow-automation`, `ai-automation` | The documented schedules, skills and [automation routes](../shibaclaw/webui/routers/automation.py). These terms do not imply a visual workflow designer. |
| `rag` | Optional semantic knowledge retrieval documented in the README and packaged through the [RAG extras](../pyproject.toml). |
| `prompt-injection`, `security` | Documented defensive controls and their [security policy](../SECURITY.md); these topics are not a security certification or a guarantee that attacks are prevented. |

The live topics include broader labels such as `local`, `llm`, `open-source`, `openai` and `python`. The replacements describe user intent and supported protocols more precisely. `matrix` remains a supported channel, but is less central to the project's overall discovery than personal-assistant or local-model intent.

### Social proof without stale adoption claims

Keep distribution sources separate:

- The [Pepy badge](https://static.pepy.tech/personalized-badge/shibaclaw?period=total&units=ABBREVIATION&left_color=YELLOWGREEN&right_color=ORANGE&left_text=downloads) returned a rounded **60k** total-download label during this audit. Use the dynamic badge, not a permanent “60,000+ users” claim.
- The [Docker pulls badge](https://img.shields.io/docker/pulls/rikyz90/shibaclaw.svg?style=flat-square) returned **19k**; the [Docker Hub repository API](https://hub.docker.com/v2/repositories/rikyz90/shibaclaw/) returned `pull_count: 19382`. These are pull events, not unique installations or people.
- [PyPI](https://pypi.org/project/shibaclaw/) supplies the package version. A CI badge represents the selected workflow/branch status, not a general reliability guarantee.

Do not add these counts together or infer active users from them. Provider/channel badges need a defined, maintained count source before being useful. No such badge generator was added.

## External discovery shortlist

The five targets below were checked through their current default-branch documentation and [GitHub repository metadata](https://docs.github.com/en/rest/repos/repos#get-a-repository). All five were unarchived and allowed public pull requests on the verification date. Their published READMEs had no case-insensitive `ShibaClaw` or `RikyZ90/ShibaClaw` match; separate issue and PR searches for `ShibaClaw` returned no matches. This is a snapshot, not a guarantee against duplicates under other names or unindexed changes.

Priority reflects fit and the effort required to make a credible submission, not promised audience reach. Read the current rules, confirm no duplicate, and make one focused submission only when the maintainer chooses to proceed. No external issue, PR, form submission or message was sent.

### 1. e2b-dev/awesome-ai-agents — High

- **Repository:** [e2b-dev/awesome-ai-agents](https://github.com/e2b-dev/awesome-ai-agents).
- **Relevance and placement:** strong fit for its **Open-source projects** section as a general-purpose personal agent; place ShibaClaw alphabetically, following the existing category/description/links format.
- **Current submission route:** the [README contribution instructions](https://github.com/e2b-dev/awesome-ai-agents#have-anything-to-add) invite a PR or their linked product form. No standalone `CONTRIBUTING.md` was present at the root. The README distinguishes assistants/agents from the separate SDK list.
- **Acceptance caveat:** demonstrate the runnable assistant, rather than pitching an SDK or implying an E2B integration. A PR route exists; inclusion remains a curator decision.
- **Neutral description:** “Self-hosted personal AI agent with a WebUI, memory, MCP tools, sub-agents and scheduled automations, supporting local and cloud models.”

### 2. kyrolabs/awesome-agents — High

- **Repository:** [kyrolabs/awesome-agents](https://github.com/kyrolabs/awesome-agents).
- **Relevance and placement:** strong fit for **Conversational / General Agents**. Add at the bottom of that section, following the list's explicit bottom-placement rule; do not place it at the top for visibility.
- **Current submission route:** [CONTRIBUTING.md](https://github.com/kyrolabs/awesome-agents/blob/main/CONTRIBUTING.md) requires a **PR, not an issue**, and an open-source, maintained, English-documented project with demonstrated traction and added value.
- **Acceptance caveat:** the rules explicitly reject brand-new repositories without history and permit automatic closure for wrong placement or unmet criteria. Link to existing releases, documentation and demo as evidence; do not substitute download events for users.
- **Neutral description:** “Personal AI agent combining a built-in WebUI, memory, tools, MCP connections and automations with local or cloud model providers.”

### 3. slavakurilyak/awesome-ai-agents — High

- **Repository:** [slavakurilyak/awesome-ai-agents](https://github.com/slavakurilyak/awesome-ai-agents).
- **Relevance and placement:** strong fit for the existing **AI Agents**, **Personal Assistants**, **Long-Term Memory** and **Local Inference** categories. Select only categories supported by the actual configured behavior; final categorization belongs to the curator.
- **Current submission route:** [CONTRIBUTING.md](https://github.com/slavakurilyak/awesome-ai-agents/blob/main/CONTRIBUTING.md) prefers the project-submission issue for founders; direct PRs are also welcome. The canonical dataset is now **`awesome-agents.json`**, not a README-only edit or the older YAML project list. Follow its targeted Go verification, validation, contribution-credit and README-generation steps for a direct PR.
- **Acceptance caveat:** a public qualifying repository and a substantive, non-automated default-branch commit within six months are required; no minimum star count or particular license is required. ShibaClaw has concrete recent feature work, for example [project verification on 2026-10-18](https://github.com/RikyZ90/ShibaClaw/commit/5f2223168ac1499eb84e3505aa2ab95bdf9d25b5). Recheck activity at submission time. Do not claim repository ownership alone proves maintainer identity.
- **Neutral description:** “Self-hosted AI assistant with persistent memory, a WebUI, MCP tool connections, delegated agents and operator-configured scheduled tasks.”

### 4. punkpeye/awesome-mcp-clients — Medium

- **Repository:** [punkpeye/awesome-mcp-clients](https://github.com/punkpeye/awesome-mcp-clients).
- **Relevance and placement:** strong protocol fit for **Clients**, alphabetically under **ShibaClaw**. Describe a self-hosted web/desktop agent that consumes MCP tools. The README already includes self-hosted agents, so this is not restricted to desktop chat applications.
- **Current submission route:** [CONTRIBUTING.md](https://github.com/punkpeye/awesome-mcp-clients/blob/main/CONTRIBUTING.md) welcomes README PRs with an accurate project link, concise description and alphabetical placement. Follow the current entry metadata style; its guideline heading says “Servers”, but the instructions themselves explicitly cover clients.
- **Acceptance caveat:** document the client behavior actually tested. Do not claim full protocol-feature parity, universal server compatibility, mobile-native applications or independently audited security. The repository was open to PRs, but its last recorded push was 2026-06-07; review latency is unknown.
- **Neutral description:** “Self-hosted AI agent with a WebUI and Windows desktop launcher that connects MCP servers to its tool system.”

### 5. ollama/ollama Community Integrations — Medium

- **Repository:** [ollama/ollama](https://github.com/ollama/ollama#community-integrations).
- **Relevance and placement:** strong local-model fit for **Community Integrations → Frameworks & Agents**; use one entry, rather than repeating the same project in several sections.
- **Current submission route:** the README explicitly invites a PR to add a project. [CONTRIBUTING.md](https://github.com/ollama/ollama/blob/main/CONTRIBUTING.md) distinguishes small documentation updates from non-trivial changes that need discussion first. Match the existing short link-and-description format.
- **Acceptance caveat:** first recheck the [Ollama setup guide](integrations/OLLAMA.md) against the supported ShibaClaw version and confirm a local model can answer and use the tools needed by the example. This audit inspected implementation/configuration, but did not launch an Ollama model. A community listing would not imply an official Ollama partnership, `ollama launch shibaclaw` support or that every model supports tool calling.
- **Neutral description:** “Self-hosted personal AI agent with a WebUI, memory, MCP tools and scheduled tasks, with support for local Ollama models.”

### Evaluated, but not an actionable submission draft

[awesome-selfhosted/awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) is relevant to a deployable self-hosted application, but its public PR route is closed; changes go through [awesome-selfhosted-data](https://github.com/awesome-selfhosted/awesome-selfhosted-data). The data repository's [contribution rules](https://github.com/awesome-selfhosted/awesome-selfhosted-data/blob/master/CONTRIBUTING.md) prohibit machine/LLM-generated entries and submissions and require a human-authored contribution. They also require a first release more than four months old, active maintenance and working installation instructions, and exclude software dependent on a specific cloud provider.

A maintainer interested in that directory should personally read its addition/PR templates and establish eligibility, including the first-release date and local-model installation path. **No entry text, YAML or submission body for that directory is prepared here.** Its release-age eligibility was not established in this audit. The likely category to evaluate is **Generative Artificial Intelligence (GenAI)**. Keep it out of the immediate five-target outreach queue.

## Potential satellite projects

Extract a component only when another real consumer needs it. A separate repository adds releases, compatibility, security review and support work; a link back is useful attribution, not a sufficient reason to split code.

| Candidate and code evidence | Independent problem and reuse | Complexity, decision and link back |
| --- | --- | --- |
| **Tool-message history repair** — [`tombstone_tool_result` and `enforce_schema_invariants`](../shibaclaw/agent/context_overflow_guard.py), with [existing tests](../tests/test_context_overflow_guard.py) | Preserve tool-call/result relationships when pruning histories, and replace large results with identifiable stubs. The pure dictionary-based helpers could help other Python agent loops without depending on the WebUI. | **Medium.** A genuinely reusable subset is plausible; retain it internally until a second consumer and provider-format fixtures exist. Keep ShibaClaw-specific pin markers and compaction policy internal. A future package could cite ShibaClaw as its originating integration and run shared regression fixtures here. This is history integrity, not Muzzle's prompt-injection boundary role. |
| **MCP registry normalization and cache adapter** — [`MCPRegistryProvider`](../shibaclaw/apps/registry/mcp_registry.py) and [registry tests](../tests/test_mcp_registry_bug.py) | Fetch/cache registry entries and normalize transport/package metadata for app catalogs. A small adapter could serve another MCP client catalog. | **Medium.** Potentially reusable after replacing ShibaClaw `AppDefinition`/path coupling and reviewing package-runtime assumptions, pagination and URL validation. The current code is not a standalone security filter or universal installer. Demonstrate use from ShibaClaw's marketplace and retain attribution if a second consumer justifies extraction. |
| **Process-backed agent task verification** — [`verification.py`](../shibaclaw/agent/verification.py), [guide](PROJECT_VERIFICATION.md) and [tests](../tests/test_project_verification.py) | Keep execution status separate from configured check results, with exit codes, bounded output, timeout and cancellation evidence. That evidence model is useful beyond one agent UI. | **High.** Keep the implementation internal for now: it depends on the exec guard, permission context, turn journal and task lifecycle. Start any future reuse discussion with the evidence schema and fixtures, not a new orchestration framework. ShibaClaw would be the reference consumer. |

Do not create another prompt-injection wrapper: [Muzzle](https://github.com/RikyZ90/Muzzle) already covers that extracted component. Do not extract subscription OAuth or the credential vault merely for discovery; the project already depends on `oauth-cli-kit`, while local account formats, keyring migration and revocation have a substantial compatibility/security burden. No independent token/context benchmark or performance claim was established here, so there is no benchmark satellite proposal.

## Contributor and profile follow-up

The live [label list](https://api.github.com/repos/RikyZ90/ShibaClaw/labels) already contains `documentation`, `good first issue` and `help wanted`. Use those for real, scoped work described in [Contribution ideas](CONTRIBUTING_IDEAS.md), with reproduction or acceptance criteria. The repository metadata reported zero open issues/PRs at verification time; this does not establish that there is no useful contribution work. Do not create empty activity or apply newcomer labels to security-sensitive work.

Suggested profile pins, if the maintainer wants this project family visible: **ShibaClaw first**, then **Muzzle** as the existing focused utility. Both repositories were verified publicly; current profile pin order was not audited. Leave other slots for maintained projects with their own useful purpose, rather than creating repositories to fill them.

High impact / low effort: apply the exact description/topics and useful homepage, keep dynamic distribution badges, and review one high-fit directory submission at a time. Medium effort: validate the local Ollama walkthrough and prepare a small Pages homepage if desired. Longer-term: extract a satellite only after a second consumer demonstrates a concrete reuse need.

## Scope and verification limits

This audit read source/documentation and live public metadata, fetched the two distribution badges, checked the conventional Pages URL, and checked the five directories' current rules and ShibaClaw-name matches. It did not run an installation, start local/cloud models, exercise every MCP server, inspect private Pages settings or profile pins, submit anything externally, change repository settings, or create satellite repositories. Directory acceptance, future review time and star growth cannot be promised.
