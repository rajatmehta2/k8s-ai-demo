import json
from typing import Dict, Any, List, Optional
from loguru import logger
from app.kubernetes.kubectl_executor import execute_kubectl

def inspect_pods(context: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves pod statuses across all namespaces and identifies unhealthy or stuck pods.
    """
    logger.info("Starting Pod inspection...")
    result = execute_kubectl(["get", "pods", "-A", "-o", "json"], context=context)
    
    if not result.success:
        logger.error(f"Failed to get pods: {result.stderr}")
        return {
            "healthy": False,
            "error": result.stderr,
            "problematic_pods": [],
            "all_pods": []
        }
        
    try:
        data = json.loads(result.stdout)
    except Exception as e:
        logger.error(f"Failed to parse kubectl output as JSON: {e}")
        return {
            "healthy": False,
            "error": f"Failed to parse JSON: {str(e)}",
            "problematic_pods": [],
            "all_pods": []
        }
        
    items = data.get("items", [])
    problematic_pods = []
    all_pods_summary = []
    
    # Common unhealthy statuses or reasons
    unhealthy_statuses = {
        "CrashLoopBackOff", "ImagePullBackOff", "Pending", "Error", "OOMKilled",
        "ContainerCreating", "PodInitializing", "ErrImagePull", "CreateContainerConfigError",
        "CreateContainerError", "InvalidImageName"
    }
    
    for item in items:
        metadata = item.get("metadata", {})
        name = metadata.get("name")
        namespace = metadata.get("namespace")
        
        status_info = item.get("status", {})
        phase = status_info.get("phase", "Unknown")
        
        container_statuses = status_info.get("containerStatuses", [])
        init_container_statuses = status_info.get("initContainerStatuses", [])
        
        pod_status = phase
        reason = None
        message = None
        unhealthy_containers = []
        
        # Check all container statuses for any waiting or terminated issues
        for cs in init_container_statuses + container_statuses:
            c_name = cs.get("name")
            state = cs.get("state", {})
            ready = cs.get("ready", False)
            restart_count = cs.get("restartCount", 0)
            
            c_status = "Running" if ready else "NotReady"
            c_reason = None
            c_message = None
            
            if "waiting" in state:
                waiting = state["waiting"]
                c_status = "Waiting"
                c_reason = waiting.get("reason", "Waiting")
                c_message = waiting.get("message", "")
            elif "terminated" in state:
                terminated = state["terminated"]
                exit_code = terminated.get("exitCode", 0)
                c_reason = terminated.get("reason", "Terminated")
                c_message = terminated.get("message", "")
                if exit_code != 0:
                    c_status = "TerminatedError"
                else:
                    c_status = "Completed"
            
            # Determine if this container is problematic
            is_problem = False
            # If the container is waiting or terminated with error, it's problematic
            if c_status in ["Waiting", "TerminatedError"]:
                is_problem = True
            # Even if it's running but has restarts, let's keep an eye on it,
            # though it's technically running now. Let's prioritize active issues.
            
            if is_problem:
                unhealthy_containers.append({
                    "container_name": c_name,
                    "status": c_status,
                    "reason": c_reason,
                    "message": c_message,
                    "restart_count": restart_count
                })
                
                # Elevate pod status/reason to the container issue if available
                if c_reason:
                    pod_status = c_reason
                    reason = c_reason
                    message = c_message
        
        # If no container statuses exist and phase is Pending/Failed
        if not container_statuses and not init_container_statuses:
            if phase in ["Pending", "Failed", "Unknown"]:
                pod_status = phase
                reason = status_info.get("reason")
                message = status_info.get("message")
                
        # Determine if overall pod is unhealthy
        is_unhealthy = False
        if phase in ["Failed", "Unknown"]:
            is_unhealthy = True
        elif phase == "Pending":
            is_unhealthy = True
            pod_status = "Pending"
        elif len(unhealthy_containers) > 0:
            is_unhealthy = True
            
        # Format a pod summary entry
        pod_summary = {
            "name": name,
            "namespace": namespace,
            "status": pod_status,
            "phase": phase,
            "ready": f"{sum(1 for cs in container_statuses if cs.get('ready'))}/{len(container_statuses)}" if container_statuses else "0/0",
            "restarts": sum(cs.get("restartCount", 0) for cs in container_statuses),
            "unhealthy_containers": unhealthy_containers,
            "reason": reason,
            "message": message
        }
        
        all_pods_summary.append(pod_summary)
        
        if is_unhealthy:
            problematic_pods.append({
                "name": name,
                "namespace": namespace,
                "status": pod_status,
                "phase": phase,
                "ready": pod_summary["ready"],
                "restarts": pod_summary["restarts"],
                "unhealthy_containers": unhealthy_containers,
                "reason": reason,
                "message": message
            })
            
    is_cluster_pods_healthy = len(problematic_pods) == 0
    logger.info(f"Pod inspection complete. Problematic pods count: {len(problematic_pods)}")
    
    return {
        "healthy": is_cluster_pods_healthy,
        "problematic_pods": problematic_pods,
        "all_pods": all_pods_summary
    }
