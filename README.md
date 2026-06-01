Jarvis --- Personal AI OS
=======================

> A multi-agent CrewAI system that automates research, content, design validation, and social posting for a solo mobile app developer.

🧠 Architecture & Stack
-----------------------

-   **Orchestration:** CrewAI (Hierarchical layout)

-   **Primary LLM:** DeepSeek (`deepseek-chat`) via OpenRouter

-   **Multimodal/Coding LLM:** MiniMax M3

-   **Vision LLM:** Anthropic Claude 3.5 Sonnet

-   **Memory:** ChromaDB (Short-term) + Obsidian Vault (Long-term)

🚀 Setup & Installation (Phase 0)
---------------------------------

1.  **Create the Folder Structure:** Run the setup script from the root directory:

    ```
    bash scripts/setup.sh

    ```

2.  **Set Up Python Environment (Using `uv` - Recommended):**

    ```
    uv venv
    source .venv/bin/activate

    ```

3.  **Install Core Dependencies:**

    ```
    uv pip install crewai crewai-tools openai anthropic python-dotenv

    ```

4.  **Configure Environment:** Copy `.env.example` to `.env` and add your API keys. Never commit `.env` to version control.

📂 Project Structure
--------------------

-   `/backend`: Core Python backend, CrewAI agents, config, tools, and FastAPI server.

-   `/frontend`: Next.js dashboard (Deferred to Phase 4).

-   `/obsidian-vault`: Long-term memory storage.

-   `/docs`: Project documentation and workflow specs.