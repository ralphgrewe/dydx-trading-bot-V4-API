from constants import ZSCORE_THRESH, USD_PER_TRADE, USD_MIN_COLLATERAL, DYDX_ADDRESS
from func_utils import format_number
from func_public import get_candles_recent
from func_cointegration import calculate_zscore
from func_private import is_open_positions
from func_bot_agent import BotAgent
import pandas as pd
import json

# Ralph Grewe: Additional Imports
from pprint import pformat
import time
from v4_proto.dydxprotocol.clob.order_pb2 import Order
import logging
logger = logging.getLogger('BotLogger')

# Open positions
async def open_positions(node, indexer, wallet):

  """
    Manage finding triggers for trade entry
    Store trades for managing later on on exit function
  """

  # Load cointegrated pairs
  df = pd.read_csv("cointegrated_pairs.csv")

  # Get markets from referencing of min order size, tick size etc
  # Ralph Grewe: Get Markets using V4 API. Data structure also slightly changed
  markets = await indexer.markets.get_perpetual_markets()

  # Initialize container for BotAgent results
  bot_agents = []

  # Opening JSON file
  try:
    open_positions_file = open("bot_agents.json")
    open_positions_dict = json.load(open_positions_file)
    for p in open_positions_dict:
      bot_agents.append(p)
  except:
    bot_agents = []
  
  # Find ZScore triggers
  for index, row in df.iterrows():

    # Extract variables
    base_market = row["base_market"]
    quote_market = row["quote_market"]
    hedge_ratio = float(row["hedge_ratio"])
    half_life = float(row["half_life"])

    # Get prices
    time.sleep(1)
    series_1 = await get_candles_recent(indexer, base_market)
    series_2 = await get_candles_recent(indexer, quote_market)

    # Get ZScore
    if len(series_1) > 0 and len(series_1) == len(series_2):
      spread = series_1 - (hedge_ratio * series_2)
      z_score = calculate_zscore(spread).values.tolist()[-1]

      logger.info(f"Base market: {base_market}, quote market: {quote_market}, z_score: {z_score}")

      # Establish if potential trade
      if abs(z_score) >= ZSCORE_THRESH:

        # Ensure like-for-like not already open (diversify trading)
        is_base_open = await is_open_positions(indexer, base_market)
        is_quote_open = await is_open_positions(indexer, quote_market)

        # Place trade
        if not is_base_open and not is_quote_open:
          logger.info(f"Checking potential trade...")

          # Determine side
          base_side = Order.SIDE_BUY if z_score < 0 else Order.SIDE_SELL
          quote_side = Order.SIDE_BUY if z_score > 0 else Order.SIDE_SELL

          # Get acceptable price in string format with correct number of decimals
          base_price = series_1[-1]
          quote_price = series_2[-1]
          accept_base_price = float(base_price) * 1.01 if z_score < 0 else float(base_price) * 0.99
          accept_quote_price = float(quote_price) * 1.01 if z_score > 0 else float(quote_price) * 0.99
          failsafe_base_price = float(base_price) * 0.05 if z_score < 0 else float(base_price) * 1.7
          base_tick_size = markets["markets"][base_market]["tickSize"]
          quote_tick_size = markets["markets"][quote_market]["tickSize"]

          # Format prices
          accept_base_price = float(format_number(accept_base_price, base_tick_size))
          accept_quote_price = float(format_number(accept_quote_price, quote_tick_size))
          accept_failsafe_base_price = float(format_number(failsafe_base_price, base_tick_size))

          # Get size
          base_quantity = 1 / base_price * USD_PER_TRADE
          quote_quantity = 1 / quote_price * USD_PER_TRADE
          base_step_size = float(markets["markets"][base_market]["stepSize"])
          quote_step_size = float(markets["markets"][quote_market]["stepSize"])

          # Format sizes
          base_size = float(format_number(base_quantity, base_step_size))
          quote_size = float(format_number(quote_quantity, quote_step_size))

          # Ensure size
          check_base = float(base_quantity) > float(base_step_size)
          check_quote = float(quote_quantity) > float(quote_step_size)

          # If checks pass, place trades
          if check_base and check_quote:

            # Check account balance, Ralph Grewe: Using V4 API
            account_response = await indexer.account.get_subaccounts(DYDX_ADDRESS)
            free_collateral = float(account_response["subaccounts"][0]["freeCollateral"])
            logger.info(f"Balance: {free_collateral} and minimum at {USD_MIN_COLLATERAL}")

            # Guard: Ensure collateral
            if free_collateral < USD_MIN_COLLATERAL:
              logger.info(f"Insufficient collateral.")
              break

            # Create Bot Agent
            bot_agent = BotAgent(
              node,
              indexer,
              wallet,
              market_1=base_market,
              market_2=quote_market,
              base_side=base_side,
              base_size=base_size,
              base_price=accept_base_price,
              quote_side=quote_side,
              quote_size=quote_size,
              quote_price=accept_quote_price,
              accept_failsafe_base_price=accept_failsafe_base_price,
              z_score=z_score,
              half_life=half_life,
              hedge_ratio=hedge_ratio
            )

            # Open Trades
            bot_open_dict = await bot_agent.open_trades()

            # Guard: Handle failure
            if bot_open_dict == "failed":
              continue

            # Handle success in opening trades
            logger.info(f"bot_open_dict: {bot_open_dict}")
            if bot_open_dict["pair_status"] == "LIVE":

              # Append to list of bot agents
              bot_agents.append(bot_open_dict)
              del(bot_open_dict)

              # Confirm live status in print
              logger.info("Trade status: Live")
              logger.info("---")
          else:
            logger.info(f"Quantities failed: base quantity {base_quantity}, base step size {base_step_size}, quote quantity {quote_quantity}, quote step size {quote_step_size}")

  # Save agents
  logger.info(f"Success: Manage open trades checked")
  if len(bot_agents) > 0:
    with open("bot_agents.json", "w") as f:
      json.dump(bot_agents, f)
