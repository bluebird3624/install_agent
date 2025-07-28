# IT Assistant with Ollama Integration

A professional, cross-platform IT assistant powered by local LLM models via the Ollama API. This tool helps users with system administration, troubleshooting, and command execution in a secure, interactive chat format.

## Features
- **Ollama Chat Integration:** Uses Ollama's `/api/chat` endpoint for natural language IT assistance.
- **Command Extraction & Execution:** Parses AI responses for shell commands, asks for user confirmation, and executes them safely.
- **Security Validation:** Blocks dangerous commands and requests confirmation for privileged actions.
- **OS Detection:** Provides OS-specific installation and troubleshooting commands (Linux, macOS, Windows).
- **Conversation History:** Maintains and saves chat history for context and auditing.
- **Fallback Responses:** Offers basic IT solutions if the AI model is unavailable.
- **Configurable Timeouts:** Separate timeouts for AI responses and command execution.
- **Logging:** All interactions and errors are logged for security and debugging.

## Requirements
- Python 3.8+
- [Ollama](https://ollama.com/download) installed and running (`ollama serve`)
- Internet connection for model downloads (if needed)

## Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/bluebird3624/install_agent.git
   cd install_agent
   ```
2. **Install dependencies:**
   (No external Python packages required; uses standard library)
3. **Start Ollama:**
   ```bash
   ollama serve
   ```
4. **Run the IT Assistant:**
   ```bash
   python3 main.py
   ```

## Usage
- **Interactive Chat:**
  - Type IT-related questions or requests (e.g., "Install htop", "Check disk space", "Configure firewall").
  - The assistant analyzes your request, provides solutions, and suggests commands.
  - For commands requiring privileges, you will be prompted for confirmation.
- **Special Commands:**
  - `help` — Show help message
  - `quit` — Exit the assistant
  - `save` — Save conversation history
  - `clear` — Clear the screen

## Command-Line Options
| Option           | Description                                 | Default                |
|------------------|---------------------------------------------|------------------------|
| `--model`        | Ollama model to use                         | `phi`                  |
| `--url`          | Ollama server URL                           | `http://localhost:11434`|
| `--timeout`      | Command execution timeout (seconds)         | `30`                   |
| `--ai-timeout`   | AI response timeout (seconds)               | `180`                  |
| `--log-level`    | Logging level (`DEBUG`, `INFO`, etc.)       | `INFO`                 |
| `--no-confirm`   | Skip confirmation for privileged commands   | (requires confirmation) |

Example:
```bash
python3 main.py --model llama2 --ai-timeout 120 --log-level DEBUG
```

## How It Works
- **OllamaClient:** Handles communication with Ollama's chat API, sending context-rich messages and receiving responses.
- **ITAssistant:** Orchestrates user interaction, context management, command extraction, and execution.
- **SecurityValidator:** Checks commands for dangerous patterns and privilege requirements.
- **PermissionManager:** Prompts user for confirmation before running privileged commands.
- **CommandExecutor:** Runs shell commands with error handling and timeouts.
- **ResponseParser:** Extracts shell commands from AI responses using regex patterns.
- **ConversationManager:** Maintains chat history and formats it for the Ollama chat endpoint.

## Security
- Blocks dangerous commands (e.g., `rm -rf /`, fork bombs).
- Requires user confirmation for privileged actions (e.g., `sudo`, `apt`, `yum`).
- Logs all actions and errors to `it_assistant.log`.

## Troubleshooting
- **AI Model Unavailable:**
  - Make sure Ollama is running (`ollama serve`).
  - Try a smaller/faster model (e.g., `llama2 7B`).
  - Increase `--ai-timeout` if needed.
- **Command Execution Issues:**
  - Check your OS and package manager compatibility.
  - Review logs in `it_assistant.log` for errors.

## Saving Conversation History
- Use the `save` command in the chat to save the current conversation to a timestamped JSON file.

## Example Session
```
You: install htop
Assistant: (Provides OS-specific install commands)
You: (Confirms execution)
Assistant: (Runs command, shows output/errors)
```

## License
``` txt
This software is proprietary and all rights are reserved by the author. Unauthorized use, distribution, or modification is strictly prohibited. Commercial use requires a separate license agreement and compensation to the author. For licensing inquiries, contact koechroy06@gmail.com
```

## Author
Roy Kipchumba
