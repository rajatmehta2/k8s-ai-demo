import json
from typing import Dict, Any, List, Optional
from loguru import logger
from app.kubernetes.kubectl_executor import execute_kubectl

def inspect_network(context: Optional[str] = None) -> Dict[str, Any]:
    """
    Inspects Kubernetes services and endpoints to identify potential selector mismatches,
    missing endpoints, or empty endpoints.
    """
    logger.info("Starting Network/Service inspection...")
    
    # Fetch all services
    svc_result = execute_kubectl(["get", "svc", "-A", "-o", "json"], context=context)
    if not svc_result.success:
        logger.error(f"Failed to get services: {svc_result.stderr}")
        return {
            "healthy": False,
            "error": f"Failed to get services: {svc_result.stderr}",
            "problematic_services": [],
            "all_services": []
        }
        
    # Fetch all endpoints
    ep_result = execute_kubectl(["get", "endpoints", "-A", "-o", "json"], context=context)
    if not ep_result.success:
        logger.error(f"Failed to get endpoints: {ep_result.stderr}")
        return {
            "healthy": False,
            "error": f"Failed to get endpoints: {ep_result.stderr}",
            "problematic_services": [],
            "all_services": []
        }
        
    try:
        svc_data = json.loads(svc_result.stdout)
        ep_data = json.loads(ep_result.stdout)
    except Exception as e:
        logger.error(f"Failed to parse networking JSON: {e}")
        return {
            "healthy": False,
            "error": f"Failed to parse JSON: {str(e)}",
            "problematic_services": [],
            "all_services": []
        }
        
    # Build endpoints map by namespace/name
    endpoints_map = {}
    for ep in ep_data.get("items", []):
        ep_meta = ep.get("metadata", {})
        ep_name = ep_meta.get("name")
        ep_ns = ep_meta.get("namespace")
        endpoints_map[f"{ep_ns}/{ep_name}"] = ep
        
    all_services = []
    problematic_services = []
    
    for svc in svc_data.get("items", []):
        svc_meta = svc.get("metadata", {})
        svc_name = svc_meta.get("name")
        svc_ns = svc_meta.get("namespace")
        
        svc_spec = svc.get("spec", {})
        svc_type = svc_spec.get("type", "ClusterIP")
        selector = svc_spec.get("selector", {})
        ports = svc_spec.get("ports", [])
        cluster_ip = svc_spec.get("clusterIP")
        
        # Check endpoints mapping for this service
        key = f"{svc_ns}/{svc_name}"
        ep = endpoints_map.get(key)
        
        has_endpoints = False
        endpoint_addresses = []
        not_ready_addresses = []
        
        if ep:
            subsets = ep.get("subsets", [])
            for subset in subsets:
                addresses = subset.get("addresses", [])
                not_ready = subset.get("notReadyAddresses", [])
                
                for addr in addresses:
                    target_ref = addr.get("targetRef", {})
                    endpoint_addresses.append({
                        "ip": addr.get("ip"),
                        "node_name": addr.get("nodeName"),
                        "pod_name": target_ref.get("name"),
                        "pod_namespace": target_ref.get("namespace")
                    })
                    
                for addr in not_ready:
                    target_ref = addr.get("targetRef", {})
                    not_ready_addresses.append({
                        "ip": addr.get("ip"),
                        "node_name": addr.get("nodeName"),
                        "pod_name": target_ref.get("name"),
                        "pod_namespace": target_ref.get("namespace")
                    })
                    
            if len(endpoint_addresses) > 0:
                has_endpoints = True
                
        is_unhealthy = False
        issues = []
        
        # If the service defines a selector, we expect at least one ready endpoint address
        # (excluding ExternalName type which uses DNS, or headless services without pod selectors)
        if selector and svc_type != "ExternalName":
            if not ep or not has_endpoints:
                is_unhealthy = True
                if len(not_ready_addresses) > 0:
                    issues.append("Endpoints exist, but all backing pods are in a NOT ready state.")
                else:
                    issues.append("No active endpoints found. This indicates a selector mismatch or that backing pods do not exist/failed to start.")
                    
        # Check if ports are empty (ExternalName can have no ports in some patterns)
        if not ports and svc_type != "ExternalName":
            is_unhealthy = True
            issues.append("Service has no ports defined.")
            
        svc_summary = {
            "name": svc_name,
            "namespace": svc_ns,
            "type": svc_type,
            "cluster_ip": cluster_ip,
            "selector": selector,
            "ports": [
                {
                    "name": p.get("name"),
                    "port": p.get("port"),
                    "target_port": str(p.get("targetPort")),
                    "protocol": p.get("protocol")
                }
                for p in ports
            ],
            "healthy": not is_unhealthy,
            "issues": issues,
            "endpoints": endpoint_addresses,
            "not_ready_endpoints": not_ready_addresses
        }
        
        all_services.append(svc_summary)
        if is_unhealthy:
            problematic_services.append(svc_summary)
            
    logger.info(f"Network inspection complete. Problematic services: {len(problematic_services)}")
    
    return {
        "healthy": len(problematic_services) == 0,
        "problematic_services": problematic_services,
        "all_services": all_services
    }
