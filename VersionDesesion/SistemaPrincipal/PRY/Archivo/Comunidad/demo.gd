# WalletConnectUI.gd - Godot 4.7.2 - USDC Base - No errors
# UI: Connect wallet + Buy with 35 USDC + Presence CID check
extends Control

@export var escrow_contract_address: String = "0xYOUR_ESCROW_CONTRACT"
@export var usdc_address: String = "0x036CbD53842c5426634e79217eA9f0C1Bd0F5e2b"
@export var rpc_url: String = "https://sepolia.base.org"

var _wallet_address: String = ""
var _is_connected: bool = false
var _last_presence_cid: String = ""
var _current_product_price_usdc: float = 35.0
var _current_order_id: String = ""

# UI nodes
@onready var status_label: Label = $VBox/StatusLabel
@onready var connect_btn: Button = $VBox/ConnectBtn
@onready var buy_btn: Button = $VBox/BuyBtn
@onready var presence_label: Label = $VBox/PresenceLabel

func _ready():
	connect_btn.pressed.connect(_on_connect_pressed)
	buy_btn.pressed.connect(_on_buy_pressed)
	buy_btn.disabled = true
	status_label.text = "Not connected - Click Connect Wallet"
	presence_label.text = "Presence: NONE - Must meet seller in game first!"

func set_presence_cid(cid: String):
	_last_presence_cid = cid
	presence_label.text = "Presence: %s... OK - Can buy!" % cid.substr(0, 10)
	presence_label.modulate = Color.GREEN
	if _is_connected:
		buy_btn.disabled = false

func _on_connect_pressed():
	# Godot Web - JS interop for MetaMask
	if OS.has_feature("web"):
		var js_code = """
		if(window.ethereum){
			window.ethereum.request({method:'eth_requestAccounts'}).then(accounts=>{
				window.godotWalletAddress = accounts[0];
				console.log('[WOLD-WALLET] Connected', accounts[0]);
			});
		} else {
			alert('Install MetaMask! https://metamask.io');
		}
		"""
		JavaScriptBridge.eval(js_code)
		# Poll for address
		await get_tree().create_timer(1.0).timeout
		_check_wallet_js()
	else:
		# Desktop test - mock
		_wallet_address = "0x1234567890123456789012345678901234567890"
		_is_connected = true
		status_label.text = "Connected (Mock): %s" % _wallet_address.substr(0, 10)
		connect_btn.text = "Connected"
		connect_btn.disabled = true
		if _last_presence_cid != "":
			buy_btn.disabled = false
		print("[WOLD-WALLET] Mock connected ", _wallet_address)

func _check_wallet_js():
	var addr = JavaScriptBridge.eval("window.godotWalletAddress || ''")
	if addr != "":
		_wallet_address = addr
		_is_connected = true
		status_label.text = "Connected: %s...%s" % [_wallet_address.substr(0,6), _wallet_address.substr(-4)]
		connect_btn.text = "Connected"
		connect_btn.disabled = true
		if _last_presence_cid != "":
			buy_btn.disabled = false
		print("[WOLD-WALLET] Connected ", _wallet_address)
	else:
		status_label.text = "Connect failed - Open in browser with MetaMask"
		print("[WOLD-WALLET] No wallet found")

func _on_buy_pressed():
	if _last_presence_cid == "":
		status_label.text = "FAIL: Must meet seller in game - Proof-of-Presence required!"
		return
	if !_is_connected:
		status_label.text = "Connect wallet first!"
		return

	_current_order_id = "WOLD_USD_%s" % Time.get_unix_time_from_system()
	var amount_cents = int(_current_product_price_usdc * 1000000) # USDC 6 decimals -> 35 USDC = 35000000

	status_label.text = "Buying %s USDC - Order %s - Presence %s..." % [_current_product_price_usdc, _current_order_id, _last_presence_cid.substr(0,8)]

	if OS.has_feature("web"):
		var js_buy = """
		(async()=>{
			const escrow = "%s";
			const usdc = "%s";
			const orderId = "%s";
			const presenceCid = "%s";
			const amount = "%s";
			const buyer = window.godotWalletAddress;
			
			if(!buyer){ alert('Connect wallet first'); return; }
			
			// Simple ethers call - approve + createOrder
			const provider = new ethers.BrowserProvider(window.ethereum);
			const signer = await provider.getSigner();
			
			const usdcAbi = ["function approve(address spender, uint256 amount) returns (bool)"];
			const escrowAbi = ["function createOrder(bytes32 orderId, address seller, uint256 amount, string presenceCid)"];
			
			const usdcContract = new ethers.Contract(usdc, usdcAbi, signer);
			const escrowContract = new ethers.Contract(escrow, escrowAbi, signer);
			
			const orderBytes = ethers.encodeBytes32String(orderId.slice(0,31));
			const seller = "0xYOUR_SELLER_WALLET"; // replace
			
			console.log('[WOLD] Approving', amount, 'USDC');
			let tx1 = await usdcContract.approve(escrow, amount);
			await tx1.wait();
			
			console.log('[WOLD] Creating order', orderId, presenceCid);
			let tx2 = await escrowContract.createOrder(orderBytes, seller, amount, presenceCid);
			await tx2.wait();
			
			window.godotTxHash = tx2.hash;
			console.log('[WOLD] Order created', tx2.hash);
		})();
		""" % [escrow_contract_address, usdc_address, _current_order_id, _last_presence_cid, str(amount_cents)]
		
		JavaScriptBridge.eval(js_buy)
		status_label.text = "Check MetaMask - Approve USDC + Confirm Order - Tx pending..."
	else:
		status_label.text = "Mock buy %s USDC - Tx: 0xMOCK...%s - Escrow locked!" % [_current_product_price_usdc, _current_order_id]
		print("[WOLD-CRYPTO] Mock order ", _current_order_id, " ", amount_cents, " USDC Presence ", _last_presence_cid)

func get_wallet_address() -> String:
	return _wallet_address
