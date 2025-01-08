from datetime import datetime, timedelta
from func_utils import format_number
import time
import json

from pprint import pformat

#Ralph Grewe: Additional Imports
from constants import DYDX_ADDRESS
from dydx_v4_client.node.market import Market
from dydx_v4_client import MAX_CLIENT_ID, OrderFlags
from v4_proto.dydxprotocol.clob.order_pb2 import Order
from dydx_v4_client.indexer.rest.constants import OrderType
from pprint import pformat
import random
import logging
logger = logging.getLogger('BotLogger')

# Get existing open positions
async def is_open_positions(indexer, market):
  open_positions = []

  # Protect API
  time.sleep(0.2)

  # Get positions
  try:
      response = await indexer.account.get_subaccounts(DYDX_ADDRESS)
      subaccounts = response["subaccounts"]
      if subaccounts is None:
          logger.info("Subaccounts is None")
      else:
          for subaccount in subaccounts:
              subaccount_number = subaccount["subaccountNumber"]
              response = await indexer.account.get_subaccount(DYDX_ADDRESS, subaccount_number)
              subaccount = response["subaccount"]

              response = await indexer.account.get_subaccount_perpetual_positions(DYDX_ADDRESS, subaccount_number, status='OPEN')
              if response is None:
                  logger.info("Perpetual Positions Response is None")
              else:
                  positions = response["positions"]
                  if positions is None:
                      logger.info("Perpetual Positions is None")
                  for position in positions:
                      if position['market'] == market:
                        open_positions.append(position)
      logger.debug(f"is_open_positions() for market {market}:")
      logger.debug(pformat(open_positions))
  except Exception as e:
      logger.error(f"Error in is_open_positions(), market {market}: {e}")
      exit(1)

  # Determine if open
  if len(open_positions) > 0:
    return True
  else:
    return False

# Ralph Grewe: Function to place market order using V4 API. 
async def place_market_order(node, indexer, wallet, market_id, side, size, price, reduce_only):
    markets = await indexer.markets.get_perpetual_markets(market_id)
    market = Market(markets["markets"][market_id])     
    order_id = market.order_id(
        DYDX_ADDRESS, 0, random.randint(0, MAX_CLIENT_ID), OrderFlags.SHORT_TERM
    )

    good_til_block = await node.latest_block_height() + 10
    new_order = market.order(
        order_id = order_id,
        order_type = OrderType.MARKET,
        side = side,
        size = size,
        price = price,
        time_in_force=Order.TimeInForce.TIME_IN_FORCE_UNSPECIFIED,
        reduce_only = reduce_only,
        good_til_block = good_til_block
    )
    realized_order_size = float(new_order.quantums) / (10.0 ** -market.market["atomicResolution"])
    logger.debug(f"Quantums: {new_order.quantums}, realized order size: {realized_order_size}")

    transaction = await node.place_order(
        wallet=wallet,
        order=new_order,
    )
    wallet.sequence += 1

    return realized_order_size, transaction, new_order

# Ralph Grewe: OrderId is given back a string
# Trying to reconstruc the OrderId required for cancelling - no idea if it's working...
async def cancel_order(node, indexer, wallet, order_id_string):
  order = await indexer.account.get_order(order_id_string)
  markets = await indexer.markets.get_perpetual_markets(order['ticker'])
  market = Market(markets["markets"][order['ticker']])  
  order_id = market.order_id(DYDX_ADDRESS, 0, int(order['clientId']), int(order['orderFlags']))

  if int(order['orderFlags']) == OrderFlags.LONG_TERM:
    blockTime = datetime.fromisoformat(order['goodTilBlockTime'])
    cancel = await node.cancel_order(wallet, order_id, good_til_block_time=int(blockTime.timestamp()))
    logger.debug(pformat(f"Canceled Long Term Order: {order}"))
  else:
    good_til_block = int(order['goodTilBlock'])
    cancel = await node.cancel_order(wallet, order_id, good_til_block=good_til_block)
    logger.debug(pformat(f"Canceled Short Term Order: {order}"))

  logger.debug(pformat(f"Result: {cancel}"))  
  return cancel

# Abort all open positions
# Ralph Grewe: Additional function to cancel all orders
async def cancel_all_orders(node, indexer, wallet):
  # Ralph Grewe: Only using subaccount 0 - should be extended to all subaccounts like for positions.
  open_orders = await indexer.account.get_subaccount_orders(DYDX_ADDRESS, 0, status="OPEN")
  for order in open_orders:
      cancel_order(node, indexer, wallet, order['id'])

# Ralph Grewe: Get open (perpetual) positions
async def get_open_positions(indexer):
  open_positions = []

  try:
      response = await indexer.account.get_subaccounts(DYDX_ADDRESS)
      subaccounts = response["subaccounts"]
      if subaccounts is None:
          logger.info("Subaccounts is None")
      else:
          for subaccount in subaccounts:
              subaccount_number = subaccount["subaccountNumber"]
              response = await indexer.account.get_subaccount(DYDX_ADDRESS, subaccount_number)
              subaccount = response["subaccount"]

              response = await indexer.account.get_subaccount_perpetual_positions(DYDX_ADDRESS, subaccount_number, status='OPEN')
              if response is None:
                  logger.info("Perpetual Positions Response is None")
              else:
                  positions = response["positions"]
                  if positions is None:
                      logger.info("Perpetual Positions is None")
                  for position in positions:
                      open_positions.append(position)
      logger.debug(pformat(f"Open Positions: {open_positions}"))
  except Exception as e:
      print(f"Error getting open positions: {e}")
      exit(1)
  
  return open_positions

# Abort all open positions
async def abort_all_positions(node, indexer, wallet):
  
  # Cancel all orders
  # Ralph Grewe: Using the V4 API function defined above
  # Ralph Grewe: Not sure if this makes a lot of sense as the trading bot uses "Market" orders (OrderTyp.MARKET)
  # Ralph Grewe: which only exist for a few blocks (<20 max). 
  await cancel_all_orders(node, indexer, wallet)

  # Protect API
  time.sleep(0.5)

  # Get markets for reference of tick size
  markets = await indexer.markets.get_perpetual_markets()

  # Protect API
  time.sleep(0.5)

  # Get all open positions
  all_positions = await get_open_positions(indexer)

  # Handle open positions
  close_orders = []
  if len(all_positions) > 0:

    # Loop through each position
    for position in all_positions:

      # Determine Market
      market = position["market"]

      # Determine Side
      if position['side'] == 'LONG':
          side = Order.SIDE_SELL
      else:
          side = Order.SIDE_BUY        

      # Get Price
      price = float(position["entryPrice"])
      accept_price = price * 1.7 if side == Order.SIDE_BUY else price * 0.3
      tick_size = markets["markets"][market]["tickSize"]
      accept_price = float(format_number(accept_price, tick_size))

      # Place order to close
      order = await place_market_order(
        node,
        indexer,
        wallet,
        market,
        side,
        float(position["sumOpen"]),
        accept_price,
        True
      )

      # Append the result
      close_orders.append(order)

      # Protect API
      time.sleep(0.2)

    # Override json file with empty list
    bot_agents = []
    with open("bot_agents.json", "w") as f:
      json.dump(bot_agents, f)

    # Return closed orders
    return close_orders

async def get_order_by_client_id(indexer, order_client_id, order_market=None, order_size=None, order_side=None):
    order_result = None
    try:
      orders = await indexer.account.get_subaccount_orders(DYDX_ADDRESS, 0)
      for order in orders:
        if int(order["clientId"]) == int(order_client_id):
          # Ralph Grewe: Further checks should be added to verify it's the order we are looking for. It's not guaranteed that clientID is only used once.
          logger.debug(pformat(order))
          if order_market != None:
            if order["ticker"] != order_market:
              continue
          if order_size != None:
            if order["size"] != order_size:
              continue
          if order_side != None:
            if order["side"] != order_side:
              continue
          order_result = order
    except Exception as e:
        print(f"Exception when retrieving order status: {e}")

    return order_result