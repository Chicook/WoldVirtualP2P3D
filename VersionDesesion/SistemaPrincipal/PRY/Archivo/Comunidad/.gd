# SellerDeliveryAgent.gd - Godot 4.7.2 - P-256 real signature for delivery
extends Node

# Dole SecurityManager yana da GetOrCreateECDSA()
var _ecdsa_key = null
var _peer_id: String = ""

func _ready():
	# Load P-256 key
	_ecdsa_key = SecurityManager.GetOrCreateECDSA() if Engine.has_singleton("SecurityManager") else null
	_peer_id = SecurityManager.GetPeerId(_ecdsa_key) if _ecdsa_key else "seller_mock"
	print("[SELLER-AGENT] PeerId ", _peer_id)

func sign_delivery_proof(order_id: String, tracking: String, gps: String) -> String:
	# Real P-256 signing - data = orderId|tracking|gps|ts
	var ts = int(Time.get_unix_time_from_system())
	var data = "%s|%s|%s|%d" % [order_id, tracking, gps, ts]
	var bytes = data.to_utf8_buffer()
	
	# If SecurityManager exposes SignData, use it - else mock base64
	var sig_b64: String = ""
	if _ecdsa_key != null and _ecdsa_key.has_method("SignData"):
		var sig = _ecdsa_key.SignData(bytes, 3) # 3 = SHA256
		sig_b64 = Marshalls.raw_to_base64(sig)
	else:
		# Mock for Godot - real in C# WoldCommerceUSD.CreateDeliveryProofUSD
		sig_b64 = Marshalls.utf8_to_base64(data).substr(0, 40) + "_P256_MOCK"
	
	print("[SELLER-P256] Delivery proof signed order=%s tracking=%s sig=%s..." % [order_id, tracking, sig_b64.substr(0,20)])
	
	# Send to JS seller.html if in web
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.godotDeliverySig = '%s'; window.godotDeliveryData = '%s';" % [sig_b64, data])
	
	return sig_b64

func on_delivery_button_pressed(order_id: String, tracking: String, gps: String):
	var sig = sign_delivery_proof(order_id, tracking, gps)
	# Call Commerce API
	print("[SELLER] Delivery ready to upload to oracle: ", sig)
	# HTTP POST to your server /api/delivery
	# _http_request.request("https://your-server.com/api/delivery", ..., {orderId, tracking, gps, deliverySig: sig})
