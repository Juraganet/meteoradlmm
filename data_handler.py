# meteora_app/data_handler.py
import requests
import pandas as pd

API_URL = "https://dlmm-api.meteora.ag/pair/all_with_pagination?limit=100&include_token_mints=So11111111111111111111111111111111111111112"

def fetch_meteora_pairs():
    """
    Fetches pair data from the Meteora API.

    Returns:
        tuple: (pandas.DataFrame, int) containing the pair data and total count.
    Raises:
        requests.exceptions.RequestException: If a network error occurs.
        ValueError: If JSON decoding fails or expected data structure is missing.
    """
    # print(f"data_handler.py: Attempting to fetch from {API_URL}") # Kept for server log, can be commented out
    try:
        response = requests.get(API_URL)
        response.raise_for_status()
        data = response.json()

        if "pairs" in data:
            if data["pairs"]:
                df = pd.DataFrame(data["pairs"])
                total = data.get("total", 0)
                # print(f"data_handler.py: Successfully fetched {len(df)} pairs. Total: {total}") # Kept for server log
                return df, total
            else:
                # print("data_handler.py: API returned 'pairs' key with an empty list.") # Kept for server log
                return pd.DataFrame(), data.get("total", 0)
        else:
            # print("data_handler.py: 'pairs' key missing in API response.") # Kept for server log
            raise ValueError("API response missing 'pairs' key.")

    except requests.exceptions.RequestException as e:
        print(f"data_handler.py: Network error fetching data: {e}") # Important for server logs
        raise
    except ValueError as e:
        print(f"data_handler.py: JSON/Value error: {e}") # Important for server logs
        if 'response' in locals() and hasattr(response, 'text'):
            print(f"data_handler.py: Raw response text (first 500 chars): {response.text[:500]}...")
        raise

if __name__ == '__main__':
    # This test block remains useful for direct module testing
    print("Testing data_handler.py directly...")
    try:
        df_test, total_test = fetch_meteora_pairs()
        if df_test is not None and not df_test.empty:
            print(f"Direct Test: Fetched {len(df_test)} pairs. Total: {total_test}")
            print("Direct Test: Columns:", df_test.columns.tolist())
            print("Direct Test: Head:\n", df_test.head())
        elif df_test is not None:
            print(f"Direct Test: Fetched 0 pairs (empty DataFrame). Total: {total_test}")
        else:
            print("Direct Test: df_test is None, which is unexpected.")
    except Exception as e:
        print(f"Direct Test: An error occurred: {e}")