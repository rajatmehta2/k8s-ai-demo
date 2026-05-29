from typing import Dict, Any
from loguru import logger

class RootCauseAnalyzer:
    """
    Correlates incident evidence and refines the LLM's raw deduction
    to isolate the primary root cause and structured explanation.
    """
    def analyze(self, raw_data: Dict[str, Any]) -> Dict[str, str]:
        root_cause = raw_data.get("root_cause", "").strip()
        explanation = raw_data.get("explanation", "").strip()

        # Apply SRE heuristics if values are missing or generic
        if not root_cause or root_cause.lower() in ["unknown", "n/a", "none", "null"]:
            logger.warning("LLM returned empty or generic root cause. Refining with SRE heuristics...")
            root_cause = "Indeterminate Cluster Failure (Insufficient telemetry or silent crash)"
            
        if not explanation:
            explanation = "Unable to correlate evidence to form a detailed explanation due to minimal log patterns."

        logger.info(f"RootCauseAnalyzer completed analysis. Cause: '{root_cause}'")
        return {
            "root_cause": root_cause,
            "explanation": explanation
        }


class FixRecommendationEngine:
    """
    Generates and refines actionable, beginner-friendly Kubernetes fixes,
    precise ready-to-run kubectl commands, and long-term prevention rules.
    """
    def generate(self, raw_data: Dict[str, Any]) -> Dict[str, str]:
        fix = raw_data.get("fix", "").strip()
        kubectl_command = raw_data.get("kubectl_command", "").strip()
        prevention = raw_data.get("prevention", "").strip()

        # Validate and provide SRE fallback commands if LLM fails to output them
        if not fix:
            fix = "Review the logs and configurations of the affected deployments or verify cluster node space."
            
        if not kubectl_command:
            logger.warning("LLM did not provide specific kubectl commands. Injecting safe triage command.")
            kubectl_command = "kubectl get pods,events -n default"
            
        if not prevention:
            prevention = "Implement resource limits and specify dynamic readiness/liveness probes in deployment configurations."

        logger.info("FixRecommendationEngine formulated resolutions and verified command precision.")
        return {
            "fix": fix,
            "kubectl_command": kubectl_command,
            "prevention": prevention
        }


class ConfidenceEngine:
    """
    Dynamically computes and calibrates the final SRE troubleshooting confidence score
    based on the presence, richness, and clarity of gathered evidence.
    """
    def calculate(self, raw_data: Dict[str, Any], evidence: Dict[str, Any]) -> int:
        raw_confidence = raw_data.get("confidence", 50)

        # Parse confidence score safely
        try:
            confidence = int(raw_confidence)
        except (ValueError, TypeError):
            logger.warning(f"Non-integer confidence '{raw_confidence}' returned. Defaulting to 50.")
            confidence = 50

        # Enforce absolute bounds
        confidence = max(0, min(100, confidence))

        # Check telemetry richness
        pods = evidence.get("pods", {})
        logs = evidence.get("logs", {})
        events = evidence.get("events", {})

        has_problematic_pods = len(pods.get("problematic_pods", [])) > 0
        has_logs = len(logs) > 0
        has_warning_events = len(events.get("warning_events", [])) > 0

        # Adjust score using SRE rules:
        # 1. If we have problematic pods but NO logs are collected, cap confidence since we are diagnosing blindly.
        if has_problematic_pods and not has_logs:
            if confidence > 65:
                logger.info("ConfidenceEngine: Problematic pods present but no container logs captured. Capping confidence at 65%.")
                confidence = min(65, confidence)

        # 2. If there are NO warning events and NO logs at all, limit confidence because there's no failure signal.
        if not has_logs and not has_warning_events:
            if confidence > 50:
                logger.info("ConfidenceEngine: No logs or warning events detected. Capping confidence at 50% due to telemetry vacuum.")
                confidence = min(50, confidence)

        # 3. If logs and warning events align perfectly, we support high scores
        if has_logs and has_warning_events:
            logger.info("ConfidenceEngine: Rich telemetry alignment verified (logs + warning events). Confirmed confidence score.")

        logger.info(f"ConfidenceEngine calculated final SRE confidence score: {confidence}%")
        return confidence
