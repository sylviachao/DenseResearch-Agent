import os
import time
import yaml
import google.generativeai as genai
from dotenv import load_dotenv
from google.api_core import exceptions
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 1. Initialization and Environment Setup
# ==========================================
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_GENAI_API_KEY"))

# --- Global Configurations for Free Tier Constraints ---
MAX_CHUNK_CHARS = 1200      # Optimized to reduce API calls while maintaining context
CHUNK_OVERLAP_CHARS = 150   # Ensures no data points are lost at split boundaries
OBESE_THRESHOLD = 750       # Threshold for local splitting if AI output is too dense

# Define different security levels based on domain sensitivity
SAFETY_CONFIGS = {
    "finance_extraction": {
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    },
    "legal_compliance": {
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    },
    "default": {
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }
}

# ==========================================
# 2. Core Component: PromptManager
# ==========================================
class PromptManager:
    """
    Manages loading of system roles (Markdown) and domain-specific skills (YAML).
    """
    def __init__(self, skill_type="finance"):
        self.skill_type = skill_type
        # Load the base persona/role from prompts folder
        self.profile = self._load_resource("prompts", "research_profile", ".md")
        # Load the specific extraction schema from skills folder
        self.skill_data = self._load_skill(skill_type)

    def _load_resource(self, folder, name, ext):
        path = os.path.join(folder, f"{name}{ext}")
        if not os.path.exists(path):
            print(f"[Warning] Resource not found: {path}. Using fallback profile.")
            return "# Role: Senior Analyst\nTask: Extract facts precisely."
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def _load_skill(self, skill_type):
        path = os.path.join("skills", f"{skill_type}.yaml")
        if not os.path.exists(path):
            print(f"[Warning] Skill YAML not found: {path}. Using default slots.")
            return {"slots": "General data points", "rules": ["Maintain precision"]}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def get_combined_instruction(self):
        """
        Synthesizes the Markdown role and YAML schema into a structured system prompt.
        """
        skill_yaml_str = yaml.dump(self.skill_data, allow_unicode=True, sort_keys=False)
        return (
            f"{self.profile}\n\n"
            f"### EXTRACTION_SKILL_SCHEMA (STRICT COMPLIANCE REQUIRED):\n"
            f"```yaml\n{skill_yaml_str}```\n"
        )

# ==========================================
# 3. Text Processing Utilities
# ==========================================
def recursive_token_safe_split(text, max_chars=MAX_CHUNK_CHARS, overlap=CHUNK_OVERLAP_CHARS):
    """
    Physical splitting: Prioritizes breaking at newlines or periods to preserve sentence integrity.
    """
    separators = ["\n\n", "\n", ". ", " "]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end == len(text):
            chunks.append(text[start:])
            break
        
        chunk_slice = text[start:end]
        split_pos = -1
        for sep in separators:
            pos = chunk_slice.rfind(sep)
            if pos != -1:
                split_pos = start + pos + len(sep)
                break
        
        actual_end = split_pos if split_pos != -1 else end
        chunks.append(text[start:actual_end].strip())
        # Move back by overlap to ensure continuity
        start = actual_end - overlap
    return chunks

def summarize_chunk(model, chunk_text, metadata,pm, is_first=False):
    """
    Handles API call with XML tag isolation for better instruction following in Flash models.
    """
# Get safety settings for the current skill, fallback to default
    current_safety = SAFETY_CONFIGS.get(pm.skill_type, SAFETY_CONFIGS["default"])    
    full_prompt = (
        f"{pm.get_combined_instruction()}\n\n"
        f"<Context>\nMetadata: {metadata}\n</Context>\n\n"
        f"<SourceText>\n{chunk_text}\n</SourceText>\n\n"
        f"RESULT (Atomic Facts Only):"
    )

    # if is_first:
    #     print("\n" + "-"*30 + " DEBUG: PROMPT STRUCTURE " + "-"*30)
    #     print(full_prompt[:800] + "...") # Preview the prompt without flooding console
    #     print("-"*85 + "\n")

    for attempt in range(3):
        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    # max_output_tokens=800,
                    temperature=0.1 # Low temperature for deterministic financial extraction
                ),
                safety_settings=current_safety
            )
            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else "Unknown"
                print(f"    [SAFETY] Chunk blocked. Reason: {finish_reason}")
                return f"[DATA_BLOCKED] Content triggered safety filters (Reason: {finish_reason})."
            
            return response.text.strip()
        except exceptions.ResourceExhausted:
            # Linear backoff for Free Tier rate limits
            wait = 60 * (attempt + 1)
            print(f"    [QUOTA] Rate limit hit. Sleeping {wait}s...")
            time.sleep(wait)
        except Exception as e:
            return f"Error: {e}"
    return "Error: Maximum retries reached."

# -----------------------------------------------------------------
# Helper: safe_split_text
# Ensures high-density facts are split into chunks under 800 chars 
# while preserving Metadata Headers for RAG grounding.
# -----------------------------------------------------------------
def safe_split_text(text, metadata, chunk_idx, threshold=800):
    """
    If the extracted facts exceed the character threshold, split them at the 
    nearest newline and prepend the metadata header to each part.
    """
    if len(text) <= threshold:
        return [f"### Chunk {chunk_idx} [{metadata}]\n{text}"]

    # Find the midpoint to initiate splitting
    mid = len(text) // 2
    # Search for the nearest newline character around the midpoint to avoid cutting sentences
    split_pos = text.rfind('\n', 0, mid + 100)
    
    if split_pos == -1: # Fallback to period if no newline is found
        split_pos = text.rfind('. ', 0, mid + 100)
    if split_pos == -1: # Hard split as a last resort
        split_pos = mid

    part_a = text[:split_pos].strip()
    part_b = text[split_pos:].strip()

    # Ensure Part B maintains the list structure if it starts mid-sentence
    if not part_b.startswith('-'):
        part_b = f"- {part_b}"

    # Return formatted sections with inherited metadata
    results = [
        f"### Chunk {chunk_idx} (Part A) [{metadata}]\n{part_a}",
        f"### Chunk {chunk_idx} (Part B) [{metadata}]\n{part_b}"
    ]
    return results

def get_model():
    # Default to gemini-2.5-flash for high token window and speed
    default_model = "gemini-2.5-flash"
    env_model = os.getenv("GOOGLE_GENAI_MODEL")

    try:
        if env_model:
            return genai.GenerativeModel(env_model)
        else:
            return genai.GenerativeModel(default_model)
    except Exception:
        print(f"[WARN] Model '{env_model}' not available. Falling back to {default_model}.")
        return genai.GenerativeModel(default_model)

# ==========================================
# 4. Main Processing Pipeline
# ==========================================
def process_file(file_path, output_dir, pm, overwrite=False):
    filename = os.path.basename(file_path)
    output_path = os.path.join(output_dir, filename.replace(".txt", ".md"))

    if os.path.exists(output_path) and not overwrite:
        print(f"Skipping {filename}: Already exists.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    model = get_model()
    
    # Extract Metadata: Identifying [Company | Date] once per file to save tokens
    try:
        meta_prompt = f"Identify only '[Company | Date]' from the first 500 chars: {content[:500]}"
        metadata = model.generate_content(meta_prompt).text.strip()
        time.sleep(5) # Cooldown for Free Tier RPM
    except:
        metadata = "[Analysis]"

    print(f"Processing: {filename} | Mode: {pm.skill_type}")
    raw_chunks = recursive_token_safe_split(content)
    processed_results = []

    for i, chunk in enumerate(raw_chunks):
        print(f"  - Extraction {i+1}/{len(raw_chunks)}...")
        facts = summarize_chunk(model, chunk, metadata, pm, is_first=(i==0))
        final_sections = safe_split_text(facts, metadata, i+1, threshold=OBESE_THRESHOLD)
        processed_results.extend(final_sections)
        # Mandatory delay for Free Tier (staying under ~15 requests per minute)
        time.sleep(12) 

    # Save finalized results as Markdown with clear section separators
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(processed_results))
    print(f"Success: {output_path}\n")

def main():
    raw_dir = "data/raw"
    processed_dir = "data/processed"
    os.makedirs(processed_dir, exist_ok=True)
    
    skill_type = "finance_extraction" 
    pm = PromptManager(skill_type)
    files = [f for f in os.listdir(raw_dir) if f.endswith(".txt")]
    if not files: return

    # Overwrite check
    existing = [f for f in files if os.path.exists(os.path.join(processed_dir, f.replace(".txt", ".md")))]
    overwrite_all = False
    if existing:
        choice = input(f"\n[!] Found {len(existing)} processed files. Overwrite ALL? (y/N): ").lower()
        overwrite_all = (choice == 'y')

    for file in files:
        process_file(os.path.join(raw_dir, file), processed_dir, pm, overwrite=overwrite_all)

if __name__ == "__main__":
    main()