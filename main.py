#!/usr/bin/env python3
"""
Professional IT Assistant with Ollama Integration
A comprehensive system administration assistant powered by local LLM models in chat style.

Author: AI Assistant
Version: 1.2
License: MIT
"""

import requests
import subprocess
import json
import sys
import os
import time
import re
import getpass
import threading
import logging
import argparse
import platform
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class Config:
    """Configuration management for the IT Assistant."""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.default_model = "phi"
        self.command_timeout = 30
        self.log_level = logging.INFO
        self.log_file = "it_assistant.log"
        self.max_retries = 3
        self.conversation_history_limit = 50
        self.ollama_timeout = 180  # 3 minutes for AI responses
        
        # Security settings
        self.require_confirmation = True
        self.sandbox_mode = False
        self.dangerous_commands = [
            r'rm\s+-rf\s+/',
            r'format\s+c:',
            r'del\s+/s\s+/q\s+c:\\',
            r'shutdown\s+-h\s+now',
            r'init\s+0',
            r':(){ :|:& };:',  # Fork bomb
            r'dd\s+if=/dev/zero',
            r'mkfs\.',
            r'fdisk.*--delete',
        ]
        
        self.privileged_commands = [
            'sudo', 'su', 'doas', 'runas',
            'systemctl', 'service', 'chkconfig',
            'apt', 'yum', 'dnf', 'pacman', 'zypper',
            'mount', 'umount', 'fsck',
            'iptables', 'ufw', 'firewall-cmd',
            'choco', 'brew',
        ]

class OllamaClient:
    """Handle communication with the Ollama API using chat endpoint."""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.ollama_url
        self.model = config.default_model
        self.logger = logging.getLogger(__name__)
        
    def test_connection(self) -> bool:
        """Test if Ollama server is accessible."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to connect to Ollama: {e}")
            return False
    
    def list_models(self) -> List[str]:
        """Get list of available models."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to get model list: {e}")
        return []
    
    def chat(self, messages: List[Dict], timeout: int = None) -> Optional[str]:
        """Send chat request to Ollama API."""
        timeout = timeout or self.config.ollama_timeout
        
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_ctx": 2048,
                    "num_predict": 512,
                }
            }
            
            print(f"{Colors.WARNING}Requesting from: {self.base_url}/api/chat{Colors.ENDC}")
            print(f"{Colors.WARNING}Model: {self.model} | Timeout: {timeout}s{Colors.ENDC}")
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('message', {}).get('content', '').strip()
            else:
                self.logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error(f"Request timed out after {timeout} seconds")
            print(f"{Colors.FAIL}AI response timed out. Try using a smaller/faster model or increase timeout.{Colors.ENDC}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            return None

class SecurityValidator:
    """Validate command safety and security."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def is_dangerous_command(self, command: str) -> Tuple[bool, str]:
        """Check if command is potentially dangerous."""
        for pattern in self.config.dangerous_commands:
            if re.search(pattern, command, re.IGNORECASE):
                return True, f"Command matches dangerous pattern: {pattern}"
        return False, ""
    
    def requires_privileges(self, command: str) -> bool:
        """Check if command requires elevated privileges."""
        command_lower = command.lower().strip()
        return any(cmd in command_lower for cmd in self.config.privileged_commands)
    
    def validate_command(self, command: str) -> Tuple[bool, str, bool]:
        """
        Validate command safety.
        Returns: (is_safe, reason, requires_privileges)
        """
        is_dangerous, danger_reason = self.is_dangerous_command(command)
        if is_dangerous:
            return False, danger_reason, False
        
        requires_privs = self.requires_privileges(command)
        return True, "", requires_privs

class PermissionManager:
    """Handle privilege escalation and user permissions."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def request_permission(self, command: str, purpose: str = "", risks: str = "") -> bool:
        """Request user permission for privileged command."""
        if not self.config.require_confirmation:
            return True
        
        print(f"\n{Colors.WARNING}⚠️  PRIVILEGE ESCALATION REQUIRED{Colors.ENDC}")
        print(f"{Colors.BOLD}Command:{Colors.ENDC} {command}")
        
        if purpose:
            print(f"{Colors.BOLD}Purpose:{Colors.ENDC} {purpose}")
        if risks:
            print(f"{Colors.BOLD}Risks:{Colors.ENDC} {risks}")
        
        while True:
            response = input(f"\n{Colors.OKBLUE}Proceed? (yes/no/explain): {Colors.ENDC}").lower().strip()
            
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            elif response in ['explain', 'e']:
                self._explain_command(command)
            else:
                print("Please respond with 'yes', 'no', or 'explain'")
    
    def _explain_command(self, command: str):
        """Provide detailed explanation of what the command does."""
        explanations = {
            'sudo': "Executes command with administrator privileges",
            'systemctl': "Controls system services (start, stop, restart, enable, disable)",
            'apt': "Package manager for Debian/Ubuntu systems",
            'yum': "Package manager for Red Hat based systems",
            'dnf': "Package manager for newer Red Hat based systems",
            'pacman': "Package manager for Arch Linux",
            'zypper': "Package manager for openSUSE",
            'mount': "Attaches filesystem to directory tree",
            'iptables': "Configures firewall rules",
            'choco': "Package manager for Windows",
            'brew': "Package manager for macOS",
        }
        
        cmd_word = command.split()[0]
        explanation = explanations.get(cmd_word, "No detailed explanation available")
        print(f"\n{Colors.OKCYAN}Command Explanation:{Colors.ENDC} {explanation}")

class CommandExecutor:
    """Execute system commands safely with proper error handling."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.security_validator = SecurityValidator(config)
        self.permission_manager = PermissionManager(config)
    
    def execute_command(self, command: str, timeout: int = None) -> Tuple[bool, str, str]:
        """
        Execute a system command safely.
        Returns: (success, stdout, stderr)
        """
        timeout = timeout or self.config.command_timeout
        
        # Validate command safety
        is_safe, reason, requires_privs = self.security_validator.validate_command(command)
        
        if not is_safe:
            error_msg = f"Command blocked for security: {reason}"
            self.logger.warning(error_msg)
            return False, "", error_msg
        
        # Request permission for privileged commands
        if requires_privs:
            purpose = "Install or modify system packages"
            risks = "May modify system configuration or install new software"
            if not self.permission_manager.request_permission(command, purpose, risks):
                return False, "", "Permission denied by user"
        
        try:
            print(f"{Colors.OKCYAN}Executing:{Colors.ENDC} {command}")
            
            # Execute command with timeout
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return_code = process.returncode
                
                if return_code == 0:
                    print(f"{Colors.OKGREEN}✓ Command completed successfully{Colors.ENDC}")
                    return True, stdout, stderr
                else:
                    print(f"{Colors.FAIL}✗ Command failed with code {return_code}{Colors.ENDC}")
                    return False, stdout, stderr
                    
            except subprocess.TimeoutExpired:
                process.kill()
                error_msg = f"Command timed out after {timeout} seconds"
                self.logger.error(error_msg)
                return False, "", error_msg
                
        except Exception as e:
            error_msg = f"Execution error: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg

class ResponseParser:
    """Parse LLM responses to extract executable commands."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Patterns to identify commands in responses
        self.command_patterns = [
            r'```bash\n(.*?)\n```',
            r'```shell\n(.*?)\n```',
            r'```sh\n(.*?)\n```',
            r'Command:\s*`([^`]+)`',
            r'Execute:\s*`([^`]+)`',
            r'Run:\s*`([^`]+)`',
            r'```\n(.*?)\n```',
        ]
    
    def extract_commands(self, response: str) -> List[str]:
        """Extract executable commands from LLM response."""
        commands = []
        
        for pattern in self.command_patterns:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            for match in matches:
                # Clean up the command
                cmd = match.strip()
                if cmd and not cmd.startswith('#'):  # Skip comments
                    commands.append(cmd)
        
        return commands
    
    def needs_user_input(self, response: str) -> bool:
        """Check if the response is asking for user input."""
        input_indicators = [
            "need to know",
            "please provide",
            "what is your",
            "can you tell me",
            "which",
            "do you have",
            "?",
        ]
        
        return any(indicator in response.lower() for indicator in input_indicators)

class ConversationManager:
    """Manage conversation history and context."""
    
    def __init__(self, config: Config):
        self.config = config
        self.history = []
        self.logger = logging.getLogger(__name__)
    
    def add_message(self, role: str, content: str, metadata: Dict = None):
        """Add message to conversation history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.history.append(message)
        
        # Limit history size
        if len(self.history) > self.config.conversation_history_limit:
            self.history = self.history[-self.config.conversation_history_limit:]
    
    def get_chat_messages(self) -> List[Dict]:
        """Get conversation history formatted for chat endpoint."""
        messages = [
            {
                "role": "system",
                "content": """You are an expert IT professional assistant. Your role is to help users with any technical requests while maintaining the highest standards of professionalism, security, and problem-solving expertise.

When providing solutions:
1. Analyze the request carefully and determine if it's actionable
2. Ask for specific information if needed
3. Provide step-by-step solutions with clear explanations
4. For executable commands, wrap them in ```bash or ```shell code blocks
5. Explain what each command does and why it's needed
6. Mention any risks or side effects
7. Provide verification steps after execution

Always prioritize system stability and security. Be thorough, professional, and educational in your responses."""
            }
        ]
        
        for msg in self.history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return messages
    
    def save_history(self, filename: str = None):
        """Save conversation history to file."""
        filename = filename or f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.history, f, indent=2)
            print(f"Conversation saved to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save conversation: {e}")

class ITAssistant:
    """Main IT Assistant class orchestrating all components."""
    
    def __init__(self, config: Config):
        self.config = config
        self.ollama_client = OllamaClient(config)
        self.command_executor = CommandExecutor(config)
        self.response_parser = ResponseParser()
        self.conversation_manager = ConversationManager(config)
        self.logger = logging.getLogger(__name__)
        self.os_type = platform.system().lower()

    def initialize(self) -> bool:
        """Initialize the assistant and check connections."""
        print(f"{Colors.HEADER}IT Assistant v1.2 - Professional System Administration{Colors.ENDC}")
        print(f"Platform: {platform.system()} {platform.release()}")
        
        # Test Ollama connection
        print("Testing Ollama connection...", end=" ")
        if self.ollama_client.test_connection():
            print(f"{Colors.OKGREEN}✓ Connected{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}✗ Failed{Colors.ENDC}")
            print("Please ensure Ollama is running and accessible.")
            return False
        
        # List available models
        models = self.ollama_client.list_models()
        if models:
            print(f"Available models: {', '.join(models)}")
            if self.config.default_model not in models:
                print(f"{Colors.WARNING}Warning: Default model '{self.config.default_model}' not found{Colors.ENDC}")
        
        print(f"Using model: {Colors.BOLD}{self.config.default_model}{Colors.ENDC}")
        print(f"Type 'help' for commands, 'quit' to exit\n")
        
        return True
    
    def _generate_fallback_response(self, user_input: str) -> str:
        """Generate a basic fallback response when AI is unavailable."""
        user_lower = user_input.lower()
        
        # Check for installation requests
        install_match = re.match(r'\b(?:install|setup)\s+([a-zA-Z0-9\-_]+)\b', user_lower)
        if install_match:
            package = install_match.group(1)
            return self._generate_install_commands(package)
        
        if any(word in user_lower for word in ['disk', 'space', 'storage']):
            return """AI unavailable. Here are basic disk space commands:

```bash
df -h
```
Shows disk usage in human-readable format.

```bash
du -sh /*
```
Shows directory sizes in root."""
        
        elif any(word in user_lower for word in ['process', 'cpu', 'memory']):
            return """AI unavailable. Here are process monitoring commands:

```bash
top
```
Shows running processes and resource usage.

```bash
ps aux | head -20
```
Lists running processes."""
        
        elif any(word in user_lower for word in ['network', 'connection', 'port']):
            return """AI unavailable. Here are network diagnostic commands:

```bash
netstat -tulpn
```
Shows listening ports.

```bash
ping -c 4 8.8.8.8
```
Tests internet connectivity."""
        
        else:
            return f"""AI model is currently unavailable (timeout). 

You asked: "{user_input}"

Please try:
1. Using a smaller/faster model (llama2 7B instead of 13B/70B)
2. Restarting Ollama: 'ollama serve'
3. Checking system resources with 'htop'
4. Reducing prompt complexity

Type your request again when ready."""
    
    def _generate_install_commands(self, package: str) -> str:
        """Generate OS-specific commands for installing a package."""
        if self.os_type == "linux":
            # Check for common Linux distributions
            try:
                with open("/etc/os-release", "r") as f:
                    os_info = f.read().lower()
                    if "debian" in os_info or "ubuntu" in os_info:
                        return f"""To install {package} on Debian/Ubuntu-based systems:

```bash
sudo apt update
sudo apt install {package}
```
These commands update the package lists and install {package}."""
                    elif "centos" in os_info or "fedora" in os_info or "rhel" in os_info:
                        return f"""To install {package} on Red Hat-based systems:

```bash
sudo dnf install {package}
```
This command installs {package} using the DNF package manager."""
                    elif "arch" in os_info:
                        return f"""To install {package} on Arch Linux:

```bash
sudo pacman -S {package}
```
This command installs {package} using the pacman package manager."""
                    else:
                        return f"""To install {package} on other Linux distributions:

```bash
sudo yum install {package}
```
This command attempts to install {package} using the YUM package manager. If this fails, check your distribution's package manager."""
            except FileNotFoundError:
                return f"""To install {package} on Linux (generic):

```bash
sudo yum install {package}
```
This command attempts to install {package} using the YUM package manager. If this fails, check your distribution's package manager."""
        
        elif self.os_type == "darwin":
            return f"""To install {package} on macOS, you need Homebrew installed. If you don't have Homebrew, install it first:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Then install {package}:

```bash
brew install {package}
```
These commands install Homebrew (if needed) and then {package}."""
        
        elif self.os_type == "windows":
            return f"""To install {package} on Windows, you need Chocolatey installed. If you don't have Chocolatey, install it first (requires PowerShell as Administrator):

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```
Then install {package}:

```powershell
choco install {package}
```
These commands install Chocolatey (if needed) and then {package}."""
        
        else:
            return f"""Unsupported operating system for installing {package}. Please specify the installation method for your system or consult the package documentation."""

    def process_user_input(self, user_input: str) -> str:
        """Process user input and generate response."""
        # Add user message to history
        self.conversation_manager.add_message("user", user_input)
        
        # Handle installation requests
        install_match = re.match(r'\b(?:install|setup)\s+([a-zA-Z0-9\-_]+)\b', user_input.lower())
        if install_match:
            package = install_match.group(1)
            response = self._generate_install_commands(package)
            self.conversation_manager.add_message("assistant", response)
            return response
        
        # Get chat messages for context
        messages = self.conversation_manager.get_chat_messages()
        
        # Generate response from Ollama
        response = self.ollama_client.chat(messages, timeout=self.config.ollama_timeout)
        
        if not response:
            # Fallback response if AI is unavailable
            fallback_response = self._generate_fallback_response(user_input)
            self.conversation_manager.add_message("assistant", fallback_response)
            return fallback_response
        
        # Add assistant response to history
        self.conversation_manager.add_message("assistant", response)
        
        return response
    
    def handle_command_execution(self, response: str) -> str:
        """Handle execution of commands found in the response."""
        commands = self.response_parser.extract_commands(response)
        
        if not commands:
            return response
        
        execution_results = []
        
        for command in commands:
            print(f"\n{Colors.OKBLUE}Found command to execute:{Colors.ENDC} {command}")
            
            # Ask user if they want to execute
            if input("Execute this command? (y/n): ").lower().strip() == 'y':
                success, stdout, stderr = self.command_executor.execute_command(command)
                
                result = {
                    "command": command,
                    "success": success,
                    "stdout": stdout,
                    "stderr": stderr
                }
                
                execution_results.append(result)
                
                # Show output
                if stdout:
                    print(f"{Colors.OKGREEN}Output:{Colors.ENDC}\n{stdout}")
                if stderr:
                    print(f"{Colors.WARNING}Errors:{Colors.ENDC}\n{stderr}")
                
                # If command failed, ask AI to analyze and fix
                if not success and stderr:
                    print(f"\n{Colors.WARNING}Command failed. Asking AI for solution...{Colors.ENDC}")
                    
                    self.conversation_manager.add_message(
                        "user",
                        f"The command '{command}' failed with this error:\n{stderr}\nPlease analyze this error and provide a solution or alternative approach."
                    )
                    
                    fix_response = self.ollama_client.chat(self.conversation_manager.get_chat_messages())
                    
                    if fix_response:
                        print(f"\n{Colors.OKCYAN}AI Analysis:{Colors.ENDC}\n{fix_response}")
                        self.conversation_manager.add_message("assistant", fix_response)
                        
                        # Recursively handle any new commands in the fix
                        return self.handle_command_execution(fix_response)
        
        return response
    
    def run_interactive_session(self):
        """Run the main interactive session."""
        if not self.initialize():
            return
        
        try:
            while True:
                try:
                    user_input = input(f"\n{Colors.BOLD}You:{Colors.ENDC} ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle special commands
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        break
                    elif user_input.lower() == 'help':
                        self.show_help()
                        continue
                    elif user_input.lower() == 'save':
                        self.conversation_manager.save_history()
                        continue
                    elif user_input.lower() == 'clear':
                        os.system('clear' if os.name == 'posix' else 'cls')
                        continue
                    
                    # Process the request
                    print(f"\n{Colors.OKCYAN}Assistant:{Colors.ENDC} Analyzing your request...")
                    
                    response = self.process_user_input(user_input)
                    print(f"\n{Colors.OKCYAN}Assistant:{Colors.ENDC}\n{response}")
                    
                    # Handle command execution if needed
                    self.handle_command_execution(response)
                    
                except KeyboardInterrupt:
                    print(f"\n{Colors.WARNING}Interrupted by user{Colors.ENDC}")
                    continue
                except Exception as e:
                    self.logger.error(f"Unexpected error: {e}")
                    print(f"{Colors.FAIL}An error occurred: {e}{Colors.ENDC}")
        
        finally:
            print(f"\n{Colors.HEADER}Thank you for using IT Assistant!{Colors.ENDC}")
            
            # Offer to save conversation
            if input("Save conversation history? (y/n): ").lower().strip() == 'y':
                self.conversation_manager.save_history()
    
    def show_help(self):
        """Display help information."""
        help_text = f"""
{Colors.HEADER}IT Assistant Commands:{Colors.ENDC}

{Colors.BOLD}Special Commands:{Colors.ENDC}
  help     - Show this help message
  quit     - Exit the assistant
  save     - Save conversation history
  clear    - Clear screen

{Colors.BOLD}Usage:{Colors.ENDC}
  Simply type your IT-related questions or requests in natural language.
  The assistant will analyze your request and provide solutions with executable commands.

{Colors.BOLD}Examples:{Colors.ENDC}
  - "Check disk space"
  - "Install htop"
  - "Install nginx"
  - "My nginx server won't start"
  - "Install Docker on Ubuntu"
  - "Show running processes using high CPU"
  - "Configure firewall to block port 22"

{Colors.BOLD}Security:{Colors.ENDC}
  - Commands requiring privileges will ask for confirmation
  - Dangerous commands are blocked automatically
  - All interactions are logged for security
        """
        print(help_text)

def setup_logging(config: Config):
    """Set up logging configuration."""
    logging.basicConfig(
        level=config.log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Professional IT Assistant with Ollama Integration')
    parser.add_argument('--model', '-m', default='phi', help='Ollama model to use')
    parser.add_argument('--url', '-u', default='http://localhost:11434', help='Ollama server URL')
    parser.add_argument('--timeout', '-t', type=int, default=30, help='Command execution timeout')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Logging level')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation for privileged commands')
    parser.add_argument('--ai-timeout', type=int, default=180, help='AI response timeout in seconds')
    
    args = parser.parse_args()
    
    # Create configuration
    config = Config()
    config.default_model = args.model
    config.ollama_url = args.url
    config.command_timeout = args.timeout
    config.log_level = getattr(logging, args.log_level)
    config.require_confirmation = not args.no_confirm
    config.ollama_timeout = args.ai_timeout
    
    # Setup logging
    setup_logging(config)
    
    # Create and run assistant
    assistant = ITAssistant(config)
    assistant.run_interactive_session()

if __name__ == "__main__":
    main()