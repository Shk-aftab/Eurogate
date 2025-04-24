# app/models/quote.py
from pydantic import BaseModel, Field, validator, field_validator # Import field_validator for newer Pydantic
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import re

# Standard container type mapping (adjust as needed based on common variations)
CONTAINER_TYPE_MAP = {
    "20' box": "22G1",
    "20box": "22G1",
    "20gp": "22G1",
    "20'gp": "22G1",
    "20 dc": "22G1",
    "20dc": "22G1",
    "22g1": "22G1",
    "40'hc": "45G1", # Assuming 40' HC maps to 45G1 for driveMybox common types
    "40 hc": "45G1",
    "40hc": "45G1",
    "40' high cube": "45G1",
    "40 high cube": "45G1",
    "45g1": "45G1",
    "40' gp": "42G1", # General Purpose 40ft
    "40 gp": "42G1",
    "40gp": "42G1",
    "42g1": "42G1",
    # Add more mappings as observed
}

class AddressDetail(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None # Make city mandatory for API call later
    zip_code: Optional[str] = Field(None, alias='zip') # Make zip mandatory for API call later
    country: str = "DE" # Keep default

    class Config:
        populate_by_name = True

class QuoteDetails(BaseModel):
    """Structured data extracted from a transport document for quotation."""
    document_type: Optional[str] = None
    order_reference: Optional[str] = None
    container_number: Optional[str] = None
    shipper_name: Optional[str] = None
    consignee_name: Optional[str] = None
    origin_address: Optional[AddressDetail] = None
    destination_address: Optional[AddressDetail] = None
    key_date: Optional[str] = None # Parsed/validated date for API use
    transport_mode: Optional[str] = None
    goods_description: Optional[str] = None
    container_type: Optional[str] = None # Standardized type code

    # --- Validators ---

    @field_validator('container_type', mode='before')
    @classmethod
    def normalize_container_type(cls, v: Any) -> Optional[str]:
        """Attempts to normalize common container type variations."""
        if not v or not isinstance(v, str):
            return None # Not provided or wrong type
        
        v_lower = v.lower().strip()
        # Direct match for standard codes
        if v_lower in ["22g1", "42g1", "45g1", "40hc"]: # Add other known standard codes
             # Find the standard casing if needed (e.g., map 40hc to 40HC or 45G1 based on API need)
             if v_lower == "40hc": return "45G1" # Example standardization
             return v.upper()

        # Check mapping
        if v_lower in CONTAINER_TYPE_MAP:
            return CONTAINER_TYPE_MAP[v_lower]

        # Basic regex for patterns like 40'HC, 20BOX etc. (less reliable)
        match_hc = re.search(r"40'?\s*(hc|high)", v_lower)
        if match_hc: return "45G1" # Standardize 40HC
        match_gp = re.search(r"40'?\s*(gp|general)", v_lower)
        if match_gp: return "42G1" # Standardize 40GP
        match_20 = re.search(r"20'?\s*(box|dc|gp|dv)", v_lower)
        if match_20: return "22G1" # Standardize 20ft variants

        print(f"Warning: Unrecognized container type '{v}'. Could not normalize.")
        return v # Return original if no mapping/pattern found, maybe API accepts it

    @field_validator('key_date', mode='before')
    @classmethod
    def validate_and_format_date(cls, v: Any) -> Optional[str]:
        """Parses various date formats and returns ISO 8601 Z format for API."""
        if not v or not isinstance(v, str):
            return None

        formats_to_try = [
            "%d.%m.%Y %H:%M", "%d.%m.%Y",          # DD.MM.YYYY HH:MM, DD.MM.YYYY
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",       # YYYY-MM-DD HH:MM:SS, YYYY-MM-DD
            "%m/%d/%Y %H:%M", "%m/%d/%Y",          # MM/DD/YYYY HH:MM, MM/DD/YYYY
            "%d-%b-%y", "%d-%b-%Y",                # DD-Mon-YY, DD-Mon-YYYY (e.g., 20-Nov-20)
            "%Y%m%d",                             # YYYYMMDD
            # Add more formats if needed
        ]
        parsed_date = None
        v_clean = v.split('T')[0].split('+')[0].strip() # Get date part, remove T part or timezone info for parsing

        for fmt in formats_to_try:
            try:
                parsed_date = datetime.strptime(v_clean, fmt)
                break
            except ValueError:
                continue

        if parsed_date:
            # Check if extracted date is in the past
            now_utc = datetime.now(timezone.utc)
            # Make parsed_date timezone-aware (assume UTC if not specified, for comparison)
            parsed_date_aware = parsed_date.replace(tzinfo=timezone.utc)

            if parsed_date_aware < now_utc - timedelta(days=1): # Allow today
                 print(f"Warning: Extracted date '{v}' is in the past.")
                 # Option 1: Return None, forcing user clarification
                 # return None
                 # Option 2: Default to a future date (e.g., tomorrow noon UTC)
                 future_date = now_utc.replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)
                 print(f"Defaulting key_date to future date: {future_date.isoformat()}")
                 return future_date.strftime('%Y-%m-%dT%H:%M:%SZ') # RFC3339 Z format

            # Date is today or future, format it correctly
            # Use noon UTC if time wasn't parsed
            if not parsed_date.hour and not parsed_date.minute:
                 parsed_date = parsed_date.replace(hour=12, minute=0, second=0)

            return parsed_date.strftime('%Y-%m-%dT%H:%M:%SZ') # RFC3339 Z format
        else:
            # Final check: Is it already in ISO format?
            try:
                 # This parses ISO 8601 including Z or timezone offsets
                 datetime.fromisoformat(v.replace('Z', '+00:00'))
                 # If it parses, ensure it's formatted with Z
                 # Re-parse to handle potential offsets correctly and format to Z
                 dt_obj = datetime.fromisoformat(v.replace('Z', '+00:00'))
                 if dt_obj < datetime.now(timezone.utc) - timedelta(days=1):
                      print(f"Warning: Provided ISO date '{v}' is in the past. Defaulting to future date.")
                      future_date = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=1)
                      return future_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                 return dt_obj.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                 print(f"Warning: Could not parse key_date '{v}' into any known format.")
                 return None # Failed validation

    @field_validator('origin_address', 'destination_address', mode='before')
    @classmethod
    def ensure_address_object(cls, v):
        """Ensure address is an object, even if LLM returns null or string."""
        if isinstance(v, dict):
            return v
        # If LLM returns null or empty string for the whole address, create an empty object
        # so subsequent validation doesn't fail on NoneType access
        elif not v:
            return AddressDetail() # Return empty Pydantic model
        # If LLM returns a single string, try to put it in city (less ideal)
        elif isinstance(v, str):
            print(f"Warning: Address received as string '{v}'. Attempting to use as city.")
            return AddressDetail(city=v)
        return v # Pass through if already correct type or other unexpected type

    # --- Completeness Check ---
    def is_complete_for_api(self) -> bool:
        """Checks if mandatory fields for the API quote request are present AND valid."""
        origin_ok = (
            self.origin_address and
            self.origin_address.city and
            self.origin_address.zip_code and
            self.origin_address.country
        )
        dest_ok = (
            self.destination_address and
            self.destination_address.city and
            self.destination_address.zip_code and
            self.destination_address.country
        )
        container_ok = bool(self.container_type) # Check if not None or empty after normalization
        date_ok = bool(self.key_date) # Check if date survived validation/formatting

        print(f"API Completeness Check: Origin OK={origin_ok}, Dest OK={dest_ok}, Container OK={container_ok}, Date OK={date_ok}")
        return bool(origin_ok and dest_ok and container_ok and date_ok)

    def get_missing_fields(self) -> List[str]:
        """Returns a list of essential fields missing for the API call."""
        missing = []
        # Check Origin Address components
        if not self.origin_address or not self.origin_address.city: missing.append("Origin City")
        if not self.origin_address or not self.origin_address.zip_code: missing.append("Origin Zip Code")
        # Add Street check if needed:
        # if not self.origin_address or not self.origin_address.street: missing.append("Origin Street")

        # Check Destination Address components
        if not self.destination_address or not self.destination_address.city: missing.append("Destination City")
        if not self.destination_address or not self.destination_address.zip_code: missing.append("Destination Zip Code")
        # Add Street check if needed:
        # if not self.destination_address or not self.destination_address.street: missing.append("Destination Street")

        # Check other fields
        if not self.container_type: missing.append("Container Type (e.g., 40HC, 22G1)")
        if not self.key_date: missing.append("Key Date (e.g., Provision/Shipping Date)")

        return missing