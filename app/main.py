# app/main.py
from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import sys
import io # For reading file content
import pypdf # For reading PDF text

from app.core.pdf_processor import handle_quote_request_with_pdf # Import the new handler


# Ensure the app directory is in the Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Core agent logic
from app.core.agent import initialize_agent, query_agent
from app.models.chat import ChatRequest, ChatResponse # Keep ChatRequest for the non-file endpoint
from app.core.config import PROJECT_ROOT

# --- FastAPI App Setup ---
app = FastAPI(title="DriveMyBox AI Agent", version="0.1.0")

static_dir = os.path.join(PROJECT_ROOT, "app", "static")
templates_dir = os.path.join(PROJECT_ROOT, "app", "templates")

if not os.path.isdir(static_dir): raise RuntimeError(f"Static directory not found: {static_dir}")
if not os.path.isdir(templates_dir): raise RuntimeError(f"Templates directory not found: {templates_dir}")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# --- Agent Initialization on Startup ---
@app.on_event("startup")
async def startup_event():
    print("FastAPI startup event: Initializing AI Agent...")
    try:
        initialize_agent(force_rebuild=False)
        print("AI Agent initialization process completed.")
    except Exception as e:
        print(f"CRITICAL ERROR during agent initialization: {e}")

# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def get_chat_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- Existing Text-Only Chat Endpoint ---
@app.post("/api/chat", response_model=ChatResponse)
async def handle_chat_message(chat_request: ChatRequest):
    """Handles text-only chat messages."""
    query = chat_request.query
    if not query or not query.strip():
        return ChatResponse(response="Please enter a message to chat.")
    try:
        agent_response_text = await query_agent(query.strip())
        return ChatResponse(response=agent_response_text)
    except Exception as e:
        print(f"Error in /api/chat endpoint processing query '{query}': {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error processing your request.")

# --- UPDATED Endpoint for File Upload + Chat ---
@app.post("/api/upload_and_chat", response_model=ChatResponse)
async def handle_upload_and_chat(
    query: str = Form(""), # Query remains optional
    file: UploadFile = File(...)
):
    """Handles file uploads. If PDF, attempts quote workflow, otherwise uses general agent."""
    filename = file.filename or "uploaded_file"
    print(f"Received file via upload_and_chat: {filename}, query: '{query}'")

    # --- Routing based on file type ---
    if file.content_type == "application/pdf" and filename.lower().endswith(".pdf"):
        print("PDF detected, attempting quote workflow...")
        # Call the dedicated PDF quote handler
        quote_response = await handle_quote_request_with_pdf(file) # Pass the UploadFile object directly
        return ChatResponse(response=quote_response)

    # --- Fallback for other allowed types (like TXT) or if PDF wasn't for quote ---
    # (Keep the previous text extraction logic for non-PDFs or general queries with files)
    elif file.content_type == "text/plain":
        print("Text file detected, combining with query for general agent...")
        file_content = ""
        try:
            contents = await file.read()
            try:
                file_content = contents.decode("utf-8")
            except UnicodeDecodeError:
                file_content = contents.decode("latin-1") # Fallback encoding
            print(f"Read {len(file_content)} chars from TXT file.")
        except Exception as e:
             print(f"Error reading TXT file {filename}: {e}")
             # Return error directly for simple file reading issues
             return ChatResponse(response=f"Error reading uploaded text file: {e}")
        finally:
            await file.close()

        # Combine query and file content for general agent
        combined_input = f"--- Start of Uploaded File ({filename}) Content ---\n{file_content}\n--- End of Uploaded File Content ---\n\nUser Query: {query if query.strip() else 'Please summarize or analyze this document.'}"

        try:
            agent_response_text = await query_agent(combined_input.strip())
            return ChatResponse(response=agent_response_text)
        except Exception as e:
            print(f"Error processing combined query/TXT file content: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail="Internal server error processing your request with the uploaded file.")

    else:
        # Handle unsupported file types explicitly if not caught by initial validation
        print(f"Unsupported file type uploaded: {file.content_type}")
        await file.close() # Close the file handle
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}. Please upload PDF for quotes or TXT for general queries.")


# --- Other Endpoints (/rebuild-index, /health) remain the same ---
@app.post("/api/rebuild-index", status_code=202)
async def rebuild_index():
    print("API request received to rebuild index...")
    try:
         initialize_agent(force_rebuild=True)
         return {"message": "Index rebuilding process initiated successfully."}
    except Exception as e:
         print(f"Error during manual index rebuild via API: {e}")
         raise HTTPException(status_code=500, detail=f"Failed to trigger index rebuild: {e}")

@app.get("/health")
async def health_check():
    return {"status": "ok"}