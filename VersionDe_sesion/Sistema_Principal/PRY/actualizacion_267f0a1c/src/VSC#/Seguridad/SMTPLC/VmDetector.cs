using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Management;
using System.Net.NetworkInformation;
using Microsoft.Win32;

namespace Visor3D.Seguridad.SMTPLC
{
    /// <summary>
    /// Motor de detección profunda de Máquinas Virtuales (VM), hipervisores y sandboxes.
    /// Inspecciona WMI, hardware, controladores de kernel, procesos en ejecución,
    /// prefijos OUI de tarjetas de red y registros de sistema.
    /// </summary>
    public static class VmDetector
    {
        // Prefijos OUI de direcciones MAC asignadas a fabricantes de virtualización
        private static readonly Dictionary<string, string> KnownVmMacOui = new(StringComparer.OrdinalIgnoreCase)
        {
            { "08:00:27", "Oracle VirtualBox" },
            { "00:05:69", "VMware" },
            { "00:0C:29", "VMware" },
            { "00:50:56", "VMware" },
            { "00:1C:14", "VMware" },
            { "00:15:5D", "Microsoft Hyper-V" },
            { "00:03:FF", "Microsoft Virtual PC / Hyper-V" },
            { "52:54:00", "QEMU / KVM" },
            { "00:16:3E", "Xen Hypervisor" },
            { "00:1C:42", "Parallels Desktop" }
        };

        // Palabras clave de fabricantes / modelos de virtualización en WMI y BIOS
        private static readonly string[] VmKeywords = new[]
        {
            "vmware",
            "virtualbox",
            "vbox",
            "qemu",
            "kvm",
            "hyper-v",
            "virtual machine",
            "bochs",
            "parallels",
            "innotek",
            "xen",
            "red hat virtio",
            "sandbox"
        };

        // Controladores (.sys) instalados por Guest Additions o VM Tools
        private static readonly string[] VmDriverFiles = new[]
        {
            "VBoxMouse.sys", "VBoxGuest.sys", "VBoxSF.sys", "VBoxVideo.sys", "VBoxWddm.sys",
            "vmmouse.sys", "vmhgfs.sys", "vmusbmouse.sys", "vmkspd.sys", "vm3dmp.sys",
            "prl_fs.sys", "prl_tg.sys",
            "xennet.sys", "xenvbd.sys",
            "viostor.sys", "vioscsi.sys", "virtio_net.sys"
        };

        // Procesos y servicios característicos de máquinas virtuales
        private static readonly string[] VmProcessNames = new[]
        {
            "vboxservice", "vboxtray",
            "vmtoolsd", "vmwaretray", "vmwareuser",
            "qemu-ga",
            "prl_tools", "prl_cc",
            "xenservice"
        };

        /// <summary>
        /// Ejecuta una evaluación multicapa para determinar si el entorno actual es una Máquina Virtual.
        /// </summary>
        public static VmDetectionResult Analyze()
        {
            var result = new VmDetectionResult();
            double score = 0.0;
            var detectedHypervisors = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var artifacts = new List<string>();

            // 1. Análisis WMI: Placa base, Fabricante, Modelo e HypervisorPresent
            InspectWmiComputerSystem(detectedHypervisors, artifacts, ref score);

            // 2. Análisis WMI: BIOS y Firmware
            InspectWmiBios(detectedHypervisors, artifacts, ref score);

            // 3. Análisis WMI: Discos duros
            InspectWmiDisks(detectedHypervisors, artifacts, ref score);

            // 4. Análisis de direcciones MAC (OUI de adaptadores de red)
            InspectNetworkMacs(detectedHypervisors, artifacts, ref score);

            // 5. Detección de controladores (.sys) en System32/drivers
            InspectKernelDrivers(detectedHypervisors, artifacts, ref score);

            // 6. Detección de procesos y servicios de VM en ejecución
            InspectRunningProcesses(detectedHypervisors, artifacts, ref score);

            // 7. Inspección de claves de Registro de Windows
            InspectRegistry(detectedHypervisors, artifacts, ref score);

            // Normalizar score y armar resultado final
            result.ConfidenceScore = Math.Min(1.0, score);
            result.IsVm = result.ConfidenceScore >= 0.40;
            result.DetectedHypervisors = detectedHypervisors.ToList();
            result.Artifacts = artifacts;

            if (result.IsVm)
            {
                result.Summary = $"Entorno de Máquina Virtual detectado ({string.Join(", ", result.DetectedHypervisors)}) con {result.ConfidenceScore * 100:0}% de confianza.";
            }
            else
            {
                result.Summary = "Sistema verificado en hardware real. Sin indicios de virtualización.";
            }

            return result;
        }

        private static void InspectWmiComputerSystem(HashSet<string> hypervisors, List<string> artifacts, ref double score)
        {
            try
            {
                using var searcher = new ManagementObjectSearcher("SELECT Manufacturer, Model, HypervisorPresent FROM Win32_ComputerSystem");
                foreach (ManagementObject obj in searcher.Get())
                {
                    string manufacturer = obj["Manufacturer"]?.ToString() ?? "";
                    string model = obj["Model"]?.ToString() ?? "";
                    bool hypervisorPresent = false;

                    if (obj["HypervisorPresent"] != null && bool.TryParse(obj["HypervisorPresent"].ToString(), out bool hp))
                    {
                        hypervisorPresent = hp;
                    }

                    if (hypervisorPresent)
                    {
                        // Windows activa este flag con VBS, Credential Guard, Hyper-V, WSL2 o
                        // sandboxing en equipos físicos, así que por sí solo no puede superar
                        // el umbral de VM: sólo corrobora otras señales.
                        score += 0.25;
                        artifacts.Add("Flag HypervisorPresent en Win32_ComputerSystem está ACTIVO (VBS/Hyper-V de Windows; señal corroborante, no concluyente).");
                        hypervisors.Add("Hipervisor de CPU");
                    }

                    string combined = $"{manufacturer} {model}".ToLowerInvariant();
                    foreach (var kw in VmKeywords)
                    {
                        if (combined.Contains(kw))
                        {
                            score += 0.45;
                            artifacts.Add($"Win32_ComputerSystem coincide con VM: Fabricante='{manufacturer}', Modelo='{model}'.");
                            hypervisors.Add(IdentifyHypervisorName(kw));
                            break;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando Win32_ComputerSystem: {ex.Message}");
            }
        }

        private static void InspectWmiBios(HashSet<string> hypervisors, List<string> artifacts, ref double score)
        {
            try
            {
                using var searcher = new ManagementObjectSearcher("SELECT SerialNumber, Version, SMBIOSBIOSVersion, Manufacturer FROM Win32_BIOS");
                foreach (ManagementObject obj in searcher.Get())
                {
                    string serial = obj["SerialNumber"]?.ToString() ?? "";
                    string version = obj["Version"]?.ToString() ?? "";
                    string smbios = obj["SMBIOSBIOSVersion"]?.ToString() ?? "";
                    string manufacturer = obj["Manufacturer"]?.ToString() ?? "";

                    string combined = $"{serial} {version} {smbios} {manufacturer}".ToLowerInvariant();
                    foreach (var kw in VmKeywords)
                    {
                        if (combined.Contains(kw))
                        {
                            score += 0.40;
                            artifacts.Add($"Win32_BIOS coincide con firma de VM: '{kw}' detectado en firmware ({smbios} / {version}).");
                            hypervisors.Add(IdentifyHypervisorName(kw));
                            break;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando Win32_BIOS: {ex.Message}");
            }
        }

        private static void InspectWmiDisks(HashSet<string> hypervisors, List<string> artifacts, ref double score)
        {
            try
            {
                using var searcher = new ManagementObjectSearcher("SELECT Model, PNPDeviceID FROM Win32_DiskDrive");
                foreach (ManagementObject obj in searcher.Get())
                {
                    string model = obj["Model"]?.ToString() ?? "";
                    string pnp = obj["PNPDeviceID"]?.ToString() ?? "";
                    string combined = $"{model} {pnp}".ToLowerInvariant();

                    foreach (var kw in VmKeywords)
                    {
                        if (combined.Contains(kw))
                        {
                            score += 0.40;
                            artifacts.Add($"Disco virtual detectado en Win32_DiskDrive: '{model}'.");
                            hypervisors.Add(IdentifyHypervisorName(kw));
                            break;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando Win32_DiskDrive: {ex.Message}");
            }
        }

        private static void InspectNetworkMacs(HashSet<string> hypervisors, List<string> artifacts, ref double score)
        {
            try
            {
                foreach (var nic in NetworkInterface.GetAllNetworkInterfaces())
                {
                    string mac = nic.GetPhysicalAddress().ToString();
                    if (mac.Length < 6) continue;

                    string formattedOui = $"{mac.Substring(0, 2)}:{mac.Substring(2, 2)}:{mac.Substring(4, 2)}".ToUpperInvariant();
                    if (KnownVmMacOui.TryGetValue(formattedOui, out string? vmName))
                    {
                        score += 0.50;
                        artifacts.Add($"Dirección MAC de adaptador ({nic.Name}) coincide con OUI de '{vmName}' ({formattedOui}).");
                        hypervisors.Add(vmName);
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando direcciones MAC: {ex.Message}");
            }
        }

        private static void InspectKernelDrivers(HashSet<string> hypervisors, List<string> artifacts, ref double score)
        {
            try
            {
                string driversPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "drivers");
                if (!Directory.Exists(driversPath)) return;

                foreach (var driver in VmDriverFiles)
                {
                    string fullPath = Path.Combine(driversPath, driver);
                    if (File.Exists(fullPath))
                    {
                        score += 0.45;
                        artifacts.Add($"Controlador de virtualización presente en el sistema: '{driver}'.");
                        hypervisors.Add(IdentifyDriverOwner(driver));
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando controladores de kernel: {ex.Message}");
            }
        }

        private static void InspectRunningProcesses(HashSet<string> hypervisors, List<string> artifacts, ref double score)
        {
            try
            {
                var running = Process.GetProcesses();
                foreach (var proc in running)
                {
                    try
                    {
                        string procName = proc.ProcessName.ToLowerInvariant();
                        if (VmProcessNames.Contains(procName))
                        {
                            score += 0.50;
                            artifacts.Add($"Proceso de utilidades de hipervisor en ejecución: '{proc.ProcessName}.exe'.");
                            hypervisors.Add(IdentifyProcessOwner(procName));
                        }
                    }
                    catch
                    {
                        // Proceso del sistema con permisos restringidos, ignorar
                    }
                    finally
                    {
                        proc.Dispose();
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando procesos activos: {ex.Message}");
            }
        }

        private static void InspectRegistry(HashSet<string> hypervisors, List<string> artifacts, ref double score)
        {
            try
            {
                // Comprobar claves de VirtualBox
                using var vboxKey = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\Oracle\VirtualBox Guest Additions");
                if (vboxKey != null)
                {
                    score += 0.60;
                    artifacts.Add("Registro de Windows: Guest Additions de Oracle VirtualBox instaladas.");
                    hypervisors.Add("Oracle VirtualBox");
                }

                // Comprobar claves de VMware
                using var vmwareKey = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\VMware, Inc.\VMware Tools");
                if (vmwareKey != null)
                {
                    score += 0.60;
                    artifacts.Add("Registro de Windows: VMware Tools instaladas.");
                    hypervisors.Add("VMware");
                }

                // Comprobar SystemBiosDate / VideoBiosVersion
                using var biosKey = Registry.LocalMachine.OpenSubKey(@"HARDWARE\Description\System\BIOS");
                if (biosKey != null)
                {
                    string videoBios = biosKey.GetValue("VideoBiosVersion")?.ToString()?.ToLowerInvariant() ?? "";
                    string sysProd = biosKey.GetValue("SystemProductName")?.ToString()?.ToLowerInvariant() ?? "";

                    foreach (var kw in VmKeywords)
                    {
                        if (videoBios.Contains(kw) || sysProd.Contains(kw))
                        {
                            score += 0.40;
                            artifacts.Add($"Registro BIOS contiene firma de hipervisor: '{kw}'.");
                            hypervisors.Add(IdentifyHypervisorName(kw));
                            break;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[SMTPLC] Error inspeccionando registro: {ex.Message}");
            }
        }

        private static string IdentifyHypervisorName(string keyword)
        {
            if (keyword.Contains("vbox") || keyword.Contains("virtualbox") || keyword.Contains("innotek"))
                return "Oracle VirtualBox";
            if (keyword.Contains("vmware"))
                return "VMware Workstation/ESXi";
            if (keyword.Contains("hyper-v") || keyword.Contains("virtual machine"))
                return "Microsoft Hyper-V";
            if (keyword.Contains("qemu") || keyword.Contains("kvm") || keyword.Contains("virtio"))
                return "QEMU / KVM";
            if (keyword.Contains("xen"))
                return "Xen Hypervisor";
            if (keyword.Contains("parallels"))
                return "Parallels Desktop";
            return $"Hipervisor ({keyword})";
        }

        private static string IdentifyDriverOwner(string driver)
        {
            if (driver.StartsWith("VBox", StringComparison.OrdinalIgnoreCase)) return "Oracle VirtualBox";
            if (driver.StartsWith("vm", StringComparison.OrdinalIgnoreCase)) return "VMware";
            if (driver.StartsWith("prl", StringComparison.OrdinalIgnoreCase)) return "Parallels Desktop";
            if (driver.StartsWith("xen", StringComparison.OrdinalIgnoreCase)) return "Xen";
            if (driver.StartsWith("vio", StringComparison.OrdinalIgnoreCase) || driver.StartsWith("virtio", StringComparison.OrdinalIgnoreCase)) return "QEMU/KVM VirtIO";
            return "Virtualización Genérica";
        }

        private static string IdentifyProcessOwner(string proc)
        {
            if (proc.StartsWith("vbox")) return "Oracle VirtualBox";
            if (proc.StartsWith("vmware") || proc.StartsWith("vmtools")) return "VMware";
            if (proc.StartsWith("qemu")) return "QEMU";
            if (proc.StartsWith("prl")) return "Parallels Desktop";
            if (proc.StartsWith("xen")) return "Xen";
            return "Hipervisor";
        }
    }
}
