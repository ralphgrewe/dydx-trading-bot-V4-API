import dydx_v4_client.network as network
from decouple import config
import asyncio
from dydx_v4_client.indexer.candles_resolution import CandlesResolution

# !!!! SELECT MODE !!!!
MODE = "DEVELOPMENT"

# Close all open positions and orders
ABORT_ALL_POSITIONS =True

# Find Cointegrated Pairs
FIND_COINTEGRATED = False

# Manage Exits
MANAGE_EXITS = True

# Place Trades
PLACE_TRADES = True

# Resolution
RESOLUTION = CandlesResolution.ONE_HOUR.value

# Stats Window
WINDOW = 21

# Thresholds - Opening
MAX_HALF_LIFE = 24
ZSCORE_THRESH = 1.2
USD_PER_TRADE = 25
USD_MIN_COLLATERAL = 10

# Thresholds - Closing
CLOSE_AT_ZSCORE_CROSS = True

# Ralph Grewe: The following sections are modified. Ethereum Address is not required any longer.
# The DYDX Address and mnemonic retrived as described in the README.md are used insted.

# Testnet Information
DYDX_ADDRESS_TESTNET = config("DYDX_ADDRESS_DEV")
DYDX_MNEMONIC_TESTNET = config("DYDX_MNEMONIC_DEV")
HTTP_PROVIDER_TESTNET = ""

# Mainnet Information
DYDX_ADDRESS_MAINNET = config("DYDX_ADDRESS_PROD")
DYDX_MNEMONIC_MAINNET = config("DYDX_MNEMONIC_PROD")
HTTP_PROVIDER_MAINNET = ""

# Chose Configuration
DYDX_ADDRESS = DYDX_ADDRESS_MAINNET if MODE == "PRODUCTION" else DYDX_ADDRESS_TESTNET
DYDX_MNEMONIC = "NOTHING" if MODE == "PRODUCTION" else DYDX_MNEMONIC_TESTNET
HOST = network if MODE == "PRODUCTION" else network.TESTNET
HTTP_PROVIDER = HTTP_PROVIDER_MAINNET if MODE == "PRODUCTION" else HTTP_PROVIDER_TESTNET

# Ralph Grewe: New API is Asyncronous - Adding a lock for thread safety (still there are some strange issues)
WALLET_LOCK = asyncio.Lock()

# Ralph Grewe: Avoid Markets with to low open interest
MARKET_MIN_OPEN_INTEREST = 250000