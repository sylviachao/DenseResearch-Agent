import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Initialization. here use gemini as the testing flash model
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_GENAI_API_KEY"))
model_name = os.getenv("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")

# Configuration Constants Optimized for 2,048 Token Constraint
# Target: 400 tokens per chunk * Top_K(4) = 1,600 tokens (Leaving 448 for Prompt/Meta)
MAX_CHUNK_SIZE = 400     # Target token count for each summarized "Atomic Fact"
CHUNK_OVERLAP = 50       # Overlap to maintain semantic continuity between segments
ADAPTIVE_THRESHOLD = 800 # Character limit trigger: AI summarization activates beyond this point
PUNCTUATION_LIST = [".", "!", "?", ";", "\n"] # Delimiters to ensure logical integrity

def get_metadata(text):
    """Extract metadata for context injection using Gemini Flash"""
    model = genai.GenerativeModel(model_name)
    prompt = f"Extract 'Company Name' and 'Report Date/Year' from this text. Output format: [Company | Date]. Text: {text[:500]}"
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "[Unknown Entity | Unknown Date]"

def smart_split(text, max_size=MAX_CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Boundary-aware chunking algorithm using punctuation backtracking"""
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + max_size
        if end >= text_len:
            chunks.append(text[start:])
            break
        
        chunk_slice = text[start:end]
        last_punc = -1
        for punc in PUNCTUATION_LIST:
            pos = chunk_slice.rfind(punc)
            if pos > last_punc:
                last_punc = pos
        
        actual_end = start + (last_punc + 1 if last_punc != -1 else max_size)
        chunks.append(text[start:actual_end])
        
        start = actual_end - overlap
        if start < 0: start = 0
        
    return chunks

def summarize_chunk(chunk_text, metadata):
    """Atomic fact extraction with metadata injection"""
    model = genai.GenerativeModel(model_name)
    prompt = f"""
    Context: {metadata}
    Role: Senior Investment Analyst
    Task: Compress the following text into a list of 'Atomic Facts'.
    Requirements:
    1. Retain all key metrics, percentages, and entity names.
    2. Format as a bulleted list starting with '- '.
    3. Minimize noise while maximizing information density.
    
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
    print(f"📄 Processing: {filename} | Metadata: {metadata}")

    raw_chunks = smart_split(content)
    final_processed_chunks = []

    for i, chunk in enumerate(raw_chunks):
        # Adaptive Logic: Summarize only if chunk is substantial
        if len(chunk) > ADAPTIVE_THRESHOLD / len(raw_chunks): 
            print(f"  - Summarizing chunk {i+1}/{len(raw_chunks)}...")
            processed_text = summarize_chunk(chunk, metadata)
        else:
            print(f"  - Chunk {i+1} size optimal, bypassing summarization.")
            processed_text = chunk
        
        final_processed_chunks.append(f"### Chunk {i+1} Context: {metadata}\n{processed_text}")

    output_filename = filename.replace(".txt", ".md")
    with open(os.path.join(output_dir, output_filename), "w", encoding="utf-8") as f:
        f.write(f"# Processed Research: {filename}\n\n")
        f.write("\n\n---\n\n".join(final_processed_chunks))
    
    print(f"✅ Success! Saved to {output_dir}/{output_filename}\n")

def main():
    raw_dir = "data/raw"
    processed_dir = "data/processed"
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    files = [f for f in os.listdir(raw_dir) if f.endswith(".txt")]
    if not files:
        print(f"⚠️ Please place .txt files in {raw_dir}")
        return

    for file in files:
        process_file(os.path.join(raw_dir, file), processed_dir)

if __name__ == "__main__":
    main()