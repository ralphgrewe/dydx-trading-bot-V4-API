from func_private import place_market_order, cancel_order, get_order_by_client_id
from datetime import datetime, timedelta
import time

from pprint import pformat

# Ralph Grewe: Additional Imports
from google.protobuf.json_format import MessageToJson
import logging
logger = logging.getLogger('BotLogger')

# Class: Agent for managing opening and checking trades
class BotAgent:
  

  """
    Primary function of BotAgent handles opening and checking order status
  """

  # Initialize class
  def __init__(
    self,
    node,
    indexer,
    wallet,
    market_1,
    market_2,
    base_side,
    base_size,
    base_price,
    quote_side,
    quote_size,
    quote_price,
    accept_failsafe_base_price,
    z_score,
    half_life,
    hedge_ratio,
  ):

    # Initialize class variables
    self.node = node
    self.indexer = indexer
    self.wallet = wallet
    self.market_1 = market_1
    self.market_2 = market_2
    self.base_side = base_side
    self.base_size = base_size
    self.base_price = base_price
    self.quote_side = quote_side
    self.quote_size = quote_size
    self.quote_price = quote_price
    self.accept_failsafe_base_price = accept_failsafe_base_price
    self.z_score = z_score
    self.half_life = half_life
    self.hedge_ratio = hedge_ratio

    # Initialze output variable
    # Pair status options are FAILED, LIVE, CLOSE, ERROR
    self.order_dict = {
      "market_1": market_1,
      "market_2": market_2,
      "hedge_ratio": hedge_ratio,
      "z_score": z_score,
      "half_life": half_life,
      "order_m1_id": "",
      "order_m1_size": base_size,
      "order_m1_side": base_side,
      "order_m1_time": "",
      "order_m2_id": "",
      "order_m2_size": quote_size,
      "order_m2_side": quote_side,
      "order_m2_time": "",
      "pair_status": "",
      "comments": "",
    }

  # Check order status by id
  async def check_order_status_by_id(self, order_client_id):

    # Allow time to process
    time.sleep(2)

    # Ralph Grewe: It's a bit more difficult here because we only have the order_id object and not the string,
    # which usally is used by get_order(). We have to find the right order by the client ID.
    # Furthermore, I assume that failed orders never show up - so if we don't find an order with the client ID, we assume it's faild
    order = await get_order_by_client_id(self.indexer, order_client_id)
    if order == None:
      return "error"

   # Extract order status
    order_status = order["status"]

    # Guard: If order cancelled move onto next Pair
    if order_status == "CANCELED":
      logger.info(f"{self.market_1} vs {self.market_2} - Order cancelled...")
      self.order_dict["pair_status"] = "FAILED"
      return "failed"
    
    # Ralph Grewe: Looks as if this was missing - or a "FAILED" status would lead to a "live" order
    if order_status == "FAILED":
      logger.info(f"{self.market_1} vs {self.market_2} - Order failed...")
      self.order_dict["pair_status"] = "FAILED"
      return "failed"
    # Guard: If order not filled wait until order expiration
    else:
      logger.debug("Waiting for order to be fullfilled before checking again...")
      time.sleep(15)
      order = await get_order_by_client_id(self.indexer, order_client_id)
      if order == None:
        return "error"
      order_status = order["status"]

      # Guard: If order cancelled move onto next Pair
      if order_status == "CANCELED":
        logger.info(f"{self.market_1} vs {self.market_2} - Order cancelled...")
        self.order_dict["pair_status"] = "FAILED"
        return "failed"

      # Guard: If not filled, cancel order
      if order_status != "FILLED":
        cancel_order(self.node, self.indexer, order_client_id)
        self.order_dict["pair_status"] = "ERROR"
        logger.info(f"{self.market_1} vs {self.market_2} - Order error...")
        return "error"

    # Return live
    return "live"

  # Open trades
  async def open_trades(self):

    # Print status
    logger.info("---")
    logger.info(f"{self.market_1}: Placing first order...")
    logger.info(f"Side: {self.base_side}, Size: {self.base_size}, Price: {self.base_price}")
    logger.info("---")

    # Place Base Order
    try:
      # Ralph Grewe: We don't simply get the order_id back from DYDX V4 - get the order ID object 
      realized_order_size, base_order_transaction, base_order = await place_market_order(
        self.node,
        self.indexer,
        self.wallet,
        self.market_1,
        self.base_side,
        self.base_size,
        self.base_price,
        False
      )

      # Store the order id
      logger.debug(f"Placed Base Order, realized size: {realized_order_size}")
      self.order_dict["order_m1_id"] = base_order.order_id.client_id
      self.order_dict["order_m1_size"] = realized_order_size
      self.order_dict["order_m1_time"] = datetime.now().isoformat()
    except Exception as e:
      self.order_dict["pair_status"] = "ERROR"
      self.order_dict["comments"] = f"Market 1 {self.market_1}: , {e}"
      logger.error(f"Error placing order for {self.market_1}: {e}")
      return self.order_dict

    # Ensure order is live before processing
    order_status_m1 = await self.check_order_status_by_id(self.order_dict["order_m1_id"])
    logger.debug(f"Checking Base Order Status: {order_status_m1}")

    # Guard: Aborder if order failed
    if order_status_m1 != "live":
      self.order_dict["pair_status"] = "ERROR"
      self.order_dict["comments"] = f"{self.market_1} failed to fill"
      return self.order_dict

    # Print status - opening second order
    logger.info("---")
    logger.info(f"{self.market_2}: Placing second order...")
    logger.info(f"Side: {self.quote_side}, Size: {self.quote_size}, Price: {self.quote_price}")
    logger.info("---")

    # Place Quote Order
    try:
      realized_order_size, quote_order_transaction, quote_order = await place_market_order(
        self.node,
        self.indexer,
        self.wallet,
        market_id=self.market_2,
        side=self.quote_side,
        size=self.quote_size,
        price=self.quote_price,
        reduce_only=False
      )

      # Store the order id
      logger.debug(f"Placed Quote Order, realized size: {realized_order_size}") 
      self.order_dict["order_m2_id"] = quote_order.order_id.client_id
      self.order_dict["order_m2_size"] = realized_order_size     
      self.order_dict["order_m2_time"] = datetime.now().isoformat()
      logger.debug(pformat(self.order_dict))
    except Exception as e:
      self.order_dict["pair_status"] = "ERROR"
      self.order_dict["comments"] = f"Market 2 {self.market_2}: , {e}"
      logger.info(f"Error placing order for {self.market_2}: {e}")
      return self.order_dict

    # Ensure order is live before processing
    order_status_m2 = await self.check_order_status_by_id(self.order_dict["order_m2_id"])
    logger.debug(f"Checking Quote Oder Status: {order_status_m2}")

    # Guard: Aborder if order failed
    if order_status_m2 != "live":
      self.order_dict["pair_status"] = "ERROR"
      self.order_dict["comments"] = f"{self.market_2} failed to fill"

      # Close order 1:
      # Ralph Grewe: Several attempts to avoid aborting early on narrow markets
      basePositionOpen = True
      for closingAttempt in range(10):
        try:
          realized_order_size, close_order_transaction, close_order = await place_market_order(
            self.node,
            self.indexer,
            self.wallet,
            market_id=self.market_1,
            side=self.quote_side,
            size=self.order_dict["order_m1_size"],
            price=self.accept_failsafe_base_price,
            reduce_only=True
          )
          logger.debug(f"Placed Close Order, Market: {self.market_1}, price: {self.accept_failsafe_base_price}, , size: {self.order_dict['order_m1_size']}, realized size: {realized_order_size}")
          logger.debug(pformat(close_order))
          # Ensure order is live before proceeding
          time.sleep(2)
          close_order_status = await self.check_order_status_by_id(close_order.order_id.client_id)

          if close_order_status == "live":
            logger.info(f"Aborted base position {self.market_1} in {closingAttempt} attempts")
            basePositionOpen = False
            break

        except Exception as e:
          self.order_dict["pair_status"] = "ERROR"
          self.order_dict["comments"] = f"Close Market 1 {self.market_1}: , {e}"
          logger.error("ABORT PROGRAM")
          logger.error("Unexpected Error")
          logger.error(e)

      if basePositionOpen:
        logger.error("ABORT PROGRAM")
        logger.error("Unexpected Error")
        logger.error(close_order_status)
        exit(2) # Probably half-opened position left over - abort with error code 2

      # Store the order id
      return self.order_dict

    # Return success result
    else:
      self.order_dict["pair_status"] = "LIVE"
      return self.order_dict