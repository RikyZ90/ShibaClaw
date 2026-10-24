# Contribution ideas

[Contributing guide](../CONTRIBUTING.md) · [Documentation](README.md) · [Project README](../README.md)

These are concrete areas to investigate, not open issues, commitments or claims that a feature is missing. Check existing [issues](https://github.com/RikyZ90/ShibaClaw/issues) and [pull requests](https://github.com/RikyZ90/ShibaClaw/pulls), then describe a bounded change and how you will verify it. A small reproducible report is useful even when you cannot submit a patch.

## Find a task

| Area | A useful scoped contribution | Start here | Evidence to include |
|---|---|---|---|
| Good first issue / documentation | Verify one integration guide on your OS and fix a misleading step, label or broken link | [Integration guides](integrations/README.md) | Installed version, OS, exact step and corrected wording; no secrets |
| Translations | Synchronize one README language with the verified English structure | [Translation checklist](#readme-translation-sync) | Native-language review, working anchors and unchanged commands |
| Integrations | Reproduce one MCP transport, authentication or plugin installation problem | [MCP tool](../shibaclaw/agent/tools/mcp.py), [plugin guide](PLUGINS_DEVELOPMENT_GUIDE.md), [MCP tests](../tests/test_mcp_lazy.py) | Minimal configuration, sanitized error and a mocked regression test |
| Provider support | Check a provider's model routing or error response against its official API documentation | [Registry](../shibaclaw/thinkers/registry.py), [provider tests](../tests/test_provider_config.py) | Official source, sanitized response fixture, test for the affected route |
| UI improvements | Reproduce a keyboard, focus, translation or narrow-screen problem in an existing flow | [Frontend](../shibaclaw/webui/frontend/), [browser fixtures](../shibaclaw/webui/tests/), [mobile tests](../shibaclaw/webui/tests/mobile-layout.test.mjs) | Steps, viewport and before/after capture; behavior test plus actual browser check |
| Testing | Add a missing edge case for callback failure, task reconnect, approval or persistence | [OAuth tests](../tests/test_webui_oauth.py), [task lifecycle tests](../tests/test_delegated_task_lifecycle.py), [automation tests](../tests/test_automation_store_sync.py) | A test that fails for a demonstrated defect, without a live account |
| Help wanted / platform checks | Verify documented Windows updates or Docker networking on a platform you use | [Windows guide](WINDOWS_INSTALLATION.md), [Ollama guide](integrations/OLLAMA.md), [Compose file](../docker-compose.yml) | Version, platform, exact path tested and observed result; preserve your existing data |

Do not add a provider merely to increase a count. Check whether its OpenAI-compatible endpoint already works through an existing route. Propose changes to authentication, persistence or public interfaces before broad implementation.

## Labels and issue reports

The repository has `good first issue`, `help wanted`, `documentation`, `bug` and `enhancement` labels. Maintainers can apply them to real reports:

- `good first issue`: a small confirmed task with a clear expected result and verification path.
- `help wanted`: a defined task needing expertise, platform access or independent reproduction.
- `documentation`: setup, wording, navigation or translation work.
- `bug` / `enhancement`: observed defects or requested behavior; describe provider, integration or UI scope in the title.

The issue chooser includes bug, feature, integration and documentation templates. The prompts are intentionally short; skip fields that do not apply. Report vulnerabilities according to the [security policy](../SECURITY.md), never with secrets in a public issue.

## README translation sync

The 2026-10-24 presentation update changes the English README. Broken navigation links in six translations were corrected to target their existing localized headings; their prose and installation examples remain intact. All seven translations need human-reviewed content synchronization:

| README | Status |
|---|---|
| [简体中文](../README.zh-CN.md) | Synchronization pending |
| [Español](../README.es.md) | Synchronization pending |
| [Português (BR)](../README.pt-BR.md) | Synchronization pending |
| [日本語](../README.ja.md) | Synchronization pending |
| [Deutsch](../README.de.md) | Synchronization pending |
| [Français](../README.fr.md) | Synchronization pending |
| [Italiano](../README.it.md) | Synchronization pending |

For each language:

1. Lead with positioning, dynamic badges, demo, six differentiators and Quick Start; move release notes later without discarding them.
2. Preserve working installation commands, release versions, image paths and language links. Keep translated heading anchors consistent with that file's navigation.
3. Link the comparison, documentation index and integration guides. Mark those linked pages as English where helpful.
4. Synchronize factual corrections: no unlimited/free Copilot promise or fixed free-model recommendations; no invented provider/channel totals or resource benchmarks. Explain subscription restrictions and the current Claude setup limitation from its guide. Replace the obsolete `print-token` login instructions with first-run admin registration, and use the positional `shibaclaw agent "message"` syntax.
5. Separate Markdown memory from optional FAISS RAG; describe actual scheduled/heartbeat jobs and `automation.json` persistence. Explain that the WebUI delegates to a gateway, started automatically with `--with-gateway`. Keep security defenses bounded rather than promising immunity to prompt injection, and avoid unverified TTS model/language counts.
6. Verify local links and rendered Markdown, then ask a fluent speaker to review the prose. Record the English revision synchronized in the PR.

The English files are the reference for this update. Existing translations may describe older behavior until synchronized; no automatic translation was substituted for review.
