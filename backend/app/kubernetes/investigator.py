from typing import Dict, Any
from loguru import logger

from app.kubernetes.pod_inspector import inspect_pods
from app.kubernetes.logs_collector import collect_logs
from app.kubernetes.events_analyzer import analyze_events
from app.kubernetes.deployment_inspector import inspect_deployments
from app.kubernetes.network_inspector import inspect_network

def run_investigation() -> Dict[str, Any]:
    """
    Orchestrates the complete junior DevOps Kubernetes cluster investigation flow:
    1. Check Pod status and find problematic pods.
    2. Collect logs for the failing pods/containers.
    3. Analyze warning events across the cluster.
    4. Inspect deployments for scaling/rollout health.
    5. Check services and endpoints for selector/connectivity issues.
    """
    logger.info("Starting orchestrated Kubernetes Cluster Investigation pipeline...")
    
    # 1. Inspect Pods
    pods_evidence = inspect_pods()
    
    # 2. Targeted Log Collection for problematic pods
    logs_evidence = {}
    problematic_pods = pods_evidence.get("problematic_pods", [])
    
    if problematic_pods:
        logger.info(f"Targeted log collection triggered for {len(problematic_pods)} problematic pods...")
        for pod in problematic_pods:
            pod_name = pod["name"]
            namespace = pod["namespace"]
            
            unhealthy_containers = pod.get("unhealthy_containers", [])
            if unhealthy_containers:
                for uc in unhealthy_containers:
                    c_name = uc.get("container_name")
                    log_key = f"{namespace}/{pod_name}/{c_name}"
                    logs_evidence[log_key] = collect_logs(
                        pod_name=pod_name,
                        namespace=namespace,
                        container_name=c_name
                    )
            else:
                log_key = f"{namespace}/{pod_name}"
                logs_evidence[log_key] = collect_logs(
                    pod_name=pod_name,
                    namespace=namespace
                )
    else:
        logger.info("All pods are healthy. Skipping log collection.")
        
    # 3. Analyze Events
    events_evidence = analyze_events()
    
    # 4. Inspect Deployments
    deployments_evidence = inspect_deployments()
    
    # 5. Check Services and Networking
    network_evidence = inspect_network()
    
    logger.info("Kubernetes Cluster Investigation pipeline successfully completed.")
    
    # Assemble final investigation structured payload
    return {
        "pods": pods_evidence,
        "logs": logs_evidence,
        "events": events_evidence,
        "deployments": deployments_evidence,
        "network": network_evidence
    }
