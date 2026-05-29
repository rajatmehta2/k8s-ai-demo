import json
from typing import Dict, Any, List, Optional
from loguru import logger
from app.kubernetes.kubectl_executor import execute_kubectl

def analyze_events(context: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves cluster-wide events and parses out warning events and critical failure logs.
    """
    logger.info("Starting Events analysis...")
    result = execute_kubectl(["get", "events", "-A", "-o", "json"], context=context)
    
    if not result.success:
        logger.error(f"Failed to get events: {result.stderr}")
        return {
            "error": result.stderr,
            "warning_events": [],
            "critical_findings": []
        }
        
    try:
        data = json.loads(result.stdout)
    except Exception as e:
        logger.error(f"Failed to parse events JSON: {e}")
        return {
            "error": f"Failed to parse JSON: {str(e)}",
            "warning_events": [],
            "critical_findings": []
        }
        
    items = data.get("items", [])
    warning_events = []
    critical_findings = []
    
    # Target reasons to highlight
    critical_reasons = {
        "FailedScheduling", "BackOff", "FailedMount", "FailedPull", 
        "ErrImagePull", "Unhealthy", "FailedCreate", "FailedDelete", 
        "FailedPostStartHook", "FailedPreStopHook", "OOMKilling"
    }
    
    for item in items:
        event_type = item.get("type", "Normal")
        reason = item.get("reason", "")
        message = item.get("message", "")
        
        involved_obj = item.get("involvedObject", {})
        obj_kind = involved_obj.get("kind", "")
        obj_name = involved_obj.get("name", "")
        obj_namespace = involved_obj.get("namespace", "default")
        
        count = item.get("count", 1)
        # Handle cases where count is not an integer or is 0/null
        try:
            count = int(count)
        except (ValueError, TypeError):
            count = 1
            
        last_timestamp = item.get("lastTimestamp") or item.get("metadata", {}).get("creationTimestamp")
        
        event_summary = {
            "type": event_type,
            "reason": reason,
            "message": message,
            "object_kind": obj_kind,
            "object_name": obj_name,
            "namespace": obj_namespace,
            "count": count,
            "last_seen": last_timestamp
        }
        
        # We classify it as important if it's Warning or if its reason is in our target reasons
        if event_type == "Warning" or reason in critical_reasons:
            warning_events.append(event_summary)
            
            # Create a simple, human-readable summary of the event finding
            finding_msg = f"[{obj_kind}] {obj_namespace}/{obj_name} reported {reason}: {message} (occurred {count} times)"
            critical_findings.append({
                "namespace": obj_namespace,
                "object": f"{obj_kind}/{obj_name}",
                "reason": reason,
                "message": message,
                "count": count,
                "last_seen": last_timestamp,
                "summary": finding_msg
            })
            
    logger.info(f"Events analysis complete. Found {len(warning_events)} warning events.")
    
    return {
        "total_events_checked": len(items),
        "warning_events_count": len(warning_events),
        "warning_events": warning_events[:50],  # Return up to 50 warning events to keep it readable
        "critical_findings": critical_findings
    }
