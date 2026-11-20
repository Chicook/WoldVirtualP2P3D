# Add to demo_servidor.py - Oracle endpoint
from flask import Flask, request, jsonify
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

app = Flask(__name__)

# Load seller P-256 pubkeys mapping peerId -> pubkey (from SecurityManager)
PEER_PUBKEYS = {} # peerId: public_key_pem

@app.route('/api/oracle/release', methods=['POST'])
def oracle_release():
    data = request.json
    order_id = data['orderId']
    delivery_sig_b64 = data['deliverySig']
    delivery_data = data['deliveryData'] # orderId|tracking|gps|ts
    seller_peer_id = data['sellerPeerId']
    
    # 1. Verify P-256 signature
    try:
        pubkey_pem = PEER_PUBKEYS.get(seller_peer_id)
        if not pubkey_pem:
            return jsonify({"ok": False, "error": "Unknown seller peerId - no P-256 pubkey"}), 400
        
        pubkey = serialization.load_pem_public_key(pubkey_pem.encode())
        sig = base64.b64decode(delivery_sig_b64)
        pubkey.verify(sig, delivery_data.encode(), ec.ECDSA(hashes.SHA256()))
        print(f"[ORACLE] P-256 verified for {order_id} seller {seller_peer_id}")
    except Exception as e:
        print(f"[ORACLE] P-256 verify failed: {e}")
        # For demo, allow mock sigs ending with _P256_MOCK
        if "_P256_MOCK" not in delivery_sig_b64:
            return jsonify({"ok": False, "error": f"P-256 sig invalid: {e}"}), 400

    # 2. Call escrow contract release() - using oracle private key
    # from web3 import Web3; w3.eth.contract(...).functions.release(...)
    # tx_hash = ...
    tx_hash = "0xMOCK_ORACLE_RELEASE_" + order_id
    
    print(f"[ORACLE] Released USDC for {order_id} tx {tx_hash}")
    return jsonify({"ok": True, "txHash": tx_hash, "released": True})

if __name__ == '__main__':
    app.run(port=8545)
