# app/core/pdf_processor.py
import os
import tempfile
import uuid
import json
import traceback
from typing import Optional, Tuple, Dict, Any
from datetime import datetime # Import datetime

from fastapi import UploadFile
# LlamaIndex imports for the user's extraction method
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core import Settings # To access configured LLM
from llama_index.llms.openai import OpenAI # Import explicitly if needed

# Pydantic model for extracted data
from app.models.quote import QuoteDetails, AddressDetail

# API Client function (using the one defined in the project)
from app.api.drivemybox_api import get_price_quotation

# Config for temp directory
from app.core.config import TEMP_UPLOAD_DIR, OPENAI_API_KEY, LLM_MODEL_NAME

# Ensure TEMP_UPLOAD_DIR exists
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

# --- Helper Function to Save File (Unchanged) ---
async def save_upload_file_tmp(upload_file: UploadFile) -> Optional[str]:
    """Saves uploaded file temporarily and returns the path, or None on failure."""
    if not upload_file or not upload_file.filename:
        print("Error: No file provided to save.")
        return None
    # Restrict to PDF for this workflow
    if not upload_file.filename.lower().endswith(".pdf"):
        print(f"Error: Invalid file type: {upload_file.filename}. Only PDF is supported for quote extraction.")
        return None
    try:
        # Use a more descriptive temporary filename pattern if desired
        safe_filename = f"upload_{uuid.uuid4()}.pdf"
        temp_filepath = os.path.join(TEMP_UPLOAD_DIR, safe_filename)
        print(f"Saving uploaded PDF temporarily to: {temp_filepath}")
        with open(temp_filepath, "wb") as f_wb:
            while content := await upload_file.read(1024 * 1024): # Read in chunks
                 f_wb.write(content)
        print(f"Successfully saved temporary PDF: {temp_filepath}")
        return temp_filepath
    except Exception as e:
        print(f"Error saving temporary file {upload_file.filename}: {type(e).__name__} - {e}")
        if 'temp_filepath' in locals() and os.path.exists(temp_filepath):
             try: os.remove(temp_filepath)
             except: pass # Ignore cleanup error
        return None
    finally:
         # Ensure file is closed even if saving fails mid-way
         if upload_file and not upload_file.file.closed:
              await upload_file.close()


# --- LLM Extraction Function (Adapted from User's Code) ---
# --- LLM Extraction Function (Updated Prompt) ---
async def extract_quote_details_with_llm(pdf_path: str) -> Tuple[Optional[QuoteDetails], Optional[str]]:
    """
    Uses LlamaIndex RAG approach (query engine) to extract structured quote details
    from a PDF file path and returns a validated Pydantic object or error message.
    """
    # ... (initial checks for pdf_path and Settings.llm remain the same) ...
    if not os.path.exists(pdf_path): return None, f"PDF file not found at {pdf_path}"
    if not Settings.llm: return None, "LLM is not configured (OpenAI API Key missing)."

    try:
        print(f"Loading PDF for LLM extraction: {pdf_path}")
        documents = SimpleDirectoryReader(input_files=[pdf_path]).load_data()
        if not documents or not documents[0].text.strip():
             return None, "No text content found in the PDF."

        document_text = documents[0].text
        print(f"Extracted ~{len(document_text)} chars. Preparing LLM prompt.")

        # Updated Prompt - More specific instructions, especially for container type
        prompt_template_str = f"""
        Analyze the following transport document text carefully. Extract the key fields listed below.
        Output the result ONLY as a single, valid JSON object matching the specified structure precisely. Do not include explanations or markdown formatting around the JSON.

        Fields to extract:
        - document_type: (e.g., "Cartage Advice", "Waggonbestellung", "Amendment", "Invoice")
        - order_reference: (Primary booking/order number like EN*, TB*, SNUE*, Roland Ref*, Unsere Ref*)
        - container_number: (e.g., "HAMU114401-2", "ONEU1548124")
        - container_type: (Identify the container size/type like "40HC", "20BOX", "40' 9'6\" HC", "22G1" and provide the common standard code like "40HC", "22G1", "45G1". If unsure, provide the text as found.)
        - shipper_name:
        - consignee_name:
        - origin_address: {{ "street": ..., "city": ..., "zip": ..., "country": "DE" }} (Extract full address if possible. If only city/zip is available, leave street as null. Default country to DE unless specified otherwise.)
        - destination_address: {{ "street": ..., "city": ..., "zip": ..., "country": "DE" }} (Extract full address if possible. If only city/zip is available, leave street as null. Default country to DE.)
        - key_date: (The most relevant date for *starting* the transport, like 'Versandtag', 'Required From', 'Planned Pickup', 'Gestellung' - e.g., "25.04.2025", "22-Apr-25", "14-Dec-20". Provide the date as written.)
        - transport_mode: (e.g., "Truck", "Rail", "Sea", "LKW")
        - goods_description: (Brief description, e.g., "Static converters", "SEATS FOR MOTOR VEHICLES", "chemikalien")

        If a value is not clearly identifiable in the text, use null for that specific field (or null for the entire address object if no address parts are found).

        Document Text:
        ---
        {document_text[:6000]}
        ---

        Valid JSON Output Only:
        """ # Limit text size

        print("Sending extraction prompt to LLM...")
        response = await Settings.llm.acomplete(prompt_template_str)
        response_text = response.text.strip()

        # ... (JSON cleaning and Pydantic validation logic remains the same) ...
        if response_text.startswith("```json"): response_text = response_text[len("```json"):].strip()
        if response_text.endswith("```"): response_text = response_text[:-3].strip()
        print(f"LLM Raw Response:\n{response_text}\n")
        try:
            extracted_data = json.loads(response_text)
            # Run Pydantic validation AND normalization here!
            quote_details = QuoteDetails.model_validate(extracted_data)
            print("Successfully parsed and validated LLM response into QuoteDetails.")
            return quote_details, None
        except json.JSONDecodeError:
            print("Error: LLM response was not valid JSON.")
            return None, "AI model did not return valid JSON."
        except Exception as pydantic_err:
             print(f"Error validating LLM response against Pydantic model: {pydantic_err}")
             traceback.print_exc()
             return None, f"AI model returned data, but it didn't match the expected format or validation rules: {pydantic_err}"

    except Exception as e:
        print(f"Error during PDF processing or LLM query: {type(e).__name__} - {e}")
        traceback.print_exc()
        return None, f"Failed to process PDF or query AI model: {type(e).__name__}"

# --- Formatting API Response (Unchanged) ---
def _format_api_response(api_response_data: Dict[str, Any]) -> str:
     # ... (Keep the function from the previous pdf_processor.py version) ...
     try:
          # Assuming structure based on user's test.py output
          route_info = api_response_data.get("route", {})
          prices = api_response_data.get("prices", []) # API returns a list of price options

          if not prices:
               return "API returned a response, but no price details were found."

          # Format the first price option as an example
          price_info = prices[0]
          main_price = price_info.get("price", {})
          price_amount = main_price.get("amount", "N/A")
          price_currency = main_price.get("currency", "EUR")
          toll = price_info.get("toll", {})
          toll_amount = toll.get("amount", "N/A")
          distance = route_info.get('distance') # In meters
          # Travel time might not be in quotation response, check structure

          message = f"Based on the extracted details, the estimated price quote is {price_amount} {price_currency}."
          if toll_amount != 'N/A':
               message += f" (Toll included: {toll_amount} {price_currency})." # Assuming same currency
          if distance is not None:
               message += f" Est. Distance: {distance / 1000:.1f} km."

          # Add other details if needed and available (e.g., long haulage flag)
          return message

     except Exception as e:
          print(f"Error formatting successful API response: {e}")
          return f"Received a response from the API, but couldn't format it clearly: {json.dumps(api_response_data)}"


# --- Main Orchestration Function (Unchanged logic, uses validated data) ---
async def handle_quote_request_with_pdf(file: UploadFile) -> str:
    """
    Orchestrates the PDF processing for quotes: Save -> LLM Extract -> Validate -> API Call -> Format Response.
    """
    print(f"--- Starting Quote Request Workflow for PDF: {file.filename} ---")
    temp_filepath = None
    try:
        # 1. Save PDF
        temp_filepath = await save_upload_file_tmp(file)
        if not temp_filepath: return "Error: Failed to save the uploaded PDF file."

        # 2. Extract & Validate using LLM + Pydantic
        extracted_details, error_msg = await extract_quote_details_with_llm(temp_filepath)
        if error_msg: return f"Error during detail extraction: {error_msg}"
        if not extracted_details: return "Error: AI model could not extract details from the PDF."

        # 3. Check Completeness for API call
        if extracted_details.is_complete_for_api():
            print("Extracted details are sufficient and validated. Preparing API call...")
            # 4. Construct API Payload using validated/normalized data
            origin_addr = extracted_details.origin_address
            dest_addr = extracted_details.destination_address

            # Use the exact structure from test.py / dMB_client.py example payload
            route_payload = {
                "route": {
                    "route_loading_points": [
                        {
                            "address": {
                                "discriminator": "ExtendedAddress",
                                "city": origin_addr.city,
                                "country": origin_addr.country,
                                "postal_code": origin_addr.zip_code, # Use validated zip
                                "street": origin_addr.street or ""
                            },
                            "discriminator": "ExtendedRouteLoadingPointCreation",
                            "sequence_number": 1,
                            "type": "WAREHOUSE", # Default type
                            "provision_location": True
                        },
                        {
                            "address": {
                                "discriminator": "ExtendedAddress",
                                "city": dest_addr.city,
                                "country": dest_addr.country,
                                "postal_code": dest_addr.zip_code, # Use validated zip
                                "street": dest_addr.street or ""
                            },
                            "discriminator": "ExtendedRouteLoadingPointCreation",
                            "sequence_number": 2,
                            "type": "WAREHOUSE", # Default type
                            "dropoff_location": True # Assume destination is dropoff
                        }
                    ]
                }
            }
            container_payload = {
                "containers": [
                    {
                        "sequence_number": 1,
                        "type_code": extracted_details.container_type, # Use validated/normalized type
                        "provision_at": extracted_details.key_date, # Use validated/formatted date
                        # Add optional fields if extracted & validated
                        # "assumed_net_weight": ...,
                    }
                ]
            }
            # Combine for the final payload structure if needed by get_price_quotation
            # The function `get_price_quotation` expects route_data and container_data separately
            # api_payload = {**route_payload, **container_payload} # Not needed for the current api function

            # 5. Call DriveMyBox API
            print(f"Calling API with Route:\n{json.dumps(route_payload, indent=2)}")
            print(f"Calling API with Containers:\n{json.dumps(container_payload['containers'], indent=2)}")
            # Pass dicts expected by get_price_quotation
            api_response_data = get_price_quotation(route_payload, container_payload['containers'])

            # 6. Format Response
            if api_response_data and 'error' not in str(api_response_data).lower():
                print("API call successful.")
                return _format_api_response(api_response_data)
            else:
                error_detail = "Could not retrieve quote or API returned an error."
                if isinstance(api_response_data, dict):
                     error_detail = api_response_data.get('details', error_detail)
                     print(f"API returned error/empty response: {api_response_data}")
                else:
                     print(f"API call failed or returned unexpected data: {api_response_data}")
                return f"Failed to get quote from API. Reason: {error_detail}"

        else:
            # 3b. Ask for Clarification
            missing_fields = extracted_details.get_missing_fields()
            print(f"Validation failed. Missing fields for API call: {missing_fields}")
            # Show cleaned/validated data where possible
            extracted_info_str = extracted_details.model_dump_json(indent=2, exclude_defaults=True, exclude_none=True)
            return (f"I read the PDF and found some details:\n```json\n{extracted_info_str}\n```\n"
                    f"However, I still need the following to get a quote: **{', '.join(missing_fields)}**. "
                    f"Could you please provide the missing information?")

    except Exception as e:
        print(f"--- Unhandled Error in PDF Quote Workflow for {file.filename} ---")
        traceback.print_exc()
        return f"An unexpected error occurred: {type(e).__name__}. Check server logs."
    finally:
         # Final cleanup
         if temp_filepath and os.path.exists(temp_filepath):
              try: os.remove(temp_filepath)
              except Exception as e_del: print(f"Warning: Failed cleanup {temp_filepath}: {e_del}")

    print(f"--- Finished Quote Request Workflow for PDF: {file.filename} ---")