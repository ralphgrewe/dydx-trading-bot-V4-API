import dydx_v4_client.network as network
from decouple import config
import asyncio

# !!!! SELECT MODE !!!!
MODE = "DEVELOPMENT"

# Close all open positions and orders
ABORT_ALL_POSITIONS = False

# Find Cointegrated Pairs
FIND_COINTEGRATED = False

# Manage Exits
MANAGE_EXITS = False

# Place Trades
PLACE_TRADES = False

# Resolution
RESOLUTION = "1HOUR"

# Stats Window
WINDOW = 21

# Thresholds - Opening
MAX_HALF_LIFE = 24
ZSCORE_THRESH = 1.5
USD_PER_TRADE = 100
USD_MIN_COLLATERAL = 1880

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