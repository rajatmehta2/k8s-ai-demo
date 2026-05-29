import json
from typing import Dict, Any
from loguru import logger

from app.models.diagnosis import KubernetesDiagnosis
from app.ai.prompt_builder import build_troubleshooting_prompt
from app.ai.client import call_openrouter
from app.ai.engines import RootCauseAnalyzer, FixRecommendationEngine, ConfidenceEngine

def clean_and_parse_json(text: str) -> Dict[str, Any]:
    """
    Cleans markdown wrappers and extracts a valid JSON dictionary from LLM text responses.
    Features robust truncated JSON recovery to close open brackets/braces/quotes.
    """
    cleaned = text.strip()
    
    # Remove markdown code block fences if present
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
        
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
        
    cleaned = cleaned.strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"Standard JSON parsing failed: {str(e)}. Attempting substring JSON extraction...")
        
        # Locate the first '{' and last '}' to handle conversational prefixes/suffixes
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            try:
                substring = cleaned[start:end+1]
                parsed = json.loads(substring)
                logger.info("Successfully recovered and parsed JSON via substring extraction.")
                return parsed
            except json.JSONDecodeError:
                pass
                
        # Truncated JSON recovery fallback
        # Let's try to repair the JSON by closing open quotes, list brackets, and object braces
        logger.warning("Attempting truncated JSON recovery...")
        repaired = cleaned
        
        # Close open string quotes
        # We count the number of quotes. If odd, append a quote.
        if repaired.count('"') % 2 != 0:
            repaired += '"'
            
        # Count open braces/brackets
        open_braces = repaired.count('{') - repaired.count('}')
        open_brackets = repaired.count('[') - repaired.count(']')
        
        for _ in range(open_brackets):
            repaired += ']'
        for _ in range(open_braces):
            repaired += '}'
            
        try:
            parsed = json.loads(repaired)
            logger.info("Successfully repaired and parsed truncated JSON.")
            return parsed
        except json.JSONDecodeError:
            pass
            
        # If repair fails, let's try a regex key-value extractor for safety
        import re
        extracted = {}
        target_keys = ["root_cause", "explanation", "fix", "kubectl_command", "prevention", "confidence"]
        for key in target_keys:
            # Matches "key": "value" (captures value)
            match = re.search(rf'"{key}"\s*:\s*"([^"]*)"', cleaned)
            if match:
                extracted[key] = match.group(1)
            else:
                # Matches integer confidence
                if key == "confidence":
                    match_int = re.search(r'"confidence"\s*:\s*(\d+)', cleaned)
                    if match_int:
                        extracted[key] = int(match_int.group(1))
                    else:
                        extracted[key] = 80
                else:
                    extracted[key] = "Not fully generated due to API response limit."
                    
        if any(extracted.values()):
            logger.info("Successfully extracted partial key-values from malformed/truncated JSON.")
            return extracted
            
        raise ValueError(f"Response content could not be parsed as valid JSON: {text[:200]}...")

async def run_agent(evidence: Dict[str, Any]) -> KubernetesDiagnosis:
    """
    Orchestrates the AI Kubernetes SRE Reasoning flow:
    1. Compiles the raw Kubernetes incident evidence into a structured SRE prompt.
    2. Invokes OpenRouter resiliently.
    3. Robustly parses and extracts the JSON output.
    4. Applies Root Cause, Fix Recommendation, and Confidence evaluation engines.
    5. Returns a structured KubernetesDiagnosis report, providing a graceful fallback on failure.
    """
    logger.info("AI Kubernetes Agent triggered for SRE incident reasoning...")
    
    try:
        # Step 1: Build the prompts
        system_prompt, user_prompt = build_troubleshooting_prompt(evidence)
        
        # Step 2: Resiliently invoke the OpenRouter LLM
        raw_response = await call_openrouter(system_prompt, user_prompt)
        
        # Step 3: Parse JSON safely
        raw_data = clean_and_parse_json(raw_response)
        
        # Step 4: Run SRE Reasoning Engines
        analyzer = RootCauseAnalyzer()
        recommender = FixRecommendationEngine()
        confidence_engine = ConfidenceEngine()
        
        analysis = analyzer.analyze(raw_data)
        recommendation = recommender.generate(raw_data)
        confidence = confidence_engine.calculate(raw_data, evidence)
        
        # Step 5: Assemble the validated diagnosis report
        diagnosis = KubernetesDiagnosis(
            root_cause=analysis["root_cause"],
            explanation=analysis["explanation"],
            fix=recommendation["fix"],
            kubectl_command=recommendation["kubectl_command"],
            prevention=recommendation["prevention"],
            confidence=confidence
        )
        
        logger.info("AI Kubernetes Agent successfully generated diagnostic SRE report.")
        return diagnosis

    except Exception as e:
        logger.exception("AI Kubernetes SRE Reasoning Engine encountered a failure.")
        
        # SRE Safe Fallback Report
        fallback_diagnosis = KubernetesDiagnosis(
            root_cause="Diagnostic Analysis Interrupted",
            explanation=(
                f"The AI SRE Reasoning Engine encountered an error while processing cluster evidence or calling the LLM API: {str(e)}. "
                "Please verify that the OpenRouter API key is active and connection timeouts are resolved."
            ),
            fix="Diagnose backend cluster health manually using standard kubectl commands.",
            kubectl_command="kubectl get pods -n default -o wide && kubectl get events --sort-by='.metadata.creationTimestamp' -n default",
            prevention="Check environment variables for OPENROUTER_API_KEY and verify API endpoint connectivity.",
            confidence=0
        )
        
        logger.warning("AI Agent returned standard graceful SRE fallback report.")
        return fallback_diagnosis
