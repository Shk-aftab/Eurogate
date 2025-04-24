# app/core/agent.py
import os
import pandas as pd
import json
from typing import List, Optional, Any, Dict

# LlamaIndex core imports
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Settings,
    Document,
    PromptTemplate # Keep for potential future use, but remove from engine init for now
)
from llama_index.core.tools import FunctionTool, QueryEngineTool, ToolMetadata # Import ToolMetadata
# from llama_index.core.query_engine import PandasQueryEngine # <-- REMOVE THIS OLD IMPORT

# LlamaIndex LLMs and Embeddings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

# LlamaIndex Agents
from llama_index.agent.openai import OpenAIAgent

# LlamaIndex Experimental (for Pandas Query Engine)
from llama_index.experimental.query_engine import PandasQueryEngine # <-- ADD THIS NEW IMPORT

# Vector Store
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

# Local imports
from app.core.config import (
    OPENAI_API_KEY, LLM_MODEL_NAME, EMBED_MODEL_NAME,
    STORAGE_DIR, CSV_FILE_PATH
)
from app.data_processing.loader import load_all_data
from app.api.drivemybox_api import get_price_quotation

# ... (Global variables and initialize_settings remain the same) ...
agent_state = {
    "agent": None,
    "df_orders": None,
    "index": None,
    "initialized": False
}

# --- Setup LlamaIndex Settings ---
def initialize_settings():
    """Initializes LlamaIndex settings for LLM and Embedding Model."""
    print("Initializing LlamaIndex settings...")
    if not OPENAI_API_KEY:
         raise ValueError("OpenAI API Key not found. Cannot initialize settings.")
    Settings.llm = OpenAI(model=LLM_MODEL_NAME, api_key=OPENAI_API_KEY)
    Settings.embed_model = OpenAIEmbedding(model=EMBED_MODEL_NAME, api_key=OPENAI_API_KEY)
    # Optional: Configure node parser globally if needed
    # from llama_index.core.node_parser import SentenceSplitter
    # Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=20)
    print(f"LlamaIndex settings initialized (LLM: {LLM_MODEL_NAME}, Embed: {EMBED_MODEL_NAME})")
# --- Agent Initialization ---

def setup_index_and_tools(vector_docs: List[Document], df: Optional[pd.DataFrame], force_rebuild: bool = False) -> Dict[str, Any]:
    """Sets up the index and tools, creating or loading from storage."""
    # ... (ChromaDB initialization remains the same) ...
    print("Initializing ChromaDB...")
    os.makedirs(os.path.join(STORAGE_DIR, "chroma_db"), exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=os.path.join(STORAGE_DIR, "chroma_db"))
    collection_name = "drivemybox_collection"
    try:
        chroma_collection = chroma_client.get_or_create_collection(collection_name)
        print(f"Using ChromaDB collection: {collection_name}")
    except Exception as e:
        print(f"Error initializing Chroma collection: {e}. Attempting reset/recreate...")
        try: chroma_client.delete_collection(collection_name)
        except: pass
        chroma_collection = chroma_client.create_collection(collection_name)
        print(f"Recreated ChromaDB collection: {collection_name}")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = None

    # ... (Index loading/building logic remains the same) ...
    if not force_rebuild and os.path.exists(os.path.join(STORAGE_DIR, "docstore.json")):
        try:
            print(f"Attempting to load index from: {STORAGE_DIR}")
            storage_context_load = StorageContext.from_defaults(persist_dir=STORAGE_DIR, vector_store=vector_store)
            index = load_index_from_storage(storage_context_load)
            print("Successfully loaded index from storage.")
        except Exception as e:
            print(f"Failed to load index from storage: {e}. Rebuilding...")
            index = None

    if index is None:
        if not vector_docs:
             print("CRITICAL: No documents available to build vector index...")
        else:
             print("Building vector store index from documents...")
             # Ensure Node Parser is set if configured globally
             from llama_index.core.node_parser import SentenceSplitter # Import here if not global
             node_parser = Settings.node_parser or SentenceSplitter(chunk_size=512) # Use global or default

             index = VectorStoreIndex.from_documents(
                 vector_docs,
                 storage_context=storage_context,
                 show_progress=True,
                 transformations=[node_parser] # Pass transformations list
             )
             print("Persisting index to disk...")
             os.makedirs(STORAGE_DIR, exist_ok=True)
             index.storage_context.persist(persist_dir=STORAGE_DIR)
             print(f"Index built and persisted to {STORAGE_DIR}.")


    # --- Create Tools ---
    all_tools = []

    # 1. Vector Query Tool
    if index:
        vector_query_engine = index.as_query_engine(similarity_top_k=4)
        vector_tool = QueryEngineTool(
            query_engine=vector_query_engine,
            metadata=ToolMetadata(
                name="general_knowledge_and_order_documents",
                description=(
                    "Provides information about driveMybox company details, services, FAQs, registration processes, "
                    "app requirements, support information, general procedures from presentations. "
                    "Also used to find information **within specific uploaded order documents** (PDFs like Cartage Advice, Invoices, Order Confirmations) based on their text content. "
                    "Use for 'what is', 'how to', 'explain' questions, or finding specific text like 'shipper name in document X.pdf' or 'goods description in TB04733688'."
                )
            )
        )
        all_tools.append(vector_tool)
        print("Vector Query Tool (including Order Doc text) created.")
    else:
        print("Skipping Vector Query Tool creation as index is unavailable.")

    # 2. Pandas Query Tool (Updated Initialization)
    # Check df is not None AND not empty before creating the tool
    if df is not None and not df.empty:
        try:
             print("Attempting to create Pandas Query Engine...")
             # Use the NEW import path and remove the custom instruction_str for now
             pandas_query_engine = PandasQueryEngine(
                 df=df,
                 verbose=True,
                 # Let LlamaIndex handle the default prompting for the experimental engine
                 # instruction_str=pandas_prompt_str # Removed custom prompt initially
                 # synthesizer=... # Optional: customize how pandas output is synthesized
             )
             pandas_tool = QueryEngineTool(
                 query_engine=pandas_query_engine,
                 metadata=ToolMetadata(
                     name="order_database_query",
                     description=(
                         "Queries a database (Pandas DataFrame) for specific structured details about transport orders using columns like `job_order_ref`, `status`, `status.1`, `container_no`, `trip_id`, `trucker_lat`, `trucker_lng`, `delay`, `price_total`, etc. "
                         "Use this for specific lookups like 'What is the status.1 for container ONEU1548124?', "
                         "'Show trucker location for trip 70701', 'List job_order_ref for orders with status ACTIVE'. Requires specific identifiers for filtering."
                     )
                 )
             )
             all_tools.append(pandas_tool)
             print("Pandas DataFrame Tool created successfully.")
        except Exception as e:
            # Print the error more prominently
            print("\n" + "*"*20 + " PANDAS TOOL FAILED " + "*"*20)
            print(f"Error creating Pandas Query Engine tool: {e}")
            import traceback
            traceback.print_exc() # Show full traceback
            print("*"*50 + "\n")
            print("Skipping Pandas tool due to error during initialization.")
    elif df is None:
         print("Skipping Pandas DataFrame Tool creation as DataFrame is None (failed to load).")
    else: # df exists but is empty
         print("Skipping Pandas DataFrame Tool creation as DataFrame is empty.")


    '''# 3. API Function Tool
    price_quote_api_tool = FunctionTool.from_defaults(
        fn=get_price_quote_tool_wrapper,
        metadata=ToolMetadata(
            name="price_quotation_api",
            description=(
                "Retrieves a non-binding price quotation for a container transport "
                "from the DriveMyBox API based on origin address, destination address, and container type. "
                "Use this ONLY when specifically asked for a 'price quote' or 'cost estimate'. "
                "Example query: 'Get a price quote from Hamburg, Kurt-Eckelmann-Straße 1 to Nürnberg, Rheinstrasse 40 for a 40HC container'."
            )
        )
    )
    all_tools.append(price_quote_api_tool)
    print("Price Quotation API Tool created.")'''

    # Final check on tools
    print(f"Total tools created for agent: {len(all_tools)}")
    if not all_tools:
         print("WARNING: No tools were successfully created. Agent capabilities will be severely limited.")

    return {"index": index, "tools": all_tools}


# ... (initialize_agent, get_agent_instance, query_agent remain structurally the same,
#      they will now use the corrected setup_index_and_tools function) ...

def initialize_agent(force_rebuild: bool = False):
    """Loads data, sets up index/tools, and creates the agent."""
    global agent_state
    if agent_state["initialized"] and not force_rebuild:
        print("Agent already initialized.")
        return

    print("\n--- Initializing Agent ---")
    initialize_settings() # Ensure LLM/Embeddings are set up first

    # Load data
    loaded_data = load_all_data()
    agent_state["df_orders"] = loaded_data["dataframe_orders"]

    # Setup index and tools
    setup_result = setup_index_and_tools(
        vector_docs=loaded_data["vector_documents"],
        df=agent_state["df_orders"],
        force_rebuild=force_rebuild
    )
    agent_state["index"] = setup_result["index"]
    tools = setup_result["tools"]

    if not tools:
         print("CRITICAL: No tools were created. The agent will not be functional.")
         agent_state["initialized"] = False
         return

    # System Prompt for the Agent (keep the updated one)
    system_prompt = """
    You are a helpful AI assistant for driveMybox, specializing in container transport logistics.
    Your goal is to answer user queries accurately using the provided tools.
    Here are your tools:
    1.  **general_knowledge_and_order_documents**: Use for general driveMybox info (company, services, FAQs), processes from presentations, AND for finding specific text within uploaded order documents (PDFs like Cartage Advice, Invoices). Example: 'What is driveMybox?', 'How to register?', 'Find shipper in TB04733688.pdf'.
    2.  **order_database_query**: Use ONLY for specific details about transport orders from the structured database extract (CSV). Use columns like `job_order_ref`, `status`, `status.1`, `container_no`, `trip_id`, `trucker_lat`, `trucker_lng`, `delay`, `price_total`, etc. Requires specific identifiers (e.g., 'EN250401749-1') for filtering. Example: 'What is the status.1 for container ONEU1548124?', 'Show trucker location for trip 70701'.
    3.  **price_quotation_api**: Use ONLY when the user explicitly asks for a 'price quote' or 'cost estimate'. Requires origin address, destination address, and container type (e.g., 40HC, 22G1).

    **Instructions:**
    - Analyze the user's query carefully to determine the best tool(s) to use.
    - If querying the order database, be precise with filters (use `job_order_ref` or `container_no` if available).
    - If using the price quote API, clearly state the information you need if the user didn't provide it (origin, destination, container type). Do not guess addresses if they are unclear.
    - If asked about content within a specific PDF order document, use the `general_knowledge_and_order_documents` tool.
    - If you use the `order_database_query` tool, present the result clearly. If it's tabular data, summarize briefly or list key points.
    - If the information isn't available in any tool, clearly state that you cannot find the answer.
    - Be concise, accurate, and helpful.
    """

    try:
        agent_state["agent"] = OpenAIAgent.from_tools(
            tools,
            llm=Settings.llm,
            verbose=True,
            system_prompt=system_prompt
        )
        agent_state["initialized"] = True
        print("--- Agent Initialization Complete ---")
    except Exception as e:
         print(f"CRITICAL Error creating OpenAI Agent: {e}")
         import traceback
         traceback.print_exc()
         agent_state["initialized"] = False

def get_agent_instance() -> Optional[OpenAIAgent]:
    """Returns the initialized agent instance."""
    if not agent_state["initialized"]:
         print("Attempting to initialize agent (called from get_agent_instance)...")
         initialize_agent()
    if not agent_state["initialized"]:
         print("Error: Agent failed to initialize (checked in get_agent_instance).")
         return None
    return agent_state["agent"]

async def query_agent(query_text: str) -> str:
    """Queries the global agent instance asynchronously."""
    current_agent = get_agent_instance()
    if not current_agent:
        return "Error: AI Agent is not available or failed to initialize. Please check server logs."
    if not query_text.strip():
        return "Please provide a query."
    try:
        print(f"\n>>> Querying Agent with: '{query_text}'")
        response = await current_agent.achat(query_text)
        response_text = str(response)
        print(f"<<< Agent Response: {response_text}")
        return response_text
    except Exception as e:
        print(f"Error during agent query: {e}")
        import traceback
        traceback.print_exc()
        return f"Sorry, an error occurred while processing your request. Error type: {type(e).__name__}"