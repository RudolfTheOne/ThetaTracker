# ThetaTracker
A terminal application for tracking options trading metrics.
This application gets your list of stock tickers and based on your basic parameters displays the most profitable option trades within defined boundaries.
See user config for more details.

The interface:
![theta-tracker-interface.png](resources%2Ftheta-tracker-interface.png)

# Pre-requisites and configuration
The app relies on three main files in order to run effectively:
* system config file `theta_tracker_system.conf`
* user config file `theta_tracker_user.conf`
* stock tickers list to track `tickers2watch.txt`

**System config** file consist of:

`{"api_key": "YOUR_td_ameritrade_api_key", "finnhub_api_key": "YOUR_finnhub_api_key", "refresh_interval": 600}`

In order to obtain your api keys for both portals please visit and register at:
https://developer.tdameritrade.com/apis
and
https://finnhub.io/

**User config** file consist of:

`{"max_delta": 0.3, "dte_range_min": 24, "dte_range_max": 45, "buying_power": 50000.0, "default_sorting_method": "arr"}`

These are the example values and if you don't have this file, the app will ask for your values.

The meaning of the configuration options are:

`max_delta` - this is simply speaking a maximum risk you want to take into account when selling the option. The possible values are between `0.0` and `1.0`. Don't bother with negative sign, just use the absolute value, it will work.

`dte_range_min` - this is a minimum number of days you want to consider when selling the option. Valid values are between `0` (today) and `365`.

`dte_range_max` - this is a maximum number of days you want to consider when selling the option. In other words: second bracket of a time window for your trades. Valid values are between previously entered `dte_range_min` and `365`.

`buying_power` - this is a buying power you want to take into account when trading. **The minimum value is 1000USD**. This might include your margin, but remember - **trading on margin increases your risk!**
The general rule is that this is a hard limit when calculating possible positions by the application. In short: if you want to sell cash secured PUTs, put your available cash on trading account. If you want to sell naked - do what you want but be warned! 🤓

`default_sorting_method` - this parameter tells what should the app use to sort the possible option trades. You should by default use 'arr', as this gives utilizes to the maximum your capital in the assumed time period. Other possible values are: 

    premium_usd
    premium_per_day
    delta

You will be able to change it later, in the app.

**Tickers' list** should be put into the `tickers2watch.txt` file - please note that you might want to put them in a specific order, for instance from the best in the first line to the least attractive in the last one.

The best way to obtain the most attractive list of tickers is to use a tool such as [finviz screener](https://finviz.com/screener.ashx) or even run a script like https://github.com/RudolfTheOne/FinVizStockSelector.

_Note: if you will not provide any list, the application will present option chains for SPY ETF._

# Running the app
Once you have your tickers and proper config files, you run the app and see its main interface.
Here is the explanation of what the app's main interface tells you:
## Header
In this part of the screen the app will report:

![header.png](resources%2Fheader.png)

`ThetaTracker` - its name 😎

`Date: YYYY-MM-DD HH:MM` - current date and time

`Buying power: $XXXXX.00` - your buying power in USD

`Market: Open` - market status (can be `Open` or `Closed`).

## Footer
Bottom part of the interface gives you a brief overview of hotkeys, as:

![footer.png](resources%2Ffooter.png)

`q` - the app will exit

`c` - configuration setup, allowing you to change user config options:

![config.png](resources%2Fconfig.png)

`s` - sorting method, see:

![sorting.png](resources%2Fsorting.png)

`r` - forced refresh: this will force the app to retrieve all the data from the external sources again and refresh displayed position on the screen. It might take a while, especially for larger number of tickets.

## Main window - main element and its details

![position.png](resources%2Fposition.png)

First row displays ticker along its position from the `tickers2watch.txt` file in the square 
bracket. 
The assumption is that if you sorted your tickers from best to worst, you might want to 
consider that info when choosing the trade. 

Next is the most essential data for the trader: **Premium Total** in USD - this 
calculates the total premium you will get for selling the total number of contracts.

**NOTE: this doesn't take into account your trade fees from your broker!**. 

The next value says about premium you will earn per day (that's simply premium total 
divided per days to expiration) followed by ARR. 

The ARR (Annual Return Rate) reflects the percentage rate of return 
expected on an investment extending the result on one trade to a full year. It's the most 
useful indicator of how profitable your trade is in specific time window.

Next are the values showing the Liquidity: BidSize, AskSize and the Spread as a percentage.

Second row gives position RISK details: PUT/CALL ratio (telling you what's the market sentiment, ie how many 
bullish trades to how many bearish trades are there on a market (based on the volume of both).
You will see an emoji icon allowing you to assess the sentiment at a glance. 

Next, there is a stock's IV (underlying's Internal Volatility) followed by the Delta value 
(remember - rule of thumb is **the lower delta, the less risky is the trade**).

Finally the underlying's price followed by difference between this price and the strike price (in the
bracket it will display `d: $2.0 0.04%` meaning the difference between the underlying price 
and the strike price is 2 dollars which translates to 0.04% of the difference.).

Third row displays the details necessary for opening the trade: the option description, it's Strike Price, 
Days to Expiration (DTE) and the number of contracts to write ("No to open"): this tells you 
how many options you can sell having your previously defined buying power.

Note: in case the specific trade's underlying has an earning report within defined time window, you will see a warning: ⚠️📆.

### Ending notes
This app has been written by Chat GPT 4.

Happy trading! 💵💪
