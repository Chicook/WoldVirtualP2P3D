# SMTPLC: Sistema de Seguridad Multi-Terminal por Locación, Proxy y Clientes

El subsistema **SMTPLC** implementa un modelo de seguridad perimetral y anti-fraude diseñado para:
1. **Evitar la creación de múltiples cuentas en diferentes dispositivos dentro de la misma ubicación física**.
2. **Detectar y bloquear de forma estricta Máquinas Virtuales (VMs)**, hipervisores y sandboxes.
3. **Detectar y bloquear VPNs, Proxies, Túneles (WireGuard, OpenVPN, Wintun) y conexiones provenientes de centros de datos/hosting**.

---

## 🏗️ Arquitectura del Subsistema

El subsistema se encuentra 100% autocontenido en el directorio `Visor3D.Seguridad.SMTPLC`:

| Archivo | Responsabilidad |
| :--- | :--- |
| `SmtplcModels.cs` | DTOs, modelos de evaluación, enums de rechazo y contratos de configuración de políticas. |
| `VmDetector.cs` | Motor de detección profunda de entornos virtualizados (VMware, VirtualBox, Hyper-V, QEMU, KVM, Xen, Parallels). |
| `VpnDetector.cs` | Motor de detección de VPNs activas, adaptadores TAP/TUN/WireGuard, proxies locales del sistema y ASNs de hosting. |
| `LocationFingerprinter.cs` | Generador de huellas de ubicación física persistente (BSSID del Gateway vía ARP + Clúster Wi-Fi ambiental + Subred WAN). |
| `LocationAccountLedger.cs` | Libro mayor anti-multicuenta con cuotas de ubicación, períodos de enfriamiento (cooldown) y sellado HMAC-SHA256. |
| `SmtplcSecurityService.cs` | Orquestador principal (Fachada/Singleton) para evaluación previa al registro y commit en el ledger. |
| `SmtplcNativeMethods.cs` | Declaraciones P/Invoke para llamadas de bajo nivel (`iphlpapi.dll` para SendARP, `wlanapi.dll` para RF scanning). |
| `SmtplcDiagnostics.cs` | Herramienta de autodiagnóstico técnico para pruebas rápidas de telemetría y auditoría en caliente. |

---

## 🔍 1. Prevención Multi-Cuenta en Diferentes Dispositivos (Misma Ubicación)

### El Desafío:
Dos computadoras distintas (ej. PC Escritorio 1 y Portátil 2) tienen hashes de hardware diferentes (distinta CPU, distinta placa base, distinta MAC local). Un sistema basado únicamente en huella de hardware del dispositivo fallaría al detectar que ambas están en la misma casa, habitación u oficina.

### La Solución SMTPLC (Anclaje Triangulado):
SMTPLC calcula el **`LocationClusterHash`** (SHA-256) combinando tres vectores físicos independientes del dispositivo local:

1. **MAC Física del Router de Enlace (BSSID Gateway vía ARP L2)**:
   - Toda máquina conectada a la red local (por cable Ethernet o Wi-Fi) debe rutear sus paquetes a través de la misma puerta de enlace predeterminada.
   - Mediante la API nativa `SendARP` de `iphlpapi.dll`, SMTPLC resuelve la dirección MAC física del chip del router (ej. `B4:EE:D4:56:78:9A`).
   - Dado que el router físico es el mismo, todos los dispositivos en ese recinto comparten exactamente la misma MAC de gateway.

2. **Clúster de Balizas Wi-Fi Ambientales (RF Spectrum Fingerprint)**:
   - Utilizando la API nativa de Windows `wlanapi.dll`, el sistema escanea el espectro de radiofrecuencia circundante y toma las balizas BSSID/SSID de los puntos de acceso cercanos (red propia, vecinos, comercios).
   - Este espectro electromagnético es geográficamente estático y forma un anclaje físico imposible de replicar en otra ubicación.

3. **Subred e IP Pública Compartida (NAT)**:
   - Todos los dispositivos conectados al router comparten la misma IP pública de salida y segmento de red del proveedor de Internet local.

### Políticas de Cuota y Cooldown:
- **`MaxAccountsPerLocation`**: Número máximo de cuentas permitidas por ubicación (por defecto: `1`). Si ya existe una cuenta registrada bajo esa firma física, cualquier otro dispositivo en esa ubicación es bloqueado de inmediato con el código `MultipleAccountsInSameLocation`.
- **`CooldownMinutesBetweenAccounts`**: Tiempo mínimo obligatorio (ej. 72 horas) entre registros permitidos en la misma ubicación física para prevenir creación automatizada de cuentas.

---

## 🛡️ 2. Detección Profunda de Máquinas Virtuales (Anti-VM)

El analizador `VmDetector` evalúa 7 capas complementarias:

1. **WMI Win32_ComputerSystem**:
   - Detección del flag de kernel `HypervisorPresent`.
   - Búsqueda de fabricantes/modelos: `VMware, Inc.`, `innotek GmbH`, `Microsoft Corporation` (Virtual Machine), `QEMU`, `KVM`, `Parallels`, `Xen`.
2. **WMI Win32_BIOS & Firmware**:
   - Inspección de cadenas `VBOX`, `VMware`, `QEMU`, `Xen` en número de serie y versión SMBIOS.
3. **WMI Win32_DiskDrive**:
   - Inspección de nombres de discos virtuales: `VBOX HARDDISK`, `VMware Virtual disk`, `QEMU HARDDISK`, `Red Hat VirtIO SCSI`.
4. **Prefijos OUI de Direcciones MAC**:
   - Prefijos de fabricantes de virtualización:
     - `08:00:27` (VirtualBox)
     - `00:05:69`, `00:0C:29`, `00:50:56`, `00:1C:14` (VMware)
     - `00:15:5D`, `00:03:FF` (Hyper-V)
     - `52:54:00`, `00:16:3E` (QEMU/KVM/Xen)
     - `00:1C:42` (Parallels)
5. **Controladores de Kernel (.sys)**:
   - Detección de drivers invitados en `System32/drivers`: `VBoxMouse.sys`, `VBoxGuest.sys`, `VBoxSF.sys`, `vmmouse.sys`, `vmhgfs.sys`, `virtio_net.sys`, etc.
6. **Procesos y Servicios de Hipervisor**:
   - Procesos activos: `vboxservice.exe`, `vboxtray.exe`, `vmtoolsd.exe`, `vmwaretray.exe`, `qemu-ga.exe`, `prl_tools.exe`.
7. **Registros de Windows**:
   - Claves de instalación de Guest Additions y VMware Tools.

---

## 🌐 3. Detección de VPNs, Proxies y Túneles (Anti-VPN)

El analizador `VpnDetector` evalúa:

1. **Interfaces de Red Virtuales**:
   - Identificación de adaptadores `NetworkInterfaceType.Tunnel` y `Ppp`.
   - Coincidencias con proveedores de software: `WireGuard`, `TAP-Windows`, `Wintun`, `NordLynx`, `ProtonVPN`, `Tailscale`, `ZeroTier`, `Cloudflare WARP`, `ExpressVPN`, `Surfshark`, `OpenVPN`, etc.
2. **Configuración de Proxy en Windows**:
   - Detección de `ProxyEnable == 1` en el registro de Windows (`Internet Settings`).
   - Detección de scripts de autoconfiguración PAC (`AutoConfigURL`).
   - Comprobación de redirección de `WebRequest.DefaultWebProxy`.
3. **Anomalías de MTU de Túnel**:
   - Detección de tamaños de MTU típicos de encapsulamiento VPN (1280, 1360, 1400, 1420 bytes) en interfaces activas con ruta predeterminada.
4. **Servidores DNS en Subredes de Túnel**:
   - Servidores DNS asignados en rangos típicos de túnel (`10.8.0.1`, `10.2.0.1`, `100.64.0.1`).
5. **Análisis de ASN y Centros de Datos (Hosting)**:
   - Verificación de la IP pública contra ASNs de hosting (Amazon AWS, Google Cloud, Microsoft Azure, DigitalOcean, Hetzner, OVH, Linode, Contabo, Vultr). Se exige conexión mediante ISP residencial legítimo.

---

## 🔒 4. Integridad del Libro Mayor (Ledger)

- Los registros de ubicación se almacenan en `%LOCALAPPDATA%\WoldVirtualP2P3D\security\smtplc_location_ledger.dat`.
- Cada guardado se sella con un **código de autenticación de mensajes HMAC-SHA256** derivado criptográficamente del hardware del sistema local.
- Si un usuario intenta modificar o adulterar el archivo manualmente, la firma no coincidirá y el sistema invalidará los datos adulterados.
- Se proporciona el método `ExportJson()` y `MergeExternalRecords()` para sincronización entre nodos P2P.

---

## 💻 5. Ejemplo de Integración en el Flujo de Registro

Para integrar la validación en el formulario de registro (`RegistroWindow.xaml.cs` o `FormularioUsuarioWindow.xaml.cs`):

```csharp
using Visor3D.Seguridad.SMTPLC;

// 1. Antes de registrar el usuario, evaluar las políticas de seguridad
var evaluation = await SmtplcSecurityService.Instance.EvaluateRegistrationAsync(
    candidateAccountName: nombreUsuario,
    deviceHardwareHash: hardwareHash);

if (!evaluation.IsAllowed)
{
    // Bloquear el registro y mostrar el motivo descriptivo al usuario
    MessageBox.Show(
        $"{evaluation.DenialReason}\n\nCódigo: {evaluation.Code}",
        evaluation.DenialTitle,
        MessageBoxButton.OK,
        MessageBoxImage.Warning);
    return;
}

// 2. Si es aprobado, crear la cuenta normalmente y registrarla en el ledger de la ubicación
// ... crear usuario en user_profile.json ...

SmtplcSecurityService.Instance.CommitRegistration(
    accountUuid: nuevoUuid,
    accountName: nombreUsuario,
    evaluation: evaluation,
    deviceHardwareHash: hardwareHash);
```

---

## 📊 6. Ejecución de Diagnóstico y Pruebas

Para emitir un reporte instantáneo en pantalla o consola de desarrollo:

```csharp
string reporte = await Visor3D.Seguridad.SMTPLC.SmtplcDiagnostics.RunFullDiagnosticAsync();
System.Diagnostics.Debug.WriteLine(reporte);
```
