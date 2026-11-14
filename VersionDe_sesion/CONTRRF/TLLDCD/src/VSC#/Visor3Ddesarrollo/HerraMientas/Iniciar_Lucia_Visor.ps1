$py = "E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\LC_STM\python\pythonw.exe"
$srv = "E:\WoldVirtualP2P3D\VersionDe_sesion\Sistema_Principal\PRY\actualizacion_c5074e3b\src\MTBGT\WoldVirtualP2P3D\lucia3D\GLTF_lucIA\celebro_3D\puente_3D\servidor_lucia.py"
$log = Join-Path $env:LOCALAPPDATA "WoldVirtualP2P3D\logs\lucia_ps.log"
Start-Process -FilePath $py -ArgumentList @("`"$srv`"", "--modelo", "qwen2.5:7b", "--puerto", "8765", "--sin-precarga-voz") -WorkingDirectory (Split-Path $srv) -WindowStyle Hidden -Wait -RedirectStandardOutput $log -RedirectStandardError "$log.err"
