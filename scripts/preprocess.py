import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Initialization
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_GENAI_API_KEY"))
model_name = os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")

# --- Global Configuration ---
USER_CONFIG = {
    "total_token_limit": 2048,
    "max_prompt_chars": 800,  # Suggested character limit for System Prompt resources
}

# --- Constraints for Data Chunking ---
MAX_CHUNK_CHARS = 700      
CHUNK_OVERLAP_CHARS = 100   
TAIL_MERGE_THRESHOLD = 300  
OBESE_THRESHOLD = 850       # Threshold to trigger recursive splitting (~200-250 Tokens)

class PromptManager:
    """
    Manages prompt resources and token budgeting to prevent redundant I/O.
    """
    def __init__(self, config):
        self.config = config
        self.profile = self._load_resource("research_profile")
        self.rules = self._load_resource("fact_extraction_rules")
        self._report_budget()

    def _load_resource(self, name):
        path = f"prompts/{name}.txt"
        os.makedirs("prompts", exist_ok=True)
        if not os.path.exists(path):
            content = f"Task: Extract atomic facts from financial text for {name}."
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return content
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def _report_budget(self):
        total_chars = len(self.profile) + len(self.rules)
        est_tokens = total_chars // 4
        # Reserve 500 tokens for model output
        data_margin = self.config["total_token_limit"] - est_tokens - 500 
        
        print("-" * 40)
        print("G3 SYSTEM: Token Budget Audit")
        print(f"  - System Prompt:   ~{est_tokens} tokens")
        print(f"  - Available Margin: ~{data_margin} tokens (Safe for Top-K 4-6)")
        print("-" * 40)

    def get_system_prompt(self):
        return f"{self.profile}\n\n### EXTRACTION RULES\n{self.rules}"

def recursive_token_safe_split(text, max_chars=MAX_CHUNK_CHARS, overlap=CHUNK_OVERLAP_CHARS):
    """
    Hierarchical splitting to protect financial decimals and semantic structure.
    """
    separators = ["\n\n", "\n", ". ", " "]
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + max_chars, text_len)
        if end == text_len:
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
        start = actual_end - overlap
        
    if len(chunks) > 1 and len(chunks[-1]) < TAIL_MERGE_THRESHOLD:
        tail = chunks.pop()
        chunks[-1] = (chunks[-1] + "\n\n[APPENDED]: " + tail).strip()
        
    return chunks

def summarize_chunk(model, chunk_text, metadata, system_prompt):
    """
    Initial Refinement: Converts raw text into a list of atomic facts.
    """
    full_prompt = f"{system_prompt}\n\n### INPUT\nMetadata: {metadata}\nText:\n{chunk_text}"
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Error in summarization: {e}"

def smart_split_obese_chunk(model, bulky_text, metadata):
    """
    Recursive Decoupling: Splits oversized fact lists into logical Parts (A/B).
    """
    split_prompt = f"""
    The extracted facts for {metadata} are too long for the token budget. 
    Please split them into TWO logically distinct sections (e.g., Bull Case vs Bear Case, or Actuals vs Projections).
    
    Requirements:
    1. Do not lose any financial data or decimals.
    2. Maintain [Actual], [Projected] tags for each point.
    3. Output format must use ---SPLIT--- as the ONLY separator.
    
    ### BULKY TEXT:
    {bulky_text}
    """
    try:
        response = model.generate_content(split_prompt)
        parts = response.text.split("---SPLIT---")
        return [p.strip() for p in parts if len(p.strip()) > 30]
    except Exception:
        return [bulky_text]

def process_file(file_path, output_dir, prompt_manager):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    filename = os.path.basename(file_path)
    model = genai.GenerativeModel(model_name)
    
    # Metadata extraction (One-time per file)
    try:
        meta_prompt = f"Identify Company and Report Status. Format: [Company | Status]. Text: {content[:800]}"
        metadata = model.generate_content(meta_prompt).text.strip()
    except:
        metadata = "[Nvidia | FY2025 Analysis]"

    print(f"Processing file: {filename}")
    
    system_prompt = prompt_manager.get_system_prompt()
    raw_chunks = recursive_token_safe_split(content)
    final_processed_chunks = []

    for i, chunk in enumerate(raw_chunks):
        print(f"  - Fact extraction for chunk {i+1}/{len(raw_chunks)}...")
        processed_text = summarize_chunk(model, chunk, metadata, system_prompt)
        
        # Detection and Recursive Splitting Logic
        if len(processed_text) > OBESE_THRESHOLD:
            print(f"    [ALERT] Obese chunk detected ({len(processed_text)} chars). Splitting...")
            sub_parts = smart_split_obese_chunk(model, processed_text, metadata)
            for sub_idx, sub_content in enumerate(sub_parts):
                tag = f" (Part {chr(65+sub_idx)})"
                final_processed_chunks.append(f"### Chunk {i+1}{tag} [{metadata}]\n{sub_content}")
            print(f"    [DONE] Successfully split into {len(sub_parts)} sub-chunks.")
        else:
            final_processed_chunks.append(f"### Chunk {i+1} [{metadata}]\n{processed_text}")

    output_path = os.path.join(output_dir, filename.replace(".txt", ".md"))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(final_processed_chunks))
    print(f"Success: {output_path}\n")

def main():
    raw_dir = "data/raw"
    processed_dir = "data/processed"
    os.makedirs(processed_dir, exist_ok=True)
    
    try:
        pm = PromptManager(USER_CONFIG)
    except Exception as e:
        print(f"Initialization Error: {e}")
        return

    files = [f for f in os.listdir(raw_dir) if f.endswith(".txt")]
    if not files:
        print(f"No files found in {raw_dir}. Please add .txt reports.")
        return

    for file in files:
        process_file(os.path.join(raw_dir, file), processed_dir, pm)

if __name__ == "__main__":
    main()