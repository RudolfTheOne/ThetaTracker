import logging
import requests
import sys
import math
from dateutil.parser import parse
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

RETRY_WAIT_SECS = 50
STRIKE_COUNT_LIMIT = 20

def make_api_request(api_key, endpoint):
    try:
        response = requests.get(endpoint)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to API: {e}")
        raise

    if response.status_code == 429:
      logging.warning(f"Rate limited. Sleeping {RETRY_WAIT_SECS} seconds")
      time.sleep(RETRY_WAIT_SECS)

    elif response.status_code == 200:
        return response.json()

    else:
        logging.error(f"Error fetching data from API. Status code: {response.status_code}")
        raise Exception(f"API request failed with status {response.status_code}")


def is_market_open(api_key):
    """Check if the market is open."""
    endpoint = f"https://api.tdameritrade.com/v1/marketdata/OPTION/hours?apikey={api_key}"

    data = make_api_request(api_key, endpoint)

    # Check if the response contains the expected data
    if data and "option" in data:
        # Iterate over each product in the option market
        for product in data["option"].values():
            if "isOpen" in product and product["isOpen"]:
                for session in product["sessionHours"]["regularMarket"]:
                    start_time = parse(session["start"])
                    end_time = parse(session["end"])
                    current_time = datetime.now(start_time.tzinfo) # ensures the current time is timezone aware

                    if start_time <= current_time <= end_time:
                        # Market is open for this product
                        return True
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


def handle_api_error(ticker):
    logging.error(f"Error: Unable to make API request for {ticker}")


def fetch_option_for_ticker(api_key, ticker, line_number, contract_type, from_date, to_date, max_delta, buying_power, sorting_method,
                       finnhub_api_key):
    try:
        endpoint = f"https://api.tdameritrade.com/v1/marketdata/chains?apikey={api_key}&symbol={ticker}&contractType={contract_type}&strikeCount={STRIKE_COUNT_LIMIT}&fromDate={from_date.strftime('%Y-%m-%d')}&toDate={to_date.strftime('%Y-%m-%d')}"
        data = make_api_request(api_key, endpoint)

        if not data or "putExpDateMap" not in data:
            handle_api_error(ticker)
            return []

        options = filter_and_sort_options(data, float(max_delta), float(buying_power), sorting_method)

        # Check if we have any options for the ticker
        if options:
            # Compute the maximum expiration_date_str for the current ticker
            expiration_date_str = max(
                (datetime.now() + timedelta(days=option["daysToExpiration"])).strftime('%Y-%m-%d') for option in
                options)

            finnhub_endpoint = f"https://finnhub.io/api/v1/calendar/earnings?from={datetime.now().strftime('%Y-%m-%d')}&to={expiration_date_str}&symbol={ticker}&token={finnhub_api_key}"
            # Try the request up to two times (original try + 1 retry)
            for _ in range(2):
                response = requests.get(finnhub_endpoint)

                if response.status_code == 429:
                    logging.error("Rate limit reached. Waiting {RETRY_WAIT_SECS} seconds before retrying...")
                    time.sleep(RETRY_WAIT_SECS)
                else:
                    break

            if response.status_code == 200 and response.text:
                earnings_data = response.json()
                has_earnings = earnings_data.get('earningsCalendar', []) != []
            else:
                logging.error(
                    f"Error: Unable to fetch earnings data for {ticker}. HTTP status code: {response.status_code}")
                has_earnings = False  # Default value if unable to fetch earnings data

            for option in options:
                option["ticker"] = ticker
                option["line_number"] = line_number
                option["has_earnings"] = has_earnings

        return options

    except requests.exceptions.RequestException as e:
        handle_api_error(ticker)
        logging.exception("There was an exception when making an API request.")
        return []


def fetch_option_chain(api_key, tickers, contract_type, from_date, to_date, max_delta, buying_power, sorting_method,
                       finnhub_api_key):
    all_options = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_option_for_ticker, api_key, ticker, line_number, contract_type, from_date, to_date,
                            max_delta, buying_power, sorting_method, finnhub_api_key): ticker for ticker, line_number in
            tickers}

        for future in as_completed(futures):
            exception = future.exception()
            if exception is not None:
                tickers.remove(futures[future])  # remove the ticker from the list
            else:
                all_options.extend(future.result())

    # Sort all options regardless of their ticker
    if sorting_method == "message":
        all_options.sort(key=lambda option: option.get(sorting_method, ""), reverse=True)
    else:
        all_options.sort(key=lambda option: float(option.get(sorting_method, "Key not present")), reverse=True)

    return all_options
