import logging.handlers
from constants import ABORT_ALL_POSITIONS, FIND_COINTEGRATED, PLACE_TRADES, MANAGE_EXITS
from func_connections import connect_dydx
from func_private import abort_all_positions
from func_public import construct_market_prices
from func_cointegration import store_cointegration_results
from func_entry_pairs import open_positions
from func_exit_pairs import manage_trade_exits

# MAIN FUNCTION
# Ralph Grewe: we need to have a "async" function here which we then can call using asyncio.run()
import asyncio
import logging
import sys
from grpc import _channel

logger = logging.getLogger('BotLogger')

async def main():
  # Connect to client
  logFile = logging.handlers.RotatingFileHandler("bot.log", mode='a', maxBytes=67107840, backupCount=32786, encoding='utf-8', delay=False, errors=None)
  logFile.setLevel(logging.DEBUG)
  logFileFormatter = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
  logFile.setFormatter(logFileFormatter)
  logger.addHandler(logFile)
  logConsole = logging.StreamHandler(sys.stdout)
  logConsole.setLevel(logging.INFO)
  logger.addHandler(logConsole)
  logger.setLevel(logging.DEBUG)
  logger.info("Bot Started")

  try:
    logger.info("-----------------------------Connecting to Client...---------------------------------------")
    # Ralph Grewe: We have to await because it's an async function
    node, indexer, wallet = await connect_dydx()
  except Exception as e:
    logger.error("Error connecting to client: {e}")
    exit(1)

  # Abort all open positions
  if ABORT_ALL_POSITIONS:
    try:
      logger.info("Closing all positions...")
      close_orders = await abort_all_positions(node, indexer, wallet)
    except Exception as e:
      logger.info("Error closing all positions: {e}")
      exit(1)

  # Find Cointegrated Pairs
  if FIND_COINTEGRATED:

    # Construct Market Prices
    try:
      logger.info("\n\n--------------------------------------Fetching market prices, please allow 3 mins...------------------------------")
      df_market_prices = await construct_market_prices(indexer)
    except Exception as e:
      logger.error(f"Error constructing market prices: {e}")
      exit(1)

    # Store Cointegrated Pairs
    try:
      logger.info("\n\n------------------------------------------Storing cointegrated pairs...--------------------------------------------")
      stores_result = store_cointegration_results(df_market_prices)
      if stores_result != "saved":
        logger.error("Error saving cointegrated pairs")
        exit(1)
    except Exception as e:
      logger.error("Error saving cointegrated pairs: {e}")
      exit(1)

  # Run as always on
  while True:

    # Place trades for opening positions
    if MANAGE_EXITS:
      try:
        logger.info("\n\n------------------------------------------Managing exits...--------------------------------------------------------")
        await manage_trade_exits(node, indexer, wallet)
      except Exception as e:
        logger.error(f"Error managing exiting positions: {e}")
        exit(1)

    # Place trades for opening positions
    if PLACE_TRADES:

      try:
        logger.info("\n\n------------------------------------------Finding trading opportunities...-----------------------------------------")
        await open_positions(node, indexer, wallet)
      except _channel._InactiveRpcError as rpc_error:
        # Specific handling for _InactiveRpcError
        if rpc_error.details() == "Received http2 header with status: 503":
          logger.warning("Warning: Received http2 header with status 503, the service may be temporarily unavailable. Continuing...")
        else:
          logger.error(f"gRPC error: {rpc_error}")
      except Exception as e:
                # General exception handling
        logger.error(f"Error trading pairs: {e}")
        exit(1)

if __name__ == "__main__":
  asyncio.run(main())