# 🐾 Contributing to ShibaClaw

First off — thanks for taking the time to contribute! Every paw print counts 🐕

## 🧭 Where to Start

- Check open [Issues](https://github.com/RikyZ90/ShibaClaw/issues) for bugs or feature requests
- Look for issues tagged `good first issue` if you're new to the project
- If no issue fits, pick a scoped task from [Contribution ideas](docs/CONTRIBUTING_IDEAS.md). These are starting points to discuss, not assigned work or a promised roadmap.
- Use the [documentation index](docs/README.md) and [integration guides](docs/integrations/README.md) to find the relevant area.
- Feel free to open a new issue before starting work on big changes

## 🔧 Development Setup

### Prerequisites
- Python 3.12+
- Docker & Docker Compose (recommended)
- Node.js and npm for WebUI development (CI uses Node.js 24)

### Local install
```bash
git clone https://github.com/RikyZ90/ShibaClaw.git
cd ShibaClaw
pip install -e ".[dev]"
```

If you are working on the Matrix integration, install the Matrix extra too:
```bash
pip install -e ".[dev,matrix]"
```

### Running Tests and Linters
We use `pytest` for testing and `ruff` for linting.
```bash
ruff check .
pytest tests/
```

For a scoped change, run the relevant test files first. WebUI sources are in `shibaclaw/webui/frontend/`; after changing them, run:

```bash
cd shibaclaw/webui
npm ci
npm test
npm run build
```

Include generated assets when the build changes them. For documentation-only changes, check local links, heading anchors, image paths and the rendered Markdown. Do not run installers or paid model requests just to check prose; state any setup you could not verify.

## 🌿 Branching & PRs
- Fork the repo and create your branch from `main`
- Branch naming: `feat/your-feature`, `fix/your-fix`, `docs/your-docs`
- Keep PRs focused — one thing at a time
- Write clear commit messages (e.g. `feat: add discord skill`, `fix: thinker timeout`)

## 🧩 Adding a New Skill
Skills live in `shibaclaw/skills/`. To add one:
- Create `shibaclaw/skills/<name>/SKILL.md`, following the [skill format](shibaclaw/skills/README.md) and an existing skill.
- Include YAML frontmatter with `name` and `description`, clear instructions, and any required binaries or environment variables.
- Skills are discovered from their directories by `SkillsLoader`; there is no separate registry to edit.

```bash
python shibaclaw/skills/skill-validator/validate_manifest.py shibaclaw/skills/<name>
pytest tests/test_skills.py
```

For a channel or speech plugin, start with the [plugin development guide](docs/PLUGINS_DEVELOPMENT_GUIDE.md) or [channel plugin guide](docs/CHANNEL_PLUGIN_GUIDE.md).


## 🛡️ Security
Found a vulnerability? Please do not open a public issue.
Refer to [SECURITY.md](SECURITY.md) for responsible disclosure guidelines. Remove API keys, OAuth codes, bearer tokens and personal data from all public reports.

## 📋 Code Style
- Follow existing code conventions
- Keep it readable — future you will thank present you
- Add docstrings to public methods

## 💙 Credits
This project was inspired by Nanobot by HKUDS.
Contributors are welcome to join the pack 🐾

## License
By contributing, you agree that your contributions will be licensed under the project's [Apache License 2.0](LICENSE).
