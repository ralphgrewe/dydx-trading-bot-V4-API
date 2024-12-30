# Ralph Grewe: This is heavily modified for the new V4 API connection

from dydx_v4_client.node.client import NodeClient
from dydx_v4_client.indexer.rest.indexer_client import IndexerClient
from dydx_v4_client.wallet import Wallet
from constants import (
    HOST,
    DYDX_ADDRESS,
    DYDX_MNEMONIC
)

async def connect_dydx():
    node = await NodeClient.connect(HOST.node)
    indexer = IndexerClient(HOST.rest_indexer)
    print("Connecting to: " + DYDX_ADDRESS)
    wallet = await Wallet.from_mnemonic(node, DYDX_MNEMONIC, DYDX_ADDRESS)

    return node, indexer, wallet