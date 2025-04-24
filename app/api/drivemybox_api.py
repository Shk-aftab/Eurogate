# app/api/drivemybox_api.py
import requests
import json
from typing import Dict, Any, Optional, List

# Import config carefully to avoid circular dependency issues if run directly
try:
    from app.core.config import DRIVEMYBOX_API_BASE_URL, DRIVEMYBOX_API_KEY
except ImportError:
    # Handle case where script might be run directly for testing outside the app context
    # This is less ideal but provides a fallback for simple tests
    import os
    from dotenv import load_dotenv
    print("Warning: Running drivemybox_api.py potentially outside app context. Loading .env directly.")
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)
    DRIVEMYBOX_API_KEY = os.getenv("DRIVEMYBOX_API_KEY")
    DRIVEMYBOX_API_BASE_URL = os.getenv("DRIVEMYBOX_API_BASE_URL", "https://api.placeholder.drivemybox.io/v1")


def get_price_quotation(route_data: Dict[str, Any], container_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Calls the DriveMyBox API to get a price quotation.

    Args:
        route_data: Dictionary representing the route structure.
        container_data: List of dictionaries representing container info.

    Returns:
        Dictionary with the API response or None if an error occurs.
    """
    if not DRIVEMYBOX_API_KEY or "api.placeholder.drivemybox.io" in DRIVEMYBOX_API_BASE_URL:
        print("Error: DriveMyBox API Key or Base URL is not configured correctly. Cannot call API.")
        return None

    # Ensure the base URL doesn't end with a slash, and the endpoint starts with one
    api_endpoint = f"{DRIVEMYBOX_API_BASE_URL.rstrip('/')}/quotations" # Adjust endpoint path if needed

    headers = {
        "Content-Type": "application/json",
        "x-api-key": DRIVEMYBOX_API_KEY
    }
    payload = {
        "route": route_data,
        "containers": container_data
    }

    print(f"Calling DriveMyBox Quotation API: {api_endpoint}")
    # print(f"Payload: {json.dumps(payload, indent=2)}") # Uncomment for debugging

    try:
        response = requests.post(api_endpoint, headers=headers, json=payload, timeout=45) # Increased timeout
        print(f"API Response Status Code: {response.status_code}")
        response.raise_for_status()  # Raise an exception for 4xx or 5xx
        return response.json()
    except requests.exceptions.Timeout:
        print(f"Error: Timeout calling DriveMyBox API endpoint: {api_endpoint}")
        return None
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred calling DriveMyBox API: {http_err}")
        error_details = {}
        try:
            error_details = response.json()
            print(f"Error Response Body: {json.dumps(error_details, indent=2)}")
        except json.JSONDecodeError:
            print(f"Error Response Body (non-JSON): {response.text}")
        # You might want to return the error details in some cases
        return {"error": True, "status_code": response.status_code, "details": error_details or response.text}
    except requests.exceptions.RequestException as req_err:
        print(f"Error calling DriveMyBox API (RequestException): {req_err}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response from DriveMyBox API.")
        print(f"Raw Response Text: {response.text}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during API call: {type(e).__name__} - {e}")
        return None

# --- Example Usage (for direct testing) ---
if __name__ == "__main__":
    if "api.placeholder.drivemybox.io" in DRIVEMYBOX_API_BASE_URL:
        print("\nCannot run API test with placeholder URL. Set correct URL in .env")
    else:
        sample_route = { # Example based on previous context
          "route_loading_points": [
            {"address": {"city": "Hamburg", "street": "Kurt-Eckelmann-Straße 1", "country": "DE", "discriminator":"structured_address"}, "type": "TERMINAL", "sequence_number": 1, "pickup_location": True, "discriminator":"loading_point"},
            {"address": {"city": "Nürnberg", "street": "Rheinstrasse 40", "country": "DE", "discriminator":"structured_address"}, "type": "WAREHOUSE", "sequence_number": 2, "dropoff_location": True, "discriminator":"loading_point"}
          ]
        }
        sample_containers = [{"sequence_number": 1, "type_code": "40HC", "provision_at": "2025-12-01T10:00:00Z"}]

        print("\nTesting DriveMyBox API call with sample data...")
        quotation = get_price_quotation(sample_route, sample_containers)

        if quotation:
            print("\nAPI Response:")
            print(json.dumps(quotation, indent=2))
        else:
            print("\nAPI call failed or returned no data.")