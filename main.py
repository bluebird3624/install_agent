import requests
import subprocess

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are a Linux shell assistant embedded inside a Python program "
        "that can run commands on the user's machine. "
        "Always respond ONLY with the bash commands wrapped in triple backticks, "
        "like this:\n```bash\n<command>\n```\n"
        "Do NOT include explanations or hypothetical scenarios. "
        "Assume the commands will be executed on a privileged shell, "
        "so do NOT include 'sudo' in your commands."
    )
}

DEFAULT_MODEL = "phi"

def ask_ollama(prompt, history, model=DEFAULT_MODEL):
    history.append({"role": "user", "content": prompt})

    messages = [SYSTEM_PROMPT] + history
    response = requests.post("http://localhost:11434/api/chat", json={
        "model": model,
        "messages": messages,
        "stream": False
    })

    result = response.json()
    print("🔍 RAW RESPONSE FROM OLLAMA:\n", result)

    if 'error' in result:
        raise Exception(f"Ollama model error: {result['error']}")

    message = result['message']['content']
    history.append({"role": "assistant", "content": message})
    return message, history

def extract_command(llm_response):
    """
    Extracts bash command enclosed in triple backticks ```bash ... ```
    Returns the command string or None if not found.
    """
    import re
    pattern = r"```bash\n(.+?)\n```"
    match = re.search(pattern, llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def run_command(cmd):
    # Remove sudo if it sneaks in
    cmd = cmd.replace("sudo ", "")
    try:
        print(f"\n🔧 Running command:\n{cmd}\n")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return f"✅ Command executed successfully:\n{result.stdout}"
        else:
            return f"❌ Command failed with error:\n{result.stderr}"
    except Exception as e:
        return f"❌ Exception occurred while running command:\n{str(e)}"

def main():
    print("🤖 Terminal Assistant (powered by Ollama)")
    print("Type your request (e.g., 'install Google Chrome'). Type 'exit' to quit.\n")

    history = []
    while True:
        user_input = input("🧑 You: ").strip()
        if user_input.lower() == 'exit':
            print("👋 Goodbye!")
            break

        try:
            response, history = ask_ollama(user_input, history)
            print("\n🤖 LLM Response:\n", response)

            command = extract_command(response)
            if command:
                confirm = input("\n⚠️ Run this command? [y/N]: ").strip().lower()
                if confirm == 'y':
                    output = run_command(command)
                    print(output)
                else:
                    print("🚫 Command not executed.")
            else:
                print("⚠️ No valid bash command found in response.")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
