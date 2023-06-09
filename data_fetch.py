import logging

import requests
import sys
import math

def make_api_request(api_key, endpoint):
    """Make an API request to the given endpoint."""
    try:
        response = requests.get(endpoint)
    except requests.exceptions.RequestException as e:
        print(f"Error: Unable to connect to the API. {e}")
        return None

    # Check if the request was successful
    if response.status_code != 200:
        print(f"Error: Unable to fetch data. Status code: {response.status_code}")
        sys.exit(1)

    return response.json()


def is_market_open(api_key):
    """Check if the market is open."""
    # Define the API endpoint
    endpoint = f"https://api.tdameritrade.com/v1/marketdata/OPTION/hours?apikey={api_key}"

    data = make_api_request(api_key, endpoint)

    # Check if the response contains the expected data
    if data and "option" in data:
        # Iterate over each product in the option market
        for product in data["option"].values():
            if "isOpen" in product and product["isOpen"]:
                # Market is open for this product
                return True
        # No open market found
        return False

    print("Error: The API response did not contain the expected data.")
    sys.exit(1)
def filter_and_sort_options(data, max_delta, buying_power, sorting_method):
    """Filter options based on the delta range and calculate the ARR for each option."""
    options = []
    put_exp_date_map = data.get("putExpDateMap", {})
    for date in put_exp_date_map:
        for strike_price in put_exp_date_map[date]:
            for option in put_exp_date_map[date][strike_price]:
                option['underlyingPrice'] = data['underlyingPrice']
                delta = abs(float(option["delta"]))
                if 0 <= delta <= max_delta:
                    option["delta"] = abs(float(option["delta"]))
                    option["no_of_contracts_to_write"] = math.floor(buying_power / (float(option["strikePrice"]) * 100))
                    if option["no_of_contracts_to_write"] < 1:
                        option["message"] = "Not enough buying power"
                    option["premium_usd"] = round(option["no_of_contracts_to_write"] * float(option["bid"]) * 100, 2)
                    option["premium_per_day"] = round(option["premium_usd"] / option["daysToExpiration"] \
                                                      if option["daysToExpiration"] != 0 else \
                                                      option["premium_usd"], 2)
                    option["arr"] = round(option["premium_usd"] / buying_power * 365 / int(option["daysToExpiration"]) * 100, 3)
                    options.append(option)

    options = sorted(options, key=lambda option: option.get(sorting_method, -1), reverse=True)[:5]
    return options


def fetch_option_chain(api_key, tickers, contract_type, from_date, to_date, max_delta, buying_power, sorting_method):
    all_options = []
    for ticker in tickers:
        endpoint = f"https://api.tdameritrade.com/v1/marketdata/chains?apikey={api_key}&symbol={ticker}&contractType={contract_type}&fromDate={from_date.strftime('%Y-%m-%d')}&toDate={to_date.strftime('%Y-%m-%d')}"
        data = make_api_request(api_key, endpoint)

        # Check if the 'putExpDateMap' key exists in the data
        if not data or "putExpDateMap" not in data:
            print(f"Error: Unable to fetch options for {ticker}.")
            continue

        options = filter_and_sort_options(data, max_delta, buying_power, sorting_method)
        # Add ticker value to each option dictionary
        for option in options:
            option["ticker"] = ticker

        all_options.extend(options)

    # Sort all options regardless of their ticker
    if sorting_method == "message":
        all_options.sort(key=lambda option: option.get(sorting_method, ""), reverse=True)
    else:
        all_options.sort(key=lambda option: float(option.get(sorting_method, "Key not present")), reverse=True)
    # logging.debug(f'All options sorted by {sorting_method}')

    return all_options