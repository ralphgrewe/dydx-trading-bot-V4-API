from datetime import datetime, timedelta
from func_utils import format_number
import time
import json

from pprint import pprint

#Ralph Grewe: Additional Imports
from constants import DYDX_ADDRESS
from dydx_v4_client.node.market import Market
from dydx_v4_client import MAX_CLIENT_ID, OrderFlags
from v4_proto.dydxprotocol.clob.order_pb2 import Order, OrderId
from dydx_v4_client.indexer.rest.constants import OrderType
import random

# Get existing open positions
def is_open_positions(client, market):

  # Protect API
  time.sleep(0.2)

  # Get positions
  all_positions = client.private.get_positions(
    market=market,
    status="OPEN"
  )

  # Determine if open
  if len(all_positions.data["positions"]) > 0:
    return True
  else:
    return False


# Check order status
def check_order_status(client, order_id):
  order = client.private.get_order_by_id(order_id)
  if order.data:
    if "order" in order.data.keys():
      return order.data["order"]["status"]
  return "FAILED"

# Ralph Grewe: Function to place market order using V4 API. 
async def place_market_order(indexer, node, wallet, market_id, side, size, price, reduce_only):
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

    transaction = await node.place_order(
        wallet=wallet,
        order=new_order,
    )
    wallet.sequence += 1

    return transaction

# Ralph Grewe: OrderId is given back a string
# Trying to reconstruc the OrderId required for cancelling - no idea if it's working...
async def order_id_from_json(indexer, order_id_string):
  order = await indexer.account.get_order(order_id_string)
  markets = await indexer.markets.get_perpetual_markets(order['ticker'])
  market = Market(markets["markets"][order['ticker']])  
  order_id = market.order_id(DYDX_ADDRESS, 0, int(order['clientId']), int(order['orderFlags']))

  return order, order_id

# Abort all open positions
# Ralph Grewe: Additional function to cancel all orders
async def cancel_all_orders(node, indexer, wallet):
  # Ralph Grewe: Only using subaccount 0 - should be extended to all subaccounts like for positions.
  open_orders = await indexer.account.get_subaccount_orders(DYDX_ADDRESS, 0, status="OPEN")
  good_til_block = await node.latest_block_height()
  for order in open_orders:
      order, order_id = await order_id_from_json(indexer, order['id'])
      if int(order['orderFlags']) == OrderFlags.LONG_TERM:
        blockTime = datetime.fromisoformat(order['goodTilBlockTime'])
        cancel = await node.cancel_order(wallet, order_id, good_til_block_time=int(blockTime.timestamp()))
      else:
        good_til_block = int(order['goodTilBlock'])
        cancel = await node.cancel_order(wallet, order_id, good_til_block=good_til_block)
      pprint(cancel)

# Ralph Grewe: Get open (perpetual) positions
async def get_open_positions(indexer):
  open_positions = []

  try:
      response = await indexer.account.get_subaccounts(DYDX_ADDRESS)
      subaccounts = response["subaccounts"]
      if subaccounts is None:
          print("Subaccounts is None")
      else:
          for subaccount in subaccounts:
              subaccount_number = subaccount["subaccountNumber"]
              response = await indexer.account.get_subaccount(DYDX_ADDRESS, subaccount_number)
              subaccount = response["subaccount"]

              response = await indexer.account.get_subaccount_perpetual_positions(DYDX_ADDRESS, subaccount_number, status='OPEN')
              if response is None:
                  print("Perpetual Positions Response is None")
              else:
                  positions = response["positions"]
                  if positions is None:
                      print("Perpetual Positions is None")
                  for position in positions:
                      open_positions.append(position)

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
          side = Order.Side.SIDE_SELL
      else:
          side = Order.Side.SIDE_BUY        

      # Get Price
      price = float(position["entryPrice"])
      accept_price = price * 1.7 if side == Order.Side.SIDE_BUY else price * 0.3
      tick_size = markets["markets"][market]["tickSize"]
      accept_price = float(format_number(accept_price, tick_size))

      # Place order to close
      print("Placing Order")
      order = await place_market_order(
        indexer,
        node,
        wallet,
        market,
        side,
        float(position["sumOpen"]),
        accept_price,
        True
      )
      print("Order placed")

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
