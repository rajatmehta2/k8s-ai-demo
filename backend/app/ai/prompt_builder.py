import json
from typing import Dict, Any, Tuple
from loguru import logger

def build_troubleshooting_prompt(evidence: Dict[str, Any]) -> Tuple[str, str]:
    """
    Compiles raw Kubernetes investigation evidence into a highly structured prompt
    instructing the LLM to behave like a Senior Kubernetes SRE.
    
    Returns:
        (system_prompt, user_prompt)
    """
    logger.info("Building Kubernetes troubleshooting prompt from gathered evidence payload...")

    system_prompt = (
        "You are a Senior Kubernetes Site Reliability Engineer (SRE) who specializes in rapid cluster incident resolution.\n"
        "Your task is to analyze the provided Kubernetes diagnostic evidence to identify the root cause, "
        "explain the failure, recommend practical fixes, and provide precise kubectl commands.\n\n"
        
        "CRITICAL RULES FOR YOUR ANALYSIS:\n"
        "1. BE A DETECTIVE: Do not blindly summarize logs or repeat what is already obvious. Correlate logs, warning events, "
        "deployment conditions, and service selector mismatches to find the true root cause.\n"
        "2. PRACTICAL & ACTIONABLE: Your suggested fix must be direct, beginner-friendly, and specific. Avoid generic recommendations "
        "like 'consult documentation' or 'check network connection'.\n"
        "3. PRECISION KUBECTL COMMANDS: The kubectl commands must be valid, concrete, and ready-to-run. Include namespace flags "
        "if a specific namespace is affected.\n"
        "4. PREVENTATIVE CARE: Suggest realistic preventative measures (e.g., resource limits, readiness probes, configmaps, liveness probes).\n"
        "5. CONFIDENCE EVALUATION: Provide a confidence score (integer from 0 to 100) based on evidence alignment: \n"
        "   - High confidence (80-100%): Log patterns match pod states perfectly, warning events confirm the failure vector, "
        "or service selectors are missing matching pods.\n"
        "   - Medium confidence (50-79%): Logs show errors but evidence is partial, or pods are crashing for less obvious runtime reasons.\n"
        "   - Low confidence (0-49%): No definitive errors found in logs or events; reasoning is circumstantial.\n\n"
        
        "OUTPUT FORMAT CONSTRAINTS:\n"
        "You MUST respond ONLY with a raw, valid JSON object matching the schema below. Do not include markdown "
        "formatting like '```json' wrapper, do not include any conversational preamble, intro, or outro text. "
        "Your output must be directly parseable by json.loads().\n\n"
        
        "JSON SCHEMA:\n"
        "{\n"
        '  "root_cause": "A concise, high-level summary of the primary root cause",\n'
        '  "explanation": "Detailed SRE explanation of how logs, events, and pod states match up, explaining the sequence of events",\n'
        '  "fix": "Actionable, practical suggested fix to resolve the issue",\n'
        '  "kubectl_command": "Specific kubectl command(s) to fix or investigate further",\n'
        '  "prevention": "Practical prevention recommendation or long-term advice to avoid this failure",\n'
        '  "confidence": 92\n'
        "}\n"
    )

    # Clean and isolate evidence sections
    pods = evidence.get("pods", {})
    logs = evidence.get("logs", {})
    events = evidence.get("events", {})
    deployments = evidence.get("deployments", {})
    network = evidence.get("network", {})

    user_prompt = (
        "### KUBERNETES INCIDENT EVIDENCE ###\n\n"
        "Analyze the following cluster-wide telemetry and provide your diagnosis.\n\n"
        
        "--- [1. PODS STATUS & LIFECYCLE] ---\n"
        f"{json.dumps(pods, indent=2)}\n\n"
        
        "--- [2. TARGETED CONTAINER LOGS] ---\n"
        f"{json.dumps(logs, indent=2)}\n\n"
        
        "--- [3. WARNING EVENTS] ---\n"
        f"{json.dumps(events, indent=2)}\n\n"
        
        "--- [4. DEPLOYMENTS CONDITION & HEALTH] ---\n"
        f"{json.dumps(deployments, indent=2)}\n\n"
        
        "--- [5. SERVICES & NETWORKING FINDINGS] ---\n"
        f"{json.dumps(network, indent=2)}\n\n"
        
        "Please generate your SRE diagnosis JSON report now:"
    )

    return system_prompt, user_prompt
