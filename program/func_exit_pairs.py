from constants import CLOSE_AT_ZSCORE_CROSS
from func_utils import format_number
from func_public import get_candles_recent
from func_cointegration import calculate_zscore
from func_private import place_market_order, get_open_positions, get_order_by_client_id
import json
import time

# Ralph Grewe additional oimports
from v4_proto.dydxprotocol.clob.order_pb2 import Order
from pprint import pformat
import logging
logger = logging.getLogger('BotLogger')

# Manage trade exits
async def manage_trade_exits(node, indexer, wallet):

  """
    Manage exiting open positions
    Based upon criteria set in constants
  """

  # Initialize saving output
  save_output = []

  # Opening JSON file
  try:
    open_positions_file = open("bot_agents.json")
    open_positions_dict = json.load(open_positions_file)
  except:
    logger.info("Couldn't open file bot_agents.json.")
    return "complete"

  # Guard: Exit if no open positions in file
  if len(open_positions_dict) < 1:
    logger.debug("No open positions in bot_agents.json")
    return "complete"
  
  # Get all open positions per trading platform
  exchange_positions = await get_open_positions(indexer)
  markets_live = []
  for position in exchange_positions:
    markets_live.append(position["market"])

  # Protect API
  time.sleep(0.5)

  # Check all saved positions match order record
  # Exit trade according to any exit trade rules
  for position in open_positions_dict:

    # Initialize is_close trigger
    is_close = False

    # Extract position matching information from file - market 1
    position_market_m1 = position["market_1"]
    position_size_m1 = float(position["order_m1_size"])
    position_side_m1 = position["order_m1_side"]

    # Extract position matching information from file - market 2
    position_market_m2 = position["market_2"]
    position_size_m2 = float(position["order_m2_size"])
    position_side_m2 = position["order_m2_side"]

    # Protect API
    time.sleep(0.5)

    # Get order info m1 per exchange
    logger.info(f"Order M1 ID:  {position['order_m1_id']}")
    order_m1 = await get_order_by_client_id(indexer, position["order_m1_id"])
    order_market_m1 = order_m1["ticker"]
    order_size_m1 = float(order_m1["size"])
    if order_m1["side"] == "SELL":
      order_side_m1 = Order.SIDE_SELL
    else:
      order_side_m1 = Order.SIDE_BUY


    # Protect API
    time.sleep(0.5)

    # Get order info m2 per exchange
    order_m2 = await get_order_by_client_id(indexer, position["order_m2_id"])
    order_market_m2 = order_m2["ticker"]
    order_size_m2 = float(order_m2["size"])
    if order_m2["side"] == "SELL":
      order_side_m2 = Order.SIDE_SELL
    else:
      order_side_m2 = Order.SIDE_BUY


    # Perform matching checks
    check_m1 = position_market_m1 == order_market_m1 and position_size_m1 == order_size_m1 and position_side_m1 == order_side_m1
    check_m2 = position_market_m2 == order_market_m2 and position_size_m2 == order_size_m2 and position_side_m2 == order_side_m2
    check_live = position_market_m1 in markets_live and position_market_m2 in markets_live

    # Guard: If not all match exit with error
    logger.info(f"checkm1: {position_market_m1}, {order_market_m1}; size: {position_size_m1}, {order_size_m1}; side: {position_side_m1}, {order_side_m1}")
    logger.info(f"checkm2: {position_market_m2}, {order_market_m2}; size: {position_size_m2}, {order_size_m2}; side: {position_side_m2}, {order_side_m2}")
    if not check_m1 or not check_m2 or not check_live:
      logger.error(f"Warning: Not all open positions match exchange records for {position_market_m1} and {position_market_m2}")
      continue

    # Get prices
    logger.debug("Getting candles")
    series_1 = await get_candles_recent(indexer, position_market_m1)
    time.sleep(0.2)
    series_2 = await get_candles_recent(indexer, position_market_m2)
    time.sleep(0.2)

    # Get markets for reference of tick size
    markets = await indexer.markets.get_perpetual_markets()
    # Protect API
    time.sleep(0.2)

    # Trigger close based on Z-Score
    if CLOSE_AT_ZSCORE_CROSS:
      logger.debug("Checking Z-Score")

      # Initialize z_scores
      hedge_ratio = float(position["hedge_ratio"])
      z_score_traded = float(position["z_score"])
      if len(series_1) > 0 and len(series_1) == len(series_2):
        spread = series_1 - (hedge_ratio * series_2)
        z_score_current = calculate_zscore(spread).values.tolist()[-1]

        # Determine trigger
        z_score_level_check = abs(z_score_current) >= abs(z_score_traded)
        z_score_cross_check = (z_score_current < 0 and z_score_traded > 0) or (z_score_current > 0 and z_score_traded < 0)

        logger.info(f"{order_market_m1} vs {order_market_m2}: zscore {z_score_current}")
        # Close trade
        if z_score_level_check and z_score_cross_check:

          # Initiate close trigger
          is_close = True

    ###
    # Add any other close logic you want here
    # Trigger is_close
    ###
    logger.debug(f"Closing position is: {is_close}")
    # Close positions if triggered
    if is_close:

      # Determine side - m1
      side_m1 = "SELL"
      if position_side_m1 == "SELL":
        side_m1 = "BUY"

      # Determine side - m2
      side_m2 = "SELL"
      if position_side_m2 == "SELL":
        side_m2 = "BUY"

      # Get and format Price
      price_m1 = float(series_1[-1])
      price_m2 = float(series_2[-1])
      accept_price_m1 = price_m1 * 1.05 if side_m1 == "BUY" else price_m1 * 0.95
      accept_price_m2 = price_m2 * 1.05 if side_m2 == "BUY" else price_m2 * 0.95
      tick_size_m1 = float(markets["markets"][position_market_m1]["tickSize"])
      tick_size_m2 = float(markets["markets"][position_market_m2]["tickSize"])
      accept_price_m1 = float(format_number(accept_price_m1, tick_size_m1))
      accept_price_m2 = float(format_number(accept_price_m2, tick_size_m2))

      # Close positions
      logger.info("Placing oders for closing...")
      try:

        # Close position for market 1
        logger.info(">>> Closing market 1 <<<")
        logger.info(f"Closing position for {position_market_m1}")

        close_order_size, close_order_m1_transaction, close_order_m1 = await place_market_order(
          node,
          indexer,
          wallet,
          market=position_market_m1,
          side=side_m1,
          size=position_size_m1,
          price=accept_price_m1,
          reduce_only=True,
        )

        logger.info(close_order_m1["order"]["id"])
        logger.info(">>> Closing <<<")

        # Protect API
        time.sleep(1)

        # Close position for market 2
        logger.info(">>> Closing market 2 <<<")
        logger.info(f"Closing position for {position_market_m2}")

        close_order_size, close_order_m2_transaction, close_order_m2 = await place_market_order(
          node,
          indexer,
          wallet,
          market=position_market_m2,
          side=side_m2,
          size=position_size_m2,
          price=accept_price_m2,
          reduce_only=True,
        )

        logger.info(close_order_m2["order"]["id"])
        logger.info(">>> Closing <<<")

      except Exception as e:
        logger.info(f"Exit failed for {position_market_m1} with {position_market_m2}")
        save_output.append(position)

    # Keep record if items and save
    else:
      save_output.append(position)

  # Save remaining items
  logger.info(f"{len(save_output)} Items remaining. Saving file...")
  with open("bot_agents.json", "w") as f:
    json.dump(save_output, f)
