import json
import os
import shutil
import time
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import streamlit as st
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Configuration
DATA_PATH = "data/deep_scraped_professors.json"
DB_DIR = "vector_db"

def ingest_data():
    # 1. Load Data
    if not os.path.exists(DATA_PATH):
        print(f"Error: {DATA_PATH} not found.")
        return

    with open(DATA_PATH, "r") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} professors from {DATA_PATH}")

    # 2. Prepare Documents
    documents = []
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n## ", "\n### ", "\n", " ", ""]
    )

    for prof in data:
        prof_name = prof.get('name', 'Unknown')
        department = prof.get('department', 'Unknown')
        style = prof.get('style', 'Unknown')
        
        scraped_pages = prof.get('scraped_pages', [])
        
        for page in scraped_pages:
            url = page.get('url', '')
            title = page.get('title', '')
            content = page.get('content', '')
            
            if not content:
                continue
            
            # KEY FIX: Filter out Generic/Administrative Pages
            # This prevents "False Attribution" where a professor gets credit for "Degree Requirements".
            ignore_paths = ["/academics/", "/admissions/", "/undergraduate", "/graduate", "/degree-requirements", "/financial-aid"]
            if any(path in url.lower() for path in ignore_paths):
                print(f"Skipping Generic Page: {title} ({url})")
                continue
                
            # Chunk the markdown content
            chunks = text_splitter.create_documents([content])
            
            for chunk in chunks:
                # Enrich metadata
                chunk.metadata["name"] = prof_name
                chunk.metadata["department"] = department
                chunk.metadata["style"] = style
                chunk.metadata["source_url"] = url
                chunk.metadata["page_title"] = title
                
                # Prepend context to page_content so retrieval makes sense
                # "Professor X (Research): ... content ..."
                chunk.page_content = f"Professor {prof_name} - {title}\nSource: {url}\n\n{chunk.page_content}"
                
                documents.append(chunk)
    
    # 3. Initialize Embeddings (Gemini)
    try:
        os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
    except Exception:
        pass # Fallback if not in secrets or running locally without streamlit context (though st.secrets usually works if .streamlit/secrets.toml exists)

    if "GOOGLE_API_KEY" not in os.environ:
        print("Error: GOOGLE_API_KEY environment variable not found.")
        return

    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    # 4. Create and Persist Vector Store
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)

    print(f"Creating ChromaDB in {DB_DIR}... ({len(documents)} chunks)")
    vectorstore = None
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        print(f"  Embedding batch {i // batch_size + 1}/{-(-len(documents) // batch_size)}...")
        if vectorstore is None:
            vectorstore = Chroma.from_documents(batch, embedding=embeddings, persist_directory=DB_DIR)
        else:
            vectorstore.add_documents(batch)
        if i + batch_size < len(documents):
            time.sleep(1)

    print("Ingestion complete! Database ready.")

if __name__ == "__main__":
    ingest_data()
