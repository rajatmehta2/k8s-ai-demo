import json
from typing import Dict, Any, List, Optional
from loguru import logger
from app.kubernetes.kubectl_executor import execute_kubectl

def inspect_deployments(context: Optional[str] = None) -> Dict[str, Any]:
    """
    Inspects deployments to check available/unavailable replicas and rollout health.
    """
    logger.info("Starting Deployment inspection...")
    result = execute_kubectl(["get", "deployments", "-A", "-o", "json"], context=context)
    
    if not result.success:
        logger.error(f"Failed to get deployments: {result.stderr}")
        return {
            "healthy": False,
            "error": result.stderr,
            "unhealthy_deployments": [],
            "all_deployments": []
        }
        
    try:
        data = json.loads(result.stdout)
    except Exception as e:
        logger.error(f"Failed to parse deployments JSON: {e}")
        return {
            "healthy": False,
            "error": f"Failed to parse JSON: {str(e)}",
            "unhealthy_deployments": [],
            "all_deployments": []
        }
        
    items = data.get("items", [])
    all_deployments = []
    unhealthy_deployments = []
    
    for item in items:
        metadata = item.get("metadata", {})
        name = metadata.get("name")
        namespace = metadata.get("namespace")
        
        spec = item.get("spec", {})
        desired_replicas = spec.get("replicas", 1)
        
        status = item.get("status", {})
        replicas = status.get("replicas", 0)
        ready_replicas = status.get("readyReplicas", 0)
        available_replicas = status.get("availableReplicas", 0)
        unavailable_replicas = status.get("unavailableReplicas", 0)
        updated_replicas = status.get("updatedReplicas", 0)
        
        conditions = status.get("conditions", [])
        
        is_unhealthy = False
        unhealthy_reasons = []
        
        # Check replica balance
        if available_replicas < desired_replicas:
            is_unhealthy = True
            unhealthy_reasons.append(
                f"Available replicas ({available_replicas}) is less than desired replicas ({desired_replicas})"
            )
            
        if unavailable_replicas > 0:
            is_unhealthy = True
            unhealthy_reasons.append(f"Has {unavailable_replicas} unavailable replicas")
            
        # Inspect conditions for failures
        for cond in conditions:
            c_type = cond.get("type")
            c_status = cond.get("status")
            c_reason = cond.get("reason")
            c_message = cond.get("message", "")
            
            # ProgressDeadlineExceeded means deployment rollout failed or timed out
            if c_type == "Progressing" and c_status == "False" and c_reason == "ProgressDeadlineExceeded":
                is_unhealthy = True
                unhealthy_reasons.append(f"Rollout failed: ProgressDeadlineExceeded ({c_message})")
                
            # If Available is False, it means the deployment is not actively available
            if c_type == "Available" and c_status == "False":
                is_unhealthy = True
                unhealthy_reasons.append(f"Deployment is unavailable: {c_message}")
                
        deployment_summary = {
            "name": name,
            "namespace": namespace,
            "desired_replicas": desired_replicas,
            "ready_replicas": ready_replicas,
            "available_replicas": available_replicas,
            "unavailable_replicas": unavailable_replicas,
            "updated_replicas": updated_replicas,
            "healthy": not is_unhealthy,
            "reasons": unhealthy_reasons,
            "conditions": [
                {
                    "type": c.get("type"),
                    "status": c.get("status"),
                    "reason": c.get("reason"),
                    "message": c.get("message")
                }
                for c in conditions
            ]
        }
        
        all_deployments.append(deployment_summary)
        if is_unhealthy:
            unhealthy_deployments.append(deployment_summary)
            
    logger.info(f"Deployment inspection complete. Unhealthy deployments: {len(unhealthy_deployments)}")
    
    return {
        "healthy": len(unhealthy_deployments) == 0,
        "unhealthy_deployments": unhealthy_deployments,
        "all_deployments": all_deployments
    }
