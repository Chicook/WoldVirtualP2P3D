extends SceneTree

func _init() -> void:
	var p := ZIPPacker.new()
	var err := p.open("user://test_cuenta.zip")
	print("open=", err)
	p.start_file("cuenta.json")
	p.write_file('{"nick":"Test","cuenta_hash":"abc"}'.to_utf8_buffer())
	p.close_file()
	p.close()
	var r := ZIPReader.new()
	print("read_open=", r.open("user://test_cuenta.zip"))
	print("data=", r.read_file("cuenta.json").get_string_from_utf8())
	r.close()
	quit(0)
