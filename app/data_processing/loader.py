# app/data_processing/loader.py
import os
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

# LlamaIndex Readers - use specific ones if needed
from llama_index.core.readers import SimpleDirectoryReader
# from llama_index.readers.file import PagedPDFReader # Example specific reader
# from llama_index.readers.file import PptxReader # Example specific reader

from llama_index.core.schema import Document

from app.core.config import (
    DATA_DIR, FAQ_FILE_PATH, CSV_FILE_PATH,
    ORDER_DOCS_DIR, PRESENTATIONS_DIR, FAQ_DIR # Make sure all paths are imported
)

from llama_index.experimental.query_engine import PandasQueryEngine

def clean_html(html_content: str) -> str:
    """Removes HTML tags from a string using BeautifulSoup."""
    if not html_content or not isinstance(html_content, str):
        return ""
    try:
        # Use 'lxml' for robustness if installed, fallback to 'html.parser'
        soup = BeautifulSoup(html_content, 'lxml')
    except ImportError:
        soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ', strip=True)

def load_faq_data(file_path: str = FAQ_FILE_PATH) -> List[Document]:
    """Loads FAQs from the specific Solutions.json structure and cleans HTML."""
    documents = []
    if not os.path.exists(file_path):
         print(f"Warning: FAQ file not found at {file_path}. Skipping FAQ loading.")
         return documents

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully read FAQ JSON file: {file_path}")

        processed_count = 0
        for category_entry in data:
            category = category_entry.get("category", {})
            category_name = category.get("name", "Unknown Category")
            for folder in category.get("all_folders", []):
                folder_name = folder.get("name", "Unknown Folder")
                for article in folder.get("articles", []):
                    title = article.get("title", "No Title")
                    desc_html = article.get("description", "")
                    desc_un_html = article.get("desc_un_html", "") # Prefer this if available
                    description = clean_html(desc_un_html if desc_un_html else desc_html)

                    # Add more context for better retrieval
                    text_content = (f"FAQ Section\nCategory: {category_name}\nFolder: {folder_name}\n"
                                    f"Question: {title}\nAnswer:\n{description}\n--- End FAQ ---")

                    metadata = {
                        "source_type": "FAQ",
                        "category": category_name,
                        "folder": folder_name,
                        "faq_id": str(article.get("id", "N/A")),
                        "title": title,
                        "file_path": file_path # Keep original file path
                    }
                    documents.append(Document(text=text_content, metadata=metadata))
                    processed_count += 1

        print(f"Processed {processed_count} FAQ articles into {len(documents)} documents.")
    except json.JSONDecodeError as e:
        print(f"Error: Could not decode JSON from {file_path}. Invalid JSON format? Error: {e}")
    except Exception as e:
        print(f"Error loading FAQ data from {file_path}: {type(e).__name__} - {e}")

    return documents

def load_other_docs(directories: List[str]) -> List[Document]:
    """Loads documents from specified directories using SimpleDirectoryReader."""
    all_docs = []
    supported_ext = [".pdf", ".txt", ".md", ".pptx", ".docx"] # Common document types

    # Define file extractors if SimpleDirectoryReader has issues, e.g., with complex PDFs
    # file_metadata = lambda filename: {"file_name": filename} # Example metadata func
    # file_extractor = {
    #      ".pdf": PagedPDFReader(return_full_document=True),
    #      ".pptx": PptxReader(),
    # }

    for dir_path in directories:
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            print(f"Warning: Directory not found or is not a directory: {dir_path}. Skipping.")
            continue

        print(f"Loading documents from: {dir_path}")
        try:
            reader = SimpleDirectoryReader(
                input_dir=dir_path,
                required_exts=supported_ext,
                recursive=True,
                # file_extractor=file_extractor, # Uncomment to use specific extractors
                # file_metadata=file_metadata, # Example metadata function
                exclude_hidden=True,
            )
            loaded_docs = reader.load_data(show_progress=True)

            # Enhance metadata and clean text
            for doc in loaded_docs:
                # Ensure standard metadata fields exist
                doc.metadata.setdefault("file_path", "Unknown")
                doc.metadata.setdefault("file_name", os.path.basename(doc.metadata["file_path"]))

                relative_path = os.path.relpath(doc.metadata["file_path"], DATA_DIR)
                source_type_guess = relative_path.split(os.sep)[0] if os.sep in relative_path else "Unknown Source"
                doc.metadata["source_type"] = source_type_guess # e.g., 'Auftragsdokumente'

                # Basic text cleaning (remove excessive whitespace/newlines)
                doc.text = ' '.join(doc.text.strip().split())

            all_docs.extend(loaded_docs)
            print(f"Loaded {len(loaded_docs)} documents from {dir_path}.")
        except Exception as e:
            print(f"Error loading documents from {dir_path}: {type(e).__name__} - {e}")

    return all_docs

def load_csv_data_pandas(file_path: str = CSV_FILE_PATH) -> Optional[pd.DataFrame]:
    """Loads the main CSV data into a Pandas DataFrame, handling duplicate columns."""
    if not os.path.exists(file_path):
        print(f"Error: CSV file not found at {file_path}. Cannot create DataFrame.")
        return None
    try:
        df = pd.read_csv(file_path, encoding='utf-8', low_memory=False)
        print(f"Read {len(df)} rows from CSV: {file_path}")

        # Handle duplicate column names robustly
        cols = list(df.columns)
        counts = {}
        new_cols = []
        for col in cols:
            if col in counts:
                counts[col] += 1
                new_cols.append(f"{col}.{counts[col]}")
            else:
                counts[col] = 0
                new_cols.append(col)

        if len(cols) != len(set(cols)): # Check if duplicates existed
             print(f"Duplicate columns found and renamed. Original: {cols}")
             df.columns = new_cols
             print(f"New columns: {df.columns.tolist()}")
        else:
             print("No duplicate columns found in CSV.")

        # Basic cleaning
        df = df.fillna("") # Replace NaN with empty string for easier processing

        # Attempt type conversions more safely
        for col in df.columns:
            if df[col].dtype == 'object':
                # Try numeric first
                try:
                    df[col] = pd.to_numeric(df[col], errors='raise') # Try direct conversion first
                    print(f"Converted column '{col}' to numeric.")
                    continue # Skip further checks if numeric
                except (ValueError, TypeError):
                     pass # Ignore if not purely numeric

                # Try datetime (if format is consistent - this is basic)
                # Add more specific formats if needed
                try:
                     df[col] = pd.to_datetime(df[col], errors='raise')
                     print(f"Converted column '{col}' to datetime.")
                     continue
                except (ValueError, TypeError):
                     pass

                # Check for boolean-like strings more carefully
                if df[col].astype(str).str.lower().isin(['true', 'false', '0', '1', 'yes', 'no', 'y', 'n', '']).all():
                     map_dict = {'true': True, '1': True, 'yes': True, 'y': True,
                                  'false': False, '0': False, 'no': False, 'n': False,
                                  '': None} # Map empty string to None for nullable boolean
                     try:
                          df[col] = df[col].astype(str).str.lower().map(map_dict).astype('boolean')
                          print(f"Converted column '{col}' to boolean.")
                     except Exception as bool_e:
                          print(f"Could not convert column '{col}' to boolean despite initial check: {bool_e}")


        print(f"Processed CSV data. DataFrame shape: {df.shape}")
        return df
    except Exception as e:
        print(f"CRITICAL Error loading or processing CSV data from {file_path}: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return None

def load_all_data() -> Dict[str, Any]:
    """Loads all data sources required for the agent."""
    print("\n--- Starting Data Loading ---")

    # 1. Load FAQs
    faq_docs = load_faq_data(FAQ_FILE_PATH)

    # 2. Load other documents (PDFs, PPTX)
    doc_directories = [PRESENTATIONS_DIR]
    other_docs = load_other_docs(doc_directories)

    # 3. Combine documents for the vector index
    vector_docs = faq_docs + other_docs
    print(f"\nTotal documents prepared for vector index: {len(vector_docs)}")
    if not vector_docs:
         print("Warning: No documents were loaded for the vector index. RAG on docs/FAQs will be limited.")

    # 4. Load CSV data into DataFrame for Pandas Query Engine
    df_orders = load_csv_data_pandas(CSV_FILE_PATH)
    if df_orders is None:
         print("Warning: Order DataFrame could not be loaded. Queries on specific order details via Pandas Tool will fail.")

    print("--- Data Loading Finished ---\n")

    return {
        "vector_documents": vector_docs,
        "dataframe_orders": df_orders
    }

# Example of running the loader directly for testing
if __name__ == "__main__":
    # This allows running `python app/data_processing/loader.py` from the project root
    # It adjusts the path temporarily to find the config module correctly
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from app.core.config import DATA_DIR # Re-import after path adjustment

    print(f"\nRunning loader test with DATA_DIR: {DATA_DIR}\n")
    loaded_data = load_all_data()
    if loaded_data["dataframe_orders"] is not None:
        print("\nDataFrame Info:")
        loaded_data["dataframe_orders"].info(verbose=True, show_counts=True)
        print("\nDataFrame Head:")
        print(loaded_data["dataframe_orders"].head())
        print("\nDataFrame Sample Row:")
        print(loaded_data["dataframe_orders"].sample(1).to_markdown())
    if loaded_data["vector_documents"]:
        print(f"\nSample Vector Document Metadata (First Doc):")
        print(loaded_data["vector_documents"][0].metadata)
        print(f"\nSample Vector Document Text (First Doc):")
        print(loaded_data["vector_documents"][0].text[:300] + "...")
    else:
         print("\nNo vector documents were loaded.")