import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

PLANE_API_KEY = os.getenv("PLANE_API_KEY")
PLANE_URL = os.getenv("PLANE_URL")

logger = logging.getLogger(__name__)

def test_plane_connection():
    """
    Test the connection to the Plane API and fetch the user's details.
    """
    # The correct base path for the API token is /api/v1/
    url = f"{PLANE_URL}/api/v1/users/me/"
    
    headers = {
        "X-Api-Key": PLANE_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        user_data = response.json()
        logger.info(f"Successfully connected! Authenticated as: {user_data.get('email', 'Unknown')} ({user_data.get('display_name', 'Unknown')})")
        return user_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to Plane API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response body: {e.response.text}")
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_plane_connection()
