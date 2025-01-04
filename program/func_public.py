from constants import RESOLUTION
from func_utils import get_ISO_times
import pandas as pd
import numpy as np
import time

from pprint import pformat
import logging
logger = logging.getLogger('BotLogger')

# Get relevant time periods for ISO from and to
ISO_TIMES = get_ISO_times()


# Get Candles recent
async def get_candles_recent(indexer, market):

  # Define output
  close_prices = []

  # Protect API
  time.sleep(0.2)

  # Get data
  try:
      response = await indexer.markets.get_perpetual_market_candles(market=market,
                                                                    resolution=RESOLUTION,
                                                                    limit = 100)
      for candle in response["candles"]:
          close_prices.append(candle["close"])
  except Exception as e:
      logger.error(f"Error getting recent candles for market: {market}:,  {e}")  

  # Construct and return close price series
  close_prices.reverse()
  prices_result = np.array(close_prices).astype(np.float32)
  return prices_result


# Get Candles Historical, Ralph Grewe: Need to be aync for V4 API
async def get_candles_historical(indexer, market):

  # Define output
  close_prices = []

  # Extract historical price data for each timeframe
  for timeframe in ISO_TIMES.keys():

    # Confirm times needed
    tf_obj = ISO_TIMES[timeframe]
    from_iso = tf_obj["from_iso"]
    to_iso = tf_obj["to_iso"]

    # Protect rate limits
    time.sleep(0.2)

    # Ralph Grewe: in the "try"- Block, get candles using V4 API
    try:
        response = await indexer.markets.get_perpetual_market_candles(market=market,
                                                                      resolution=RESOLUTION,
                                                                      from_iso = from_iso,
                                                                      to_iso = to_iso,
                                                                      limit = 100)
        for candle in response["candles"]:
            close_prices.append({"datetime": candle["startedAt"], market: candle["close"]})
    except Exception as e:
        logger.error(f"Error getting historical candles: {e}")    

  # Construct and return DataFrame
  close_prices.reverse()
  return close_prices


# Construct market prices, Ralph Grewe: Needs to be async for V4 API
async def construct_market_prices(indexer):

  # Declare variables
  tradeable_markets = []

  # Ralph Grewe: Get Markets using V4 API. Data structure also slightly changed
  markets = await indexer.markets.get_perpetual_markets()

  # Find tradeable pairs
  for market in markets["markets"]:
      if markets["markets"][market]["status"] == 'ACTIVE':
          tradeable_markets.append(market)
      else:
          logger.info("Market not active: ", market)

  # Set initial DateFrame
  close_prices = await get_candles_historical(indexer, tradeable_markets[0])
  df = pd.DataFrame(close_prices)
  df.set_index("datetime", inplace=True)

  # Append other prices to DataFrame
  # You can limit the amount to loop though here to save time in development
  for market in tradeable_markets[1:]:
    # Ralph Grewe: To see some progress when fetching many markets
    logger.info(f"Fetching market: {market}")
    close_prices_add = await get_candles_historical(indexer, market)
    # Ralph Grewe: Adding try/except block to avoid abort if few market data frames have flaws
    try:
      df_add = pd.DataFrame(close_prices_add)
      df_add.set_index("datetime", inplace=True)
      df = pd.merge(df, df_add, how="outer", on="datetime", copy=False)
    except Exception as e:
        logger.error(f"Error merging frame for {market}: {e}")
        logger.debug(pformat(df_add))
    del df_add

  # Check any columns with NaNs
  nans = df.columns[df.isna().any()].tolist()
  if len(nans) > 0:
    logger.info("Dropping columns: ")
    logger.info(nans)
    df.drop(columns=nans, inplace=True)

  # Return result
  return df
