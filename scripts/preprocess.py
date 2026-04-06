import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Initialization
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_GENAI_API_KEY"))
model_name = os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")

# --- Strict 2,048 Token Budget Strategy ---
# 1,400 chars roughly equals 350-400 tokens.
MAX_CHUNK_CHARS = 1400      
CHUNK_OVERLAP_CHARS = 200   
# If the last chunk is smaller than this, merge it backward to maintain context.
TAIL_MERGE_THRESHOLD = 800  

SEPARATORS = ["\n\n", "\n", ". ", " "] 

def get_metadata(text):
    """Extract context metadata for chunk grounding"""
    model = genai.GenerativeModel(model_name)
    prompt = f"Extract 'Company Name' and 'Report Date/Year'. Format: [Company | Date]. Text: {text[:500]}"
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "[Unknown Entity | Unknown Date]"

def recursive_token_safe_split(text, max_chars=MAX_CHUNK_CHARS, overlap=CHUNK_OVERLAP_CHARS):
    """Hierarchical split to protect numbers and maintain structural logic"""
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
        for sep in SEPARATORS:
            pos = chunk_slice.rfind(sep)
            if pos != -1:
                split_pos = start + pos + len(sep)
                break
        
        actual_end = split_pos if split_pos != -1 else end
        chunks.append(text[start:actual_end].strip())
        start = actual_end - overlap
        
    # --- Tail-Merge: Combine small final fragment with the previous chunk ---
    if len(chunks) > 1 and len(chunks[-1]) < TAIL_MERGE_THRESHOLD:
        tail = chunks.pop()
        chunks[-1] = (chunks[-1] + "\n\n[APPENDED DATA]: " + tail).strip()
        
    return chunks

def summarize_chunk(chunk_text, metadata):
    """Data Refiner: Compresses text into high-density Atomic Facts"""
    model = genai.GenerativeModel(model_name)
    prompt = f"""
    Context: {metadata} (Reference Date)
    Role: Senior Investment Analyst
    Task: Convert the text into a bulleted list of 'Atomic Facts'.
    
    Strict Constraints:
    1. Output MUST be < 350 tokens.
    2. Numerical Integrity: Never split or round numbers (e.g., 369.42 stays 369.42).
    3. Timeline Sensitivity: Explicitly label 'FY2025 (Actual)', 'FY2026 (Projected)', or 'NTM'.
    4. Format: '- [Fact] [Context/Source]'
    5. Deduplication: If data repeats within the text, merge into one fact.
    
    Text:
    {chunk_text}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def process_file(file_path, output_dir):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    filename = os.path.basename(file_path)
    metadata = get_metadata(content)
    print(f"Processing: {filename} | Metadata: {metadata}")

    # Split with tail-merge logic
    raw_chunks = recursive_token_safe_split(content)
    final_processed_chunks = []

    for i, chunk in enumerate(raw_chunks):
        # ALL chunks now pass through the summarizer for consistency
        print(f"  - Summarizing chunk {i+1}/{len(raw_chunks)}...")
        processed_text = summarize_chunk(chunk, metadata)
        
        # Consistent output format for Dify Knowledge Base
        final_processed_chunks.append(f"### Chunk {i+1} Context: {metadata}\n{processed_text}")

    output_filename = filename.replace(".txt", ".md")
    with open(os.path.join(output_dir, output_filename), "w", encoding="utf-8") as f:
        f.write(f"# Processed Research: {filename}\n\n")
        f.write("\n\n---\n\n".join(final_processed_chunks))
    
    print(f"Success! Saved to {output_dir}/{output_filename}\n")

def main():
    raw_dir = "data/raw"
    processed_dir = "data/processed"
    os.makedirs(processed_dir, exist_ok=True)
    
    files = [f for f in os.listdir(raw_dir) if f.endswith(".txt")]
    if not files:
        print(f"Warning: No files found in {raw_dir}")
        return

    for file in files:
        process_file(os.path.join(raw_dir, file), processed_dir)

if __name__ == "__main__":
    main()