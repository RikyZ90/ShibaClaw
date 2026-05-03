# 🐾 ShibaClaw: Easy Deploy Guide 🚀

Setting up ShibaClaw is as easy as fetching a ball! Choose your preferred method below to get started.

---

### 🐋 Option 1: Docker (Recommended)

This method ensures you have all dependencies ready to go in a contained environment using the pre-built image. ShibaClaw uses a **distributed architecture** to keep memory usage low:
- **Gateway (Brain)**: ~256MB RAM minimum.
- **WebUI (Proxy)**: ~128MB RAM minimum.

The image is published automatically to Docker Hub on every release — no need to clone the repo or build locally.

1. **Launch**: Download the compose file and start the services:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/RikyZ90/ShibaClaw/main/docker-compose.yml -o docker-compose.yml
   docker compose up -d             # pulls the image and starts gateway + webUI
   ```
2. **Onboard**: Configure your LLM provider:
   ```bash
   docker exec -it shibaclaw-gateway shibaclaw onboard
   ```
   *Follow the prompts to add your LLM API keys.*
3. **Verify**: Check the logs to ensure your Shiba is hunting:
   ```bash
   docker logs -f shibaclaw-gateway
   ```

> **To update**: just run `docker compose pull && docker compose up -d` — no rebuild needed.

### 🛠️ manual Docker run (No Compose)

If you prefer to run the image directly:

```bash
docker pull rikyz90/shibaclaw:latest
docker run -d --name shibaclaw -p 3000:3000 -v shibaclaw_data:/root/.shibaclaw rikyz90/shibaclaw:latest
```

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
2. **Configure**: Run the onboarding setup:
   ```bash
   shibaclaw onboard
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
   - **Web Mode**: Launch the full WebUI interface with the background agent engine.
     ```bash
     shibaclaw web --with-gateway
     # Or explicit localhost/port:
     shibaclaw web --host 127.0.0.1 --port 3000 --with-gateway
     ```

> **OpenRouter OAuth note**: the PKCE callback reuses the same WebUI URL and port, so port `3000` remains the normal WebUI port and does not require a second local server. If your WebUI is published through a reverse proxy or a different public origin, set `SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL=https://your-public-webui-host` before starting ShibaClaw.

---

## 🦴 Useful Commands

| Command | Action |
| :--- | :--- |
| `shibaclaw --version` | Check the installed ShibaClaw version. |
| `shibaclaw onboard` | Reconfigure provider, model, and channels. |
| `shibaclaw web -g` | Launch WebUI + Gateway (background) on `http://127.0.0.1:3000`. |

**Happy hunting!** 🐕‍🦺🔥
