# 🐾 Contributing to ShibaClaw

First off — thanks for taking the time to contribute! Every paw print counts 🐕

## 🧭 Where to Start

- Check open [Issues](https://github.com/RikyZ90/ShibaClaw/issues) for bugs or feature requests
- Look for issues tagged `good first issue` if you're new to the project
- Feel free to open a new issue before starting work on big changes

## 🔧 Development Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (recommended)

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

## 🌿 Branching & PRs
- Fork the repo and create your branch from `main`
- Branch naming: `feat/your-feature`, `fix/your-fix`, `docs/your-docs`
- Keep PRs focused — one thing at a time
- Write clear commit messages (e.g. `feat: add discord skill`, `fix: thinker timeout`)

## 🧩 Adding a New Skill
Skills live in `shibaclaw/skills/`. To add one:
- Create a new file in `shibaclaw/skills/`
- Implement the skill following the existing patterns
- Register it in the Skills Registry


## 🛡️ Security
Found a vulnerability? Please do not open a public issue.
Refer to `SECURITY.md` for responsible disclosure guidelines.

## 📋 Code Style
- Follow existing code conventions
- Keep it readable — future you will thank present you
- Add docstrings to public methods

## 💙 Credits
This project was inspired by Nanobot by HKUDS.
Contributors are welcome to join the pack 🐾

## License
By contributing, you agree that your contributions will be licensed under the MIT License.
