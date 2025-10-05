# tenants-voice-website/ingest_data.py

# --- Installation ---
# Before running, install the necessary libraries by running this command in your terminal:
# pip install supabase langchain google-generativeai python-dotenv python-dateutil

import os
import getpass
import re
import ast
import time
from datetime import datetime
from dateutil.parser import parse as parse_date
from dotenv import load_dotenv
from supabase import create_client, Client
from langchain.text_splitter import RecursiveCharacterTextSplitter
import google.generativeai as genai

# --- Configuration ---
# Load environment variables from a .env file if it exists
load_dotenv()

def get_user_keys():
    """Securely prompts the user for their API keys."""
    print("--- Please enter your credentials ---")
    supabase_url = input("Enter your Supabase URL: ").strip()
    supabase_key = getpass.getpass("Enter your Supabase Anon Key: ").strip()
    google_key = getpass.getpass("Enter your Google AI API Key: ").strip()
    return supabase_url, supabase_key, google_key

def initialize_clients(supabase_url, supabase_key, google_key):
    """Initializes and returns the Supabase and Google AI clients."""
    try:
        supabase = create_client(supabase_url, supabase_key)
        genai.configure(api_key=google_key)
        embedding_model = genai.GenerativeModel('text-embedding-004')
        tagging_model = genai.GenerativeModel('gemini-2.5-flash')
        print("\nSuccessfully connected to Supabase and Google AI.")
        return supabase, embedding_model, tagging_model
    except Exception as e:
        print(f"Error initializing clients: {e}")
        return None, None, None

def extract_metadata(file_path):
    """
    Extracts metadata (Source URL, Priority Date) from the top of a text file.
    """
    source_url = None
    priority_date = None
    modified_date = None
    scraped_date = None
    header_end_line = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 10 and "---" not in line:
                break
            header_end_line = i + 1

            if re.match(r'Source URL:', line, re.IGNORECASE):
                source_url = line.split(':', 1)[1].strip()

            if re.match(r'Date modified:|Last Modified:', line, re.IGNORECASE):
                date_str = line.split(':', 1)[1].strip()
                try:
                    modified_date = parse_date(date_str).date()
                except Exception:
                    pass
            elif re.match(r'Date Scraped:|Scrape Date:', line, re.IGNORECASE):
                date_str = line.split(':', 1)[1].strip()
                try:
                    scraped_date = parse_date(date_str).date()
                except Exception:
                    pass
            
            if "---" in line:
                break
    
    priority_date = modified_date or scraped_date
    return source_url, priority_date, header_end_line

def get_ai_tags(chunk_text, model):
    """
    Uses Gemini to generate keywords/tags for a text chunk.
    This new version is more robust and can handle messy AI responses.
    """
    try:
        prompt = f"""From the following text, extract a list of the 3-5 most important keywords or topics. 
        Return ONLY a Python list of strings, like `['keyword1', 'keyword2']`.

        Text: "{chunk_text}"
        """
        response = model.generate_content(prompt)
        
        # --- NEW ROBUST PARSING LOGIC ---
        # Find the list within the AI's response, even if it includes extra text.
        match = re.search(r'\[.*?\]', response.text)
        if match:
            list_str = match.group(0)
            tags = ast.literal_eval(list_str)
            if isinstance(tags, list):
                return tags
        # --- END NEW LOGIC ---

    except Exception as e:
        if 'rate limit' in str(e).lower():
            print("  - Rate limit hit, pausing for 5 seconds...")
            time.sleep(5)
            return get_ai_tags(chunk_text, model) # Retry the request
        print(f"  - Warning: Could not generate tags. Error: {e}")
    return [] # Return empty list on failure

def process_file(file_path, supabase, embedding_model, tagging_model, text_splitter):
    """Processes a single file: extracts metadata, chunks, generates tags/embeddings, and uploads."""
    print(f"\n--- Processing file: {os.path.basename(file_path)} ---")
    
    try:
        source_url, priority_date, header_end_line = extract_metadata(file_path)
        print(f"  - Found Metadata: URL={source_url is not None}, Date={priority_date}")

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            content = "".join(lines[header_end_line:])

        chunks = text_splitter.split_text(content)
        print(f"  - Split content into {len(chunks)} chunks.")

        for i, chunk in enumerate(chunks):
            print(f"  - Processing chunk {i + 1}/{len(chunks)}...")
            
            tags = get_ai_tags(chunk, tagging_model)
            print(f"    - Generated Tags: {tags}")

            embedding_response = genai.embed_content(model='models/text-embedding-004', content=chunk)
            embedding = embedding_response['embedding']
            print("    - Generated Embedding.")
            
            supabase.table('documents').insert({
                'content': chunk,
                'embedding': embedding,
                'priority_date': str(priority_date) if priority_date else None,
                'source_url': source_url,
                'keywords': tags
            }).execute()
            print("    - Uploaded to Supabase.")

    except Exception as e:
        print(f"  - ERROR: Failed to process file {os.path.basename(file_path)}. Error: {e}")


def main():
    """Main function to run the ingestion script."""
    supabase_url, supabase_key, google_key = get_user_keys()
    
    if not all([supabase_url, supabase_key, google_key]):
        print("Missing one or more keys. Exiting.")
        return

    supabase, embedding_model, tagging_model = initialize_clients(supabase_url, supabase_key, google_key)
    if not supabase or not embedding_model or not tagging_model:
        print("Failed to initialize clients. Exiting.")
        return
        
    knowledge_path = 'knowledge_source'
    if not os.path.isdir(knowledge_path):
        print(f"Error: The '{knowledge_path}' folder was not found.")
        print("Please create it and add your .txt files.")
        return

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
    )
    
    files_to_process = [f for f in os.listdir(knowledge_path) if f.endswith('.txt')]

    if not files_to_process:
        print(f"No .txt files found in the '{knowledge_path}' folder. Exiting.")
        return
        
    for filename in files_to_process:
        file_path = os.path.join(knowledge_path, filename)
        process_file(file_path, supabase, embedding_model, tagging_model, text_splitter)
        
    print("\n--- Ingestion complete! ---")
    print("Your knowledge base has been successfully built in Supabase.")


if __name__ == "__main__":
    main()

