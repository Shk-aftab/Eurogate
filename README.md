# DriveMyBox AI Agent (Hackathon Project - v0.2)

This project implements an AI agent using Retrieval-Augmented Generation (RAG) and LLM Function Calling/Program capabilities, powered by LlamaIndex and OpenAI. It answers questions about the driveMybox platform and provides price quotes based on uploaded PDF documents.

**Use Case:** driveMybox (Digital platform for truck container transports)

## Features

*   **RAG Chat:** Answers general questions (FAQs, processes, document content) using a vector index of provided documents (FAQs, PPTX, PDF text).
*   **Structured Data Query:** Answers specific questions about orders (status, IDs, locations, times) using a Pandas Query Engine on the provided CSV database extract.
*   **PDF Quote Workflow:**
    *   Accepts PDF uploads (invoices, orders) via the chat interface.
    *   Uses an LLM program (`LLMTextCompletionProgram`) to extract structured quote details (origin, destination, container type) from the PDF text.
    *   Validates extracted information.
    *   If details are missing, asks the user for clarification (basic single-turn).
    *   If details are complete, calls the (test) DriveMyBox API to get a price quotation.
    *   Returns the quote or clarification request to the user.
*   Web Interface: Simple chat UI built with FastAPI, HTML, CSS, JS.
*   Persistent Index: Uses ChromaDB to store vector embeddings locally (`./storage/`).

## Project Structure

(Keep the structure diagram as before)
...

## Setup

(Keep setup steps 1-5 as before, ensuring `python-multipart` is in requirements)
... Make sure `.env` has the correct **`DRIVEMYBOX_API_BASE_URL`**.

## Running the Application

1.  **Start the FastAPI server:**
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```
    *   The first run builds the vector index in `./storage`. Subsequent runs load it.
2.  **Access the Chat UI:**
    Open `http://127.0.0.1:8000`.

## How it Works

1.  **Data Ingestion & Indexing (on startup):** FAQs, presentations, and text from order PDFs are loaded, processed, embedded, and stored in a ChromaDB vector index. The CSV order data is loaded into a Pandas DataFrame.
2.  **Agent/Processor Initialization (on startup):**
    *   A LlamaIndex `OpenAIAgent` is initialized with tools for querying the vector index and the Pandas DataFrame (for non-quote text queries).
    *   Settings for the LLM (used by both agent and PDF processor) are configured.
3.  **Chat Interaction (`/api/chat`):**
    *   The endpoint accepts text (`query`) and an optional PDF file (`file`) via `FormData`.
    *   **If a PDF file is present:**
        *   The file is passed to `app.core.pdf_processor.handle_quote_request_with_pdf`.
        *   This saves the PDF, extracts text, uses an LLM program to get structured `QuoteDetails`.
        *   If details are incomplete, it returns a clarification message.
        *   If complete, it calls the `app.api.drivemybox_api.get_price_quotation` function.
        *   The formatted quote or API error is returned.
    *   **If NO file is present:**
        *   The text `query` is passed to `app.core.agent.query_agent`.
        *   The RAG agent checks if it's a quote request (and deflects it, asking for PDF upload).
        *   Otherwise, the agent uses its tools (Vector Search, Pandas Query) to answer the text-based question.
        *   The agent's synthesized response is returned.

## Example Usage

*   **Text Query (RAG/Pandas):**
    *   "What is driveMybox?"
    *   "What's the status of order EN250401749-1?"
    *   "Show the trucker location for trip 72357."
    *   "What requirements are mentioned in the presentations for the app?"
*   **PDF Quote Request:**
    1.  Type a query like: "Get quote from this order" or "Price estimate for this PDF".
    2.  Click the file input button, select your PDF order/invoice file.
    3.  Click "Send".
    4.  The agent will respond with either the quote details or a request for missing information (e.g., "I extracted X, Y but need Container Type. Please provide it.").

## Potential Improvements / Bonus Points

*   **Conversational Clarification:** Implement proper state management to handle multi-turn conversations when asking for missing quote details.
*   **Robust PDF Structure Parsing:** Use more advanced PDF parsing libraries (like `unstructured`, `PyMuPDF`) or LLM vision models if text extraction is insufficient for complex layouts.
*   **Enhanced API Tool Parsing (for Text):** If text-based quotes *are* needed, implement robust NLP/LLM function calling to extract parameters reliably.
*   **Source Citation:** Display file names/page numbers or CSV rows used for RAG/Pandas answers.
*   **Streaming:** Stream LLM responses and potentially PDF processing status updates.
*   **Error Handling:** More specific error messages and logging.
*   **UI/UX:** Improve the frontend significantly.