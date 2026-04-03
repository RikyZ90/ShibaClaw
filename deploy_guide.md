# 🐾 ShibaClaw: Easy Deploy Guide 🚀

Setting up ShibaClaw is as easy as fetching a ball! Choose your preferred method below to get started.

---

## 🐋 Option 1: Docker (The Easiest Way)

This method ensures you have all dependencies ready to go in a contained environment.

1. **Launch**: Run the following command in the project root:
   ```bash
   git clone https://github.com/RikyZ90/ShibaClaw.git .
   docker compose up --build        # start gateway + webUI
   ```
2. **Onboard**: Launch the interactive configuration wizard:
   ```bash
   docker exec -it shibaclaw-gateway shibaclaw onboard --wizard
   ```
   *Follow the prompts to add your LLM API keys.*
3. **Verify**: Check the logs to ensure your Shiba is hunting:
   ```bash
   docker logs -f shibaclaw-gateway
   ```

> **To update**: just run `docker compose pull && docker compose up -d` — no rebuild needed.

---

## 🐍 Option 2: Bare Metal (Without Docker)

Ideal for local development or lightweight environments.

1. **Install**: Choose your preferred method:

   **From PyPI (recommended):**
   ```bash
   pip install shibaclaw
   ```

   **From source (edge/develop):**
   ```bash
   git clone https://github.com/RikyZ90/ShibaClaw.git
   cd ShibaClaw
   pip install .
   ```
2. **Configure**: Start the onboarding wizard:
   ```bash
   shibaclaw onboard --wizard
   ```
3. **Run**: Choose your mode:
   - **Chat Mode**: Interact directly in the terminal.
     ```bash
     shibaclaw agent -m "Hello!"
     ```
   - **Gateway Mode**: Run the background service for channels (Telegram, etc.).
     ```bash
     shibaclaw gateway
     ```

---

## 🦴 Useful Commands

| Command | Action |
| :--- | :--- |
| `shibaclaw --version` | Check if you have the latest Shiba (v0.0.8). |
| `shibaclaw onboard` | Refresh settings without overwriting everything. |
| `shibaclaw onboard --wizard` | Forced step-by-step setup. |

**Happy hunting!** 🐕‍🦺🔥
