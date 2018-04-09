#!/usr/bin/env python3
# requires Python 3.5

import os
import random
import hashlib
from test_framework.address import byte_to_base58
from test_framework.key import CECKey
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_equal,
    connect_nodes_bi,
    start_nodes,
)

# Generate wallet import format from private key.
def wif(pk):
    # Base58Check version for regtest WIF keys is 0xef = 239
    return byte_to_base58(pk, 239)

class BlockSignTest(BitcoinTestFramework):

    # Dynamically generate N keys to be used for block signing.
    def init_keys(self, num_keys):
        self.keys = []
        self.wifs = []
        for i in range(num_keys):
            k = CECKey()
            pk_bytes = hashlib.sha256(str(random.getrandbits(256)).encode('utf-8')).digest()
            k.set_secretbytes(pk_bytes)
            w = wif(pk_bytes)
            print("generated key {}: \n  priv: {}\n  pub: {}\n  wif: {}".format(i+1,
                k.get_privkey().hex(),
                k.get_pubkey().hex(),
                w))
            self.keys.append(k)
            self.wifs.append(wif(pk_bytes))

    # The signblockscript is a Bitcoin Script k-of-n multisig script.
    def make_signblockscript(self):
        script = "{}".format(50 + self.required_signers)
        for i in range(self.num_nodes):
            k = self.keys[i]
            script += "41"
            script += k.get_pubkey().hex()
        script += "{}".format(50 + self.num_nodes) # num keys
        script += "ae" # OP_CHECKMULTISIG
        return script

    def __init__(self, num_nodes=3, required_signers=3):
        assert(num_nodes >= required_signers)
        super().__init__()
        self.setup_clean_chain = True
        self.num_nodes = num_nodes
        self.init_keys(self.num_nodes)
        self.required_signers = required_signers
        signblockscript = self.make_signblockscript()
        print('signblockscript', signblockscript)
        self.extra_args = [[
            "-chain=blocksign",
            # We can't validate pegins since we don't run the parent chain.
            "-validatepegin=0",
            "-signblockscript={}".format(signblockscript)
        ]] * self.num_nodes

    def setup_network(self, split=False):
        self.nodes = start_nodes(self.num_nodes, self.options.tmpdir, self.extra_args)
        # Have every node import its block signing private key.
        for i in range(self.num_nodes):
            self.nodes[i].importprivkey(self.wifs[i])
            if i + 1 < self.num_nodes:
                connect_nodes_bi(self.nodes, i, i + 1)
            else:
                connect_nodes_bi(self.nodes, 0, i)
        self.is_network_split = False
        self.sync_all()

    def mine_block(self):
        # mine block in round robin sense: depending on the block number, a node
        # is selected to create the block, others sign it and the selected node
        # broadcasts it
        mineridx = self.nodes[0].getblockcount() % self.num_nodes # assuming in sync
        miner = self.nodes[mineridx]

        # miner makes a block
        block = miner.getnewblockhex()

        # collect required_signers signatures
        sigs = []
        for i in range(self.required_signers):
            result = miner.combineblocksigs(block, sigs)
            assert_equal(result["complete"], False)
            sigs.append(self.nodes[i].signblock(block))

        # miner submits
        result = miner.combineblocksigs(block, sigs)
        assert_equal(result["complete"], True)
        signedblock = result["hex"]
        miner.submitblock(signedblock)

    def mine_blocks(self, num_blocks):
        for i in range(num_blocks):
            self.mine_block()
            self.sync_all()

    def check_height(self, expected_height):
        for n in self.nodes:
            assert_equal(n.getblockcount(), expected_height)

    def run_test(self):
        self.check_height(0)

        # mine a block
        self.mine_block()
        self.sync_all()

        # mine blocks
        self.mine_blocks(100)

        self.check_height(101)

if __name__ == '__main__':
    BlockSignTest(num_nodes=3, required_signers=3).main()
