#!/usr/bin/env python2

from test_framework.authproxy import AuthServiceProxy, JSONRPCException
import os
import random
import sys
import time
import subprocess
import shutil

if len(sys.argv) < 2:
    print("path to bitcoind must be included as argument")
    sys.exit(0)
bitcoin_bin_path = sys.argv[1]
sidechain_bin_path = os.path.normpath(os.path.dirname(os.path.realpath(__file__))+"/../../src")
if len(sys.argv) > 2:
    sidechain_bin_path = sys.argv[2]

print(bitcoin_bin_path)
print(sidechain_bin_path)

# Sync mempool, make a block, sync blocks
def sync_all(sidechain, sidechain2):
    timeout = 20
    while len(sidechain.getrawmempool()) != len(sidechain2.getrawmempool()):
        time.sleep(1)
        timeout -= 1
        if timeout == 0:
            raise Exception("Peg-in has failed to propagate.")
    block = sidechain2.generate(1)
    while sidechain.getblockcount() != sidechain2.getblockcount():
        time.sleep(1)
        timeout -= 1
        if timeout == 0:
            raise Exception("Blocks are not propagating.")
    return block

fedpeg_key="cPxqWyf1HDGpGFH1dnfjz8HbiWxvwG8WXyetbuAiw4thKXUdXLpR"
fedpeg_pubkey="512103dff4923d778550cc13ce0d887d737553b4b58f4e8e886507fc39f5e447b2186451ae"

def get_pseudorandom_str(str_length=10):
    return ''.join(random.choice('0123456789ABCDEF') for i in range(str_length))

def get_temp_dir(nodename):
    return "/tmp/%s_%s" % (nodename, get_pseudorandom_str())

class SingletonPort():
    def __init__(self, ):
        self.port = 8000 + os.getpid()%999

    def next_port(self):
        self.port = self.port + 1
        return self.port

class Node():
    def __init__(self, daemonname='elements', nodename='test', port_dealer=SingletonPort()):
        self.daemonname = daemonname
        self.nodename = '%s_%s' % (self.daemonname, nodename)
        self.port = port_dealer.next_port()
        self.rpcport = port_dealer.next_port()
        self.datadir = get_temp_dir(nodename)
        self.password = get_pseudorandom_str()
        os.makedirs(self.datadir)

    def __del__(self):
        shutil.rmtree(self.datadir)

    def init_daemon(self, daemon_bin_path, extra_args=''):
        daemonstart = "%s/%sd -datadir=%s %s" % (daemon_bin_path, self.daemonname, self.datadir, extra_args)
        subprocess.Popen(daemonstart.split(), stdout=subprocess.PIPE)

    def write_bitcoin_conf(self, f):
        f.write("regtest=1\n")
        f.write("rpcuser=bitcoinrpc\n")
        f.write("discover=0\n")
        f.write("listen=0\n")
        f.write("testnet=0\n")
        f.write("txindex=1\n")
        f.write("daemon=1\n")
        f.write("listen=0\n")
        f.write("rpcpassword="+self.password+"\n")
        f.write("rpcport="+str(self.rpcport)+"\n")
        f.write("discover=0\n")

    def write_sidechain_conf(self, f, mainchain_node, connect_port):
        f.write("regtest=1\n")
        f.write("rpcuser=sidechainrpc\n")
        f.write("rpcpassword="+self.password+"\n")
        f.write("rpcport="+str(self.rpcport)+"\n")
        f.write("discover=0\n")
        f.write("testnet=0\n")
        f.write("txindex=1\n")
        f.write("fedpegscript="+fedpeg_pubkey+"\n")
        f.write("daemon=1\n")
        f.write("mainchainrpchost=127.0.0.1\n")
        f.write("mainchainrpcport="+str(mainchain_node.rpcport)+"\n")
        f.write("mainchainrpcuser=bitcoinrpc\n")
        f.write("mainchainrpcpassword="+mainchain_node.password+"\n")
        f.write("validatepegin=1\n")
        f.write("validatepegout=0\n")
        f.write("port="+str(self.port)+"\n")
        f.write("connect=localhost:"+str(connect_port)+"\n")
        f.write("listen=1\n")
        f.write("discover=0\n")

    def write_sidechain2_conf(self, f, mainchain_node, connect_port):
        f.write("regtest=1\n")
        f.write("rpcuser=sidechainrpc2\n")
        f.write("rpcpassword="+self.password+"\n")
        f.write("rpcport="+str(self.rpcport)+"\n")
        f.write("discover=0\n")
        f.write("testnet=0\n")
        f.write("txindex=1\n")
        f.write("fedpegscript="+fedpeg_pubkey+"\n")
        f.write("daemon=1\n")
        f.write("mainchainrpchost=127.0.0.1\n")
        f.write("mainchainrpcport="+str(mainchain_node.rpcport)+"\n")
        f.write("mainchainrpcuser=bitcoinrpc\n")
        f.write("mainchainrpcpassword="+mainchain_node.password+"\n")
        f.write("validatepegin=1\n")
        f.write("validatepegout=0\n")
        f.write("port="+str(self.port)+"\n")
        f.write("connect=localhost:"+str(connect_port)+"\n")
        f.write("listen=1\n")
        f.write("discover=0\n")
        
    def write_conf(self, mainchain_node=None, connect_port=None):
        with open(os.path.join(self.datadir, "%s.conf" % self.daemonname), 'w') as f:
            print('self.nodename', self.nodename)
            if self.nodename == 'bitcoin_bitcoin':
                self.write_bitcoin_conf(f)
            elif self.nodename == 'elements_sidechain':
                self.write_sidechain_conf(f, mainchain_node, connect_port)
            elif self.nodename == 'elements_sidechain2':
                self.write_sidechain2_conf(f, mainchain_node, connect_port)
            else:
                raise NotImplementedError

PORT_DEALER = SingletonPort()
NODES = {
    'bitcoin': Node('bitcoin', 'bitcoin', port_dealer=PORT_DEALER),
    'sidechain': Node('elements', 'sidechain', port_dealer=PORT_DEALER),
    'sidechain2': Node('elements', 'sidechain2', port_dealer=PORT_DEALER),
}

NODES['bitcoin'].write_conf()
NODES['sidechain'].write_conf(NODES['bitcoin'], NODES['sidechain2'].port)
NODES['sidechain2'].write_conf(NODES['bitcoin'], NODES['sidechain'].port)

try:
    # Default is 8, meaning 8+2 confirms for wallet acceptance normally
    # this will require 10+2.
    sidechain_args = " -peginconfirmationdepth=10 "

    # Start daemons
    print("Starting daemons at "+NODES['bitcoin'].datadir+", "+NODES['sidechain'].datadir+" and "+NODES['sidechain2'].datadir)
    NODES['bitcoin'].init_daemon(bitcoin_bin_path)
    NODES['sidechain'].init_daemon(sidechain_bin_path, sidechain_args)
    NODES['sidechain2'].init_daemon(sidechain_bin_path, sidechain_args)

    print("Daemons started")
    time.sleep(3)

    bitcoin = AuthServiceProxy("http://bitcoinrpc:"+NODES['bitcoin'].password+"@127.0.0.1:"+str(NODES['bitcoin'].rpcport))
    sidechain = AuthServiceProxy("http://sidechainrpc:"+NODES['sidechain'].password+"@127.0.0.1:"+str(NODES['sidechain'].rpcport))
    sidechain2 = AuthServiceProxy("http://sidechainrpc2:"+NODES['sidechain2'].password+"@127.0.0.1:"+str(NODES['sidechain2'].rpcport))
    print("Daemons started, making blocks to get funds")
    time.sleep(3)

    bitcoin.generate(101)
    sidechain.generate(101)

    addr = bitcoin.getnewaddress()

    addrs = sidechain.getpeginaddress()
    txid1 = bitcoin.sendtoaddress(addrs["mainchain_address"], 24)
    # 10+2 confirms required to get into mempool and confirm
    bitcoin.generate(11)
    time.sleep(2)
    proof = bitcoin.gettxoutproof([txid1])
    raw = bitcoin.getrawtransaction(txid1)

    print("Attempting peg-in")
    try:
        pegtxid = sidechain.claimpegin(raw, proof)
        raise Exception("Peg-in should not mature enough yet, need another block.")
    except JSONRPCException as e:
        assert("Peg-in Bitcoin transaction needs more confirmations to be sent." in e.error["message"])
        pass

    # Should fail due to non-matching wallet address
    try:
        pegtxid = sidechain.claimpegin(raw, proof, sidechain.getnewaddress())
        raise Exception("Peg-in with non-matching claim_script should fail.")
    except JSONRPCException as e:
        assert("Given claim_script does not match the given Bitcoin transaction." in e.error["message"])
        pass

    # 12 confirms allows in mempool
    bitcoin.generate(1)
    # Should succeed via wallet lookup for address match, and when given
    pegtxid1 = sidechain.claimpegin(raw, proof)

    # Will invalidate the block that confirms this transaction later
    blockhash = sync_all(sidechain, sidechain2)
    sidechain.generate(5)

    tx1 = sidechain.gettransaction(pegtxid1)

    if "confirmations" in tx1 and tx1["confirmations"] == 6:
        print("Peg-in is confirmed: Success!")
    else:
        raise Exception("Peg-in confirmation has failed.")

    # Look at pegin fields
    decoded = sidechain.decoderawtransaction(tx1["hex"])
    assert decoded["vin"][0]["is_pegin"] == True
    assert len(decoded["vin"][0]["pegin_witness"]) > 0

    # Quick reorg checks of pegs
    sidechain.invalidateblock(blockhash[0])
    if sidechain.gettransaction(pegtxid1)["confirmations"] != 0:
        raise Exception("Peg-in didn't unconfirm after invalidateblock call.")
    # Re-enters block
    sidechain.generate(1)
    if sidechain.gettransaction(pegtxid1)["confirmations"] != 1:
        raise Exception("Peg-in should have one confirm on side block.")
    sidechain.reconsiderblock(blockhash[0])
    if sidechain.gettransaction(pegtxid1)["confirmations"] != 6:
        raise Exception("Peg-in should be back to 6 confirms.")

    # Do many claims in mempool
    n_claims = 100

    print("Flooding mempool with many small claims")
    pegtxs = []
    sidechain.generate(101)

    for i in range(n_claims):
        addrs = sidechain.getpeginaddress()
        txid = bitcoin.sendtoaddress(addrs["mainchain_address"], 1)
        bitcoin.generate(12)
        proof = bitcoin.gettxoutproof([txid])
        raw = bitcoin.getrawtransaction(txid)
        pegtxs += [sidechain.claimpegin(raw, proof)]

    sync_all(sidechain, sidechain2)

    sidechain2.generate(1)
    for pegtxid in pegtxs:
        tx = sidechain.gettransaction(pegtxid)
        if "confirmations" not in tx or tx["confirmations"] == 0:
            raise Exception("Peg-in confirmation has failed.")

    print("Success!")

except JSONRPCException as e:
        print("Pegging testing failed, aborting:")
        print(e.error)
except Exception as e:
        print("Pegging testing failed, aborting:")
        print(e)

print("Stopping daemons and cleaning up")
bitcoin.stop()
sidechain.stop()
sidechain2.stop()
