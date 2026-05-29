from typing import Dict, Any, Optional, List
from loguru import logger
from app.kubernetes.kubectl_executor import execute_kubectl

def collect_logs(pod_name: str, namespace: str, container_name: Optional[str] = None, tail_lines: int = 100, context: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches logs for a given pod and namespace. If a container name is specified,
    fetches for that container, otherwise fetches logs for all containers in the pod.
    """
    logger.info(f"Collecting logs for pod {namespace}/{pod_name}...")
    
    args = ["logs", pod_name, "-n", namespace, f"--tail={tail_lines}"]
    if container_name:
        args.extend(["-c", container_name])
    else:
        # Fetch logs for all containers if possible
        args.append("--all-containers")
        
    result = execute_kubectl(args, context=context)
    
    # If it failed because --all-containers is not supported or fails on completed containers
    if not result.success and "--all-containers" in args:
        logger.debug(f"Retrying log collection without --all-containers for pod {namespace}/{pod_name}")
        args.remove("--all-containers")
        result = execute_kubectl(args, context=context)
        
    logs = result.stdout if result.success else f"Error retrieving logs: {result.stderr.strip()}"
    
    # Perform a light analysis for startup errors, exceptions, connection errors, etc.
    findings = []
    lower_logs = logs.lower()
    
    error_patterns = {
        "exception": "Exception detected",
        "connection failure": "Connection failure / connection timeout",
        "dial tcp": "Network dial TCP failure (possible connection issue)",
        "missing env": "Missing environment variable / configuration missing",
        "database": "Database access or connection error",
        "auth": "Authentication or authorization failure",
        "failed to load": "Resource loading failure",
        "panic": "Go Panic error / stacktrace",
        "fatal": "Fatal startup error",
        "error": "Generic error logs present"
    }
    
    for pattern, description in error_patterns.items():
        if pattern in lower_logs:
            findings.append(description)
            
    # Avoid general "Generic error logs present" if we already have specific errors
    if len(findings) > 1 and "Generic error logs present" in findings:
        findings.remove("Generic error logs present")
        
    return {
        "pod_name": pod_name,
        "namespace": namespace,
        "container_name": container_name or "all",
        "logs": logs,
        "concise_findings": findings
    }
