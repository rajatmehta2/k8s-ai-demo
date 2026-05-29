import asyncio
import httpx
from loguru import logger
from typing import Dict, Any

from app.core.config import settings

async def call_openrouter(system_prompt: str, user_prompt: str, max_retries: int = 3, initial_delay: float = 1.0) -> str:
    """
    Asynchronously invokes the OpenRouter API chat completions endpoint using HTTPX.
    
    Features:
    - Retries with exponential backoff for rate limits and server-side transient failures.
    - Strong timeout configurations to prevent hangs.
    - Safe secret usage via app settings.
    - Enforced JSON structure requests.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    if not settings.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY is not set or is empty in the environment configuration.")
        raise ValueError("Missing OpenRouter API Key. Please provide OPENROUTER_API_KEY in your environment.")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/rajatmehta2/k8s-ai-demo",
        "X-Title": "AI Kubernetes SRE Agent"
    }

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 3000
    }

    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"Calling OpenRouter API (Attempt {attempt}/{max_retries}) using model: {settings.openrouter_model}..."
            )
            
            # Setup HTTPX async client with a timeout of 45 seconds to accommodate slower LLM generations
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                # Check if the request was successful
                if response.status_code == 200:
                    response_data = response.json()
                    choices = response_data.get("choices", [])
                    if not choices:
                        raise ValueError("OpenRouter returned 200 OK but the response structure is missing the 'choices' list.")
                    
                    content = choices[0].get("message", {}).get("content", "")
                    if not content:
                        raise ValueError("OpenRouter choice exists but the 'message/content' string is empty.")
                    
                    logger.info("Successfully received valid response from OpenRouter API.")
                    return content
                
                # Handle error statuses
                logger.warning(
                    f"Received error response status {response.status_code} from OpenRouter on attempt {attempt}/{max_retries}."
                )
                
                # Retry on rate limiting (429) or transient gateway/server errors (500, 502, 503, 504)
                if response.status_code in [429, 500, 502, 503, 504]:
                    if attempt == max_retries:
                        response.raise_for_status()
                else:
                    # Non-retryable client errors (400, 401, 403, 404, etc.)
                    logger.error(f"Non-retryable HTTP status {response.status_code} encountered: {response.text}")
                    response.raise_for_status()

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning(f"HTTPX error encountered during attempt {attempt}/{max_retries}: {str(e)}")
            if attempt == max_retries:
                logger.error("Max retries reached. Raising HTTPX error.")
                raise e
        except Exception as e:
            logger.warning(f"Unexpected exception during attempt {attempt}/{max_retries}: {str(e)}")
            if attempt == max_retries:
                logger.error("Max retries reached. Raising unexpected exception.")
                raise e

        # Exponential backoff wait
        logger.info(f"Retrying OpenRouter call in {delay:.2f} seconds...")
        await asyncio.sleep(delay)
        delay *= 2.0

    raise RuntimeError("resilient_call_openrouter failed after exhausting all retry attempts.")
