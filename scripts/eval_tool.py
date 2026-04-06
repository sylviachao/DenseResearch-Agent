import time
import requests
import os
from dotenv import load_dotenv

# 1. Load Configurations
load_dotenv()

# Dify API Settings
# Ensure these are set in your .env file
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "your-dify-api-key-here")
DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1")

# Constraint Settings for G3 Task
# 3072 is the strict total session limit defined in the project requirements
TOKEN_LIMIT = 3072  
COST_PER_1K_TOKENS = 0.0001  # Estimated pricing for Gemini 2.5 Flash

def run_evaluation(query):
    """
    Executes a research query through the Dify API and evaluates performance 
    against G3 memory and token constraints.
    """
    print(f"\n[RESEARCH QUERY]: {query}")
    print("-" * 60)
    
    start_time = time.time()
    
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Payload for Dify Chat-Message API (Blocking mode for evaluation)
    payload = {
        "inputs": {},
        "query": query,
        "response_mode": "blocking",
        "user": "g3_evaluator_001"
    }
    
    try:
        response = requests.post(
            f"{DIFY_BASE_URL}/chat-messages", 
            headers=headers, 
            json=payload, 
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        
        latency = time.time() - start_time
        answer = result.get('answer', 'No response received.')
        
        # Extract metadata for precise token and resource tracking
        metadata = result.get('metadata', {})
        usage = metadata.get('usage', {})
        
        # Use actual usage data from API; fallback to estimation if metadata is missing
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', (len(answer) / 4) + 1000)
        
        # Track retrieval resources to verify RAG grounding
        sources = metadata.get('retriever_resources', [])
        
        estimated_cost = (total_tokens / 1000) * COST_PER_1K_TOKENS

        # Output Detailed Evaluation Metrics
        print(f"[RESPONSE SUMMARY]: {answer[:200].replace(chr(10), ' ')}...")
        
        print(f"\n[SYSTEM METRICS]:")
        print(f"  - Latency: {latency:.2f} seconds")
        print(f"  - Retrieval: {len(sources)} chunks utilized from Knowledge Base")
        print(f"  - Prompt Tokens (Input): {prompt_tokens}")
        print(f"  - Completion Tokens (Output): {completion_tokens}")
        print(f"  - Total Session Tokens: {total_tokens}")
        print(f"  - Calculated Session Cost: ${estimated_cost:.6f}")

        # G3 Constraint Validation Logic
        print(f"\n[CONSTRAINT VALIDATION]:")
        if total_tokens <= TOKEN_LIMIT:
            print(f"  - Status: PASSED (Under {TOKEN_LIMIT} token limit)")
        else:
            print(f"  - Status: FAILED (Exceeded {TOKEN_LIMIT} token limit)")
        print("-" * 60)

    except Exception as e:
        print(f"[ERROR]: Evaluation failed: {str(e)}")

def main():
    print("=" * 70)
    print("BINOC G3 INVESTMENT AGENT - SYSTEM PERFORMANCE EVALUATOR")
    print("=" * 70)

    # Standardized test cases for Financial Research Analysis
    test_queries = [
        "What are the specific revenue growth projections for Nvidia in FY2026?",
        "Identify key risks mentioned in the latest earnings call regarding AI hardware demand.",
        "Summarize the FCF (Free Cash Flow) trend based on the provided atomic facts."
    ]

    if DIFY_API_KEY == "your-dify-api-key-here" or not DIFY_API_KEY:
        print("Configuration Error: Please provide a valid DIFY_API_KEY in the .env file.")
        return

    for i, query in enumerate(test_queries):
        print(f"\n[TEST CASE {i+1}/{len(test_queries)}]")
        run_evaluation(query)
        # Small delay to respect rate limits and ensure log readability
        time.sleep(1)

if __name__ == "__main__":
    main()