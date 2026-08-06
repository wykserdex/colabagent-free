# 🤖 ColabAgent Free

**Self‑hosted AI coding agent for those without a powerful PC.**  
All heavy inference runs on **Google Colab** (free GPU), while the lightweight orchestrator runs locally and communicates via a Cloudflare Tunnel.

---

## ✨ Features

- 📂 **Project exploration** – list files, read files, search text.
- ✏️ **Code editing** – atomic writes and precise patches (no full-file rewrites).
- 🧪 **Test execution** – `pytest` with a restricted set of flags.
- 🔍 **Git integration** – `status` and `diff` to review changes.
- 🛡️ **Safety first** – path confinement, secret redaction, human approval for risky actions.
- 🖥️ **Two interfaces** – CLI (Typer) and TUI (Textual).
- 💸 **100% free** – no expensive hardware required, compute is offloaded to Colab.

---

## 🧠 How It Works

1. **Start the server in Google Colab** – it pulls Ollama with a model (e.g., `gpt-oss:20b`), launches a FastAPI app, and exposes it via Cloudflare Tunnel.
2. **Copy the generated URL** (e.g., `https://something.trycloudflare.com`).
3. **Configure your local `.env`** with that URL.
4. **Run the agent** – it sends requests to Colab, gets responses, and performs actions on your local project.

No large models are loaded locally – any machine with Python 3.11+ will do.

---

## 📦 Local Installation

Clone the repository and install the package:

```bash
git clone https://github.com/wykserdex/colabagent-free.git
cd colabagent-free
pip install -e .
