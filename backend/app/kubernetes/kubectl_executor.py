import subprocess
import os
from typing import List, Dict, Any, Optional
from loguru import logger
from app.core.config import settings

class KubectlResult:
    def __init__(self, success: bool, stdout: str, stderr: str, returncode: int, command: str):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.command = command

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
            "command": self.command
        }

def execute_kubectl(args: List[str], context: Optional[str] = None) -> KubectlResult:
    """
    Safely executes a kubectl command using Python's subprocess.
    Automatically resolves and configures KUBECONFIG if present in settings.
    Optional context switcher flags can be passed to target a specific cluster.
    """
    command = ["kubectl"]
    if context:
        command.extend(["--context", context])
    command.extend(args)
    
    command_str = " ".join(command)
    logger.info(f"Executing kubectl command: {command_str}")

    # Set up environment variables
    env = os.environ.copy()
    if settings.kubeconfig_path:
        expanded_path = os.path.expanduser(settings.kubeconfig_path)
        if os.path.exists(expanded_path):
            env["KUBECONFIG"] = expanded_path
            logger.debug(f"Applied KUBECONFIG: {expanded_path}")
        else:
            logger.warning(f"Configured KUBECONFIG path does not exist: {expanded_path}")

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=30  # Safely timeout after 30 seconds
        )
        success = result.returncode == 0
        if not success:
            logger.warning(f"Command failed with code {result.returncode}: {command_str}. Error: {result.stderr.strip()}")
        return KubectlResult(
            success=success,
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            command=command_str
        )
    except subprocess.TimeoutExpired as e:
        logger.error(f"Command timed out after 30s: {command_str}")
        return KubectlResult(
            success=False,
            stdout="",
            stderr=f"Command timed out: {str(e)}",
            returncode=-1,
            command=command_str
        )
    except Exception as e:
        logger.error(f"Execution error on command '{command_str}': {str(e)}")
        return KubectlResult(
            success=False,
            stdout="",
            stderr=f"Execution error: {str(e)}",
            returncode=-1,
            command=command_str
        )

def get_contexts() -> List[str]:
    """
    Fetches the available Kubernetes contexts/clusters from the local kubeconfig.
    """
    result = execute_kubectl(["config", "get-contexts", "-o", "name"])
    if not result.success:
        logger.error(f"Failed to get Kubernetes contexts: {result.stderr}")
        return []
    
    # Split output by line and clean whitespaces
    contexts = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    logger.info(f"Retrieved available Kubernetes contexts: {contexts}")
    return contexts

def get_current_context() -> str:
    """
    Retrieves the currently active context from the local kubeconfig.
    """
    result = execute_kubectl(["config", "current-context"])
    if not result.success:
        logger.error(f"Failed to get current Kubernetes context: {result.stderr}")
        return ""
    
    current = result.stdout.strip()
    logger.info(f"Active Kubernetes context: '{current}'")
    return current
