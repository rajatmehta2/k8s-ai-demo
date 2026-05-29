from fastapi import APIRouter, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect
from loguru import logger
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import json
import asyncio

# Existing SRE Modules
from app.kubernetes.pod_inspector import inspect_pods
from app.kubernetes.logs_collector import collect_logs
from app.kubernetes.events_analyzer import analyze_events
from app.kubernetes.deployment_inspector import inspect_deployments
from app.kubernetes.network_inspector import inspect_network
from app.ai.agent import run_agent
from app.kubernetes.kubectl_executor import get_contexts, get_current_context
from app.models.diagnosis import KubernetesDiagnosis

# InsForge Emulated Services
from app.services.insforge import (
    register_user,
    login_user,
    verify_token,
    add_history_record,
    get_history_records
)

router = APIRouter()

# --- Pydantic Schemas for Requests/Responses ---
class UserAuth(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    status: str
    message: str
    token: Optional[str] = None

# --- Authentication Dependency ---
async def get_current_user(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    Dependency to authenticate request via JWT-like bearer token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Authentication failed: Missing or malformed Authorization header.")
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authentication token. Please sign in."
        )
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        logger.warning("Authentication failed: Token is invalid or expired.")
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid token. Please sign in again."
        )
    return payload


# --- Kubernetes Contexts & Error Translation Helpers ---

def get_friendly_kubernetes_error(stderr: str) -> str:
    """
    Translates raw kubectl errors to helpful, beginner-friendly messages.
    """
    stderr_lower = stderr.lower()
    if "refused" in stderr_lower or "unable to connect" in stderr_lower or "dial tcp" in stderr_lower:
        return (
            "Unable to connect to Kubernetes cluster.\n\n"
            "Please verify:\n"
            "- The kubeconfig file path is correct\n"
            "- The Kubernetes cluster is active and running (e.g. docker ps for kind/minikube)\n"
            "- Your network connectivity to the cluster api-server is open"
        )
    elif "no such file" in stderr_lower or "cannot find" in stderr_lower or "not found" in stderr_lower and "config" in stderr_lower:
        return (
            "Kubeconfig file is missing or inaccessible.\n\n"
            "Please verify:\n"
            "- The KUBECONFIG_PATH environment variable is configured correctly\n"
            "- The config file actually exists at that path"
        )
    elif "context" in stderr_lower and ("not found" in stderr_lower or "does not exist" in stderr_lower):
        return (
            "The selected Kubernetes context does not exist in your kubeconfig.\n\n"
            "Please verify:\n"
            "- The chosen cluster name is correct\n"
            "- Run 'kubectl config get-contexts' to check active contexts on your system"
        )
    elif "permission" in stderr_lower or "denied" in stderr_lower or "unauthorized" in stderr_lower:
        return (
            "Authentication or permission error when calling the Kubernetes API.\n\n"
            "Please verify:\n"
            "- You have the necessary role/permissions to get resources\n"
            "- Your current kubeconfig context has active user credentials"
        )
    else:
        return f"Kubernetes cluster query failed:\n{stderr.strip()}"

@router.get("/api/kubernetes/contexts")
async def get_kubernetes_contexts(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Fetches the available Kubernetes contexts/clusters from the local kubeconfig.
    """
    logger.info(f"Fetching contexts list requested by user: {user['email']}")
    contexts = get_contexts()
    current = get_current_context()
    return {
        "status": "success",
        "contexts": contexts,
        "current": current
    }


# --- Endpoints ---

@router.post("/api/auth/register", response_model=AuthResponse)
async def register(auth: UserAuth):
    """
    Registers a new user on the platform.
    """
    logger.info(f"Received registration request for email: {auth.email}")
    user = register_user(auth.email, auth.password)
    if not user:
        raise HTTPException(
            status_code=400,
            detail="User already exists or registration failed."
        )
    return {
        "status": "success",
        "message": "User registered successfully! Please log in."
    }

@router.post("/api/auth/login", response_model=AuthResponse)
async def login(auth: UserAuth):
    """
    Authenticates a user and returns a token.
    """
    logger.info(f"Received login request for email: {auth.email}")
    token = login_user(auth.email, auth.password)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )
    return {
        "status": "success",
        "message": "Login successful!",
        "token": token
    }

@router.get("/api/investigations/history")
async def history(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Fetches the logged-in user's previous investigation history.
    """
    logger.info(f"Fetching history records for user ID: {user['user_id']}")
    records = get_history_records(user["user_id"])
    return {
        "status": "success",
        "history": records
    }

@router.post("/investigate")
async def investigate_cluster(
    context: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Runs a full cluster-wide Kubernetes investigation and reasons about failures.
    Only authenticated users are allowed.
    Saves final reports to the SQLite history database.
    """
    logger.info(f"HTTP POST /investigate triggered by user: {user['email']} (target context: {context}). Starting SRE audit...")
    try:
        # Step 1: Collect Pod configurations
        pods_evidence = inspect_pods(context=context)
        
        # Check for immediate Kubernetes connection/kubeconfig error
        if pods_evidence.get("error"):
            friendly_err = get_friendly_kubernetes_error(pods_evidence["error"])
            raise HTTPException(status_code=400, detail=friendly_err)
        
        # Step 2: Collect logs for unhealthy pods
        logs_evidence = {}
        problematic_pods = pods_evidence.get("problematic_pods", [])
        if problematic_pods:
            for pod in problematic_pods:
                pod_name = pod["name"]
                namespace = pod["namespace"]
                unhealthy_containers = pod.get("unhealthy_containers", [])
                if unhealthy_containers:
                    for uc in unhealthy_containers:
                        c_name = uc.get("container_name")
                        log_key = f"{namespace}/{pod_name}/{c_name}"
                        logs_evidence[log_key] = collect_logs(pod_name=pod_name, namespace=namespace, container_name=c_name, context=context)
                else:
                    log_key = f"{namespace}/{pod_name}"
                    logs_evidence[log_key] = collect_logs(pod_name=pod_name, namespace=namespace, context=context)
        
        # Step 3: Collect Events
        events_evidence = analyze_events(context=context)
        if events_evidence.get("error"):
            friendly_err = get_friendly_kubernetes_error(events_evidence["error"])
            raise HTTPException(status_code=400, detail=friendly_err)
            
        # Step 4: Inspect Deployments
        deployments_evidence = inspect_deployments(context=context)
        if deployments_evidence.get("error"):
            friendly_err = get_friendly_kubernetes_error(deployments_evidence["error"])
            raise HTTPException(status_code=400, detail=friendly_err)
            
        # Step 5: Check Networking
        network_evidence = inspect_network(context=context)
        if network_evidence.get("error"):
            friendly_err = get_friendly_kubernetes_error(network_evidence["error"])
            raise HTTPException(status_code=400, detail=friendly_err)
        
        # Assemble complete evidence payload
        evidence = {
            "pods": pods_evidence,
            "logs": logs_evidence,
            "events": events_evidence,
            "deployments": deployments_evidence,
            "network": network_evidence
        }
        
        unhealthy_deployments = deployments_evidence.get("unhealthy_deployments", [])
        problematic_services = network_evidence.get("problematic_services", [])
        
        # Determine if cluster is completely healthy to bypass LLM
        is_healthy = len(problematic_pods) == 0 and len(unhealthy_deployments) == 0 and len(problematic_services) == 0
        
        if is_healthy:
            logger.info("Kubernetes cluster is fully healthy! Bypassing AI reasoning engine for speed and cost efficiency.")
            diagnosis = KubernetesDiagnosis(
                root_cause="No critical issues detected",
                explanation="No critical Kubernetes issues detected. Your pods, deployments, services, and networking configurations appear fully operational and healthy.",
                fix="No actions required. Keep up the good work!",
                kubectl_command="kubectl get all -A",
                prevention="Continue monitoring your deployments and set up Prometheus/Grafana alerts for proactive health checks.",
                confidence=100
            )
        else:
            # Step 6: AI agent SRE reasoning layer
            diagnosis = await run_agent(evidence)
        
        # Determine primary namespace
        primary_namespace = "default"
        if problematic_pods:
            primary_namespace = problematic_pods[0]["namespace"]
        
        # Save to history database
        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        add_history_record(
            user_id=user["user_id"],
            timestamp=timestamp_str,
            root_cause=diagnosis.root_cause,
            explanation=diagnosis.explanation,
            suggested_fix=diagnosis.fix,
            command=diagnosis.kubectl_command,
            namespace=primary_namespace,
            confidence=diagnosis.confidence,
            status="Completed"
        )
        
        return {
            "status": "success",
            "investigation": evidence,
            "diagnosis": {
                "root_cause": diagnosis.root_cause,
                "explanation": diagnosis.explanation,
                "suggested_fix": diagnosis.fix,
                "command": diagnosis.kubectl_command,
                "confidence": diagnosis.confidence
            }
        }
    except Exception as e:
        logger.exception("Unexpected error occurred during Kubernetes investigation or SRE reasoning.")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during cluster investigation: {str(e)}"
        )

# --- Real-Time Updates via WebSockets ---

@router.websocket("/api/investigate/ws")
async def investigate_ws(websocket: WebSocket):
    """
    WebSocket endpoint that streams progressive cluster troubleshooting steps
    in real-time and concludes with the diagnostic reasoning.
    """
    await websocket.accept()
    logger.info("New WebSocket connection established for real-time investigation.")
    
    user = None
    try:
        # Step 1: Authentication check via message token
        auth_msg = await websocket.receive_text()
        data = json.loads(auth_msg)
        token = data.get("token")
        context = data.get("context") # Optional target Kubernetes cluster context
        
        if not token:
            logger.warning("WS Auth failed: Token missing.")
            await websocket.send_json({"error": "Unauthorized: Authentication token is missing."})
            await websocket.close(code=1008)
            return
            
        user = verify_token(token)
        if not user:
            logger.warning("WS Auth failed: Invalid token.")
            await websocket.send_json({"error": "Unauthorized: Session expired or token is invalid."})
            await websocket.close(code=1008)
            return
            
        logger.info(f"WS authenticated successfully for user: {user['email']} (target context: {context})")
        await websocket.send_json({"status": "authenticated", "message": "Authentication successful!"})
        
        # Helper to send steps
        async def send_step(step_name: str, status: str, detail: Optional[str] = None):
            await websocket.send_json({
                "type": "step",
                "step": step_name,
                "status": status,
                "detail": detail
            })
            # Add short buffer for visual premium feedback
            await asyncio.sleep(0.3)
            
        # Step 2: Checking Pods
        await send_step("Checking Pods", "running")
        pods_evidence = inspect_pods(context=context)
        if pods_evidence.get("error"):
            friendly_err = get_friendly_kubernetes_error(pods_evidence["error"])
            await websocket.send_json({"type": "error", "error": friendly_err})
            await send_step("Checking Pods", "failed")
            return
        await send_step("Checking Pods", "success")
        
        # Step 3: Reading Logs
        await send_step("Reading Logs", "running")
        logs_evidence = {}
        problematic_pods = pods_evidence.get("problematic_pods", [])
        if problematic_pods:
            for pod in problematic_pods:
                pod_name = pod["name"]
                namespace = pod["namespace"]
                unhealthy_containers = pod.get("unhealthy_containers", [])
                if unhealthy_containers:
                    for uc in unhealthy_containers:
                        c_name = uc.get("container_name")
                        log_key = f"{namespace}/{pod_name}/{c_name}"
                        logs_evidence[log_key] = collect_logs(pod_name=pod_name, namespace=namespace, container_name=c_name, context=context)
                else:
                    log_key = f"{namespace}/{pod_name}"
                    logs_evidence[log_key] = collect_logs(pod_name=pod_name, namespace=namespace, context=context)
        await send_step("Reading Logs", "success")
        
        # Step 4: Analyzing Events
        await send_step("Analyzing Events", "running")
        events_evidence = analyze_events(context=context)
        if events_evidence.get("error"):
            friendly_err = get_friendly_kubernetes_error(events_evidence["error"])
            await websocket.send_json({"type": "error", "error": friendly_err})
            await send_step("Analyzing Events", "failed")
            return
        await send_step("Analyzing Events", "success")
        
        # Step 5: Inspecting Deployments
        await send_step("Inspecting Deployments", "running")
        deployments_evidence = inspect_deployments(context=context)
        if deployments_evidence.get("error"):
            friendly_err = get_friendly_kubernetes_error(deployments_evidence["error"])
            await websocket.send_json({"type": "error", "error": friendly_err})
            await send_step("Inspecting Deployments", "failed")
            return
        await send_step("Inspecting Deployments", "success")
        
        # Step 6: Checking Networking
        await send_step("Checking Networking", "running")
        network_evidence = inspect_network(context=context)
        if network_evidence.get("error"):
            friendly_err = get_friendly_kubernetes_error(network_evidence["error"])
            await websocket.send_json({"type": "error", "error": friendly_err})
            await send_step("Checking Networking", "failed")
            return
        await send_step("Checking Networking", "success")
        
        # Assemble evidence
        evidence = {
            "pods": pods_evidence,
            "logs": logs_evidence,
            "events": events_evidence,
            "deployments": deployments_evidence,
            "network": network_evidence
        }
        
        unhealthy_deployments = deployments_evidence.get("unhealthy_deployments", [])
        problematic_services = network_evidence.get("problematic_services", [])
        
        is_healthy = len(problematic_pods) == 0 and len(unhealthy_deployments) == 0 and len(problematic_services) == 0
        
        # Step 7: AI SRE Reasoning
        await send_step("AI Reasoning", "running")
        if is_healthy:
            logger.info("Kubernetes cluster is fully healthy! Bypassing AI reasoning engine in WS.")
            diagnosis = KubernetesDiagnosis(
                root_cause="No critical issues detected",
                explanation="No critical Kubernetes issues detected. Your pods, deployments, services, and networking configurations appear fully operational and healthy.",
                fix="No actions required. Keep up the good work!",
                kubectl_command="kubectl get all -A",
                prevention="Continue monitoring your deployments and set up Prometheus/Grafana alerts for proactive health checks.",
                confidence=100
            )
        else:
            diagnosis = await run_agent(evidence)
        await send_step("AI Reasoning", "success")
        
        # Step 8: Save to database
        primary_namespace = "default"
        if problematic_pods:
            primary_namespace = problematic_pods[0]["namespace"]
            
        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        add_history_record(
            user_id=user["user_id"],
            timestamp=timestamp_str,
            root_cause=diagnosis.root_cause,
            explanation=diagnosis.explanation,
            suggested_fix=diagnosis.fix,
            command=diagnosis.kubectl_command,
            namespace=primary_namespace,
            confidence=diagnosis.confidence,
            status="Completed"
        )
        
        # Step 9: Finalizing & Sending Diagnosis
        await send_step("Root Cause Found", "success")
        
        await websocket.send_json({
            "type": "result",
            "diagnosis": {
                "root_cause": diagnosis.root_cause,
                "explanation": diagnosis.explanation,
                "suggested_fix": diagnosis.fix,
                "command": diagnosis.kubectl_command,
                "confidence": diagnosis.confidence,
                "namespace": primary_namespace
            }
        })
        
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client.")
    except Exception as e:
        logger.exception("Error occurred during real-time WebSocket investigation.")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"An error occurred during cluster investigation: {str(e)}"
            })
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass
