#Requires -RunAsAdministrator
<#
  One-time setup: lets a Mac reach this Windows development VM (Parallels) over SSH, for the jobs that need
  Windows: Winlink Express checks, the Windows installer roles, the PowerShell release builds.

  Run it in Windows PowerShell opened with "Run as administrator":
      powershell -ExecutionPolicy Bypass -File \\Mac\Projects\church-emcomm-wnlk-forms\dev\setup-windows-vm-ssh.ps1
  Add another Mac's key later (copy its ~/.ssh/id_ed25519.pub somewhere this VM can read):
      ... -File ...\setup-windows-vm-ssh.ps1 -PublicKeyFile C:\Mac\Home\Downloads\mac-studio.pub
  After both Macs log in with their keys, turn off password logins:
      ... -File ...\setup-windows-vm-ssh.ps1 -KeysOnly
  With Tailscale installed on this VM, also allow SSH from your Tailscale devices (for a Mac not on this local network):
      ... -File ...\setup-windows-vm-ssh.ps1 -Tailscale

  What it does: installs the Windows OpenSSH Server, starts it now and at every boot, allows port 22 from the
  local network only, makes Windows PowerShell the login shell, and adds the Mac's public key to
  C:\ProgramData\ssh\administrators_authorized_keys (an administrator account reads its keys there, not from
  ~\.ssh). It reads public keys only; no secret is written into this file or the repository.
#>
param(
    [string[]]$PublicKeyFile = @('C:\Mac\Home\.ssh\id_ed25519.pub'),
    [switch]$KeysOnly,
    [switch]$Tailscale
)
$ErrorActionPreference = 'Stop'

# 1. OpenSSH Server
$cap = Get-WindowsCapability -Online -Name 'OpenSSH.Server*' | Select-Object -First 1
if ($cap.State -ne 'Installed') {
    Write-Host 'Installing OpenSSH Server (a few minutes)...'
    Add-WindowsCapability -Online -Name $cap.Name | Out-Null
}
Set-Service sshd -StartupType Automatic
Start-Service sshd
Write-Host 'OpenSSH Server: running, starts at boot.'

# 2. Firewall: port 22 from the local network only (any network profile; this VM's network is marked Public).
#    -Tailscale adds Tailscale's address range, which a rule for the local subnet does not cover. The range sticks:
#    a later run without the switch keeps it, so -KeysOnly on its own does not cut off a Mac that uses Tailscale.
$rule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
$allowed = @('LocalSubnet')
if ($rule -and (($rule | Get-NetFirewallAddressFilter).RemoteAddress -contains '100.64.0.0/255.192.0.0')) { $Tailscale = $true }
if ($Tailscale) { $allowed += '100.64.0.0/10' }
if (-not $rule) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Direction Inbound `
        -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -RemoteAddress $allowed | Out-Null
} else {
    Set-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -Enabled True -Profile Any -RemoteAddress $allowed
}
Write-Host "Firewall: port 22 open to $($allowed -join ' and ') only."

# 3. Login shell: Windows PowerShell 5.1
New-Item -Path 'HKLM:\SOFTWARE\OpenSSH' -Force | Out-Null
New-ItemProperty -Path 'HKLM:\SOFTWARE\OpenSSH' -Name DefaultShell -PropertyType String -Force `
    -Value "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" | Out-Null
Write-Host 'Login shell: Windows PowerShell.'

# 4. Public keys -> administrators_authorized_keys (Administrators and SYSTEM only, or sshd ignores the file)
$auth = 'C:\ProgramData\ssh\administrators_authorized_keys'
if (-not (Test-Path $auth)) { New-Item -ItemType File -Path $auth -Force | Out-Null }
$have = @(Get-Content $auth -ErrorAction SilentlyContinue | Where-Object { $_.Trim() })
foreach ($f in $PublicKeyFile) {
    if (-not (Test-Path $f)) { Write-Warning "No public key at $f (skipped)"; continue }
    foreach ($k in (Get-Content $f | Where-Object { $_ -match '^(ssh-|ecdsa-)' })) {
        if ($have -contains $k.Trim()) { Write-Host "Key already present: $($k.Split(' ')[-1])" }
        else { Add-Content -Path $auth -Value $k.Trim() -Encoding ascii; $have += $k.Trim(); Write-Host "Key added: $($k.Split(' ')[-1])" }
    }
}
icacls $auth /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null

# 5. Optional: keys only
$cfg = 'C:\ProgramData\ssh\sshd_config'
if ($KeysOnly) {
    if ($have.Count -eq 0) { throw 'No key in administrators_authorized_keys: refusing to turn off password logins.' }
    $t = Get-Content $cfg -Raw
    $t = [regex]::Replace($t, '(?m)^#?\s*PasswordAuthentication\s+\S+', 'PasswordAuthentication no')
    if ($t -notmatch '(?m)^PasswordAuthentication no') { $t = "PasswordAuthentication no`r`n" + $t }
    Set-Content -Path $cfg -Value $t -Encoding ascii
    Write-Host 'Password logins: off (keys only).'
}
Restart-Service sshd

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254*' } | Select-Object -First 1).IPAddress
Write-Host ''
Write-Host "Done. On each Mac, add to ~/.ssh/config:"
Write-Host ''
Write-Host "  Host $($env:COMPUTERNAME.ToLower())"
Write-Host "    HostName $ip"
Write-Host "    User $env:USERNAME"
Write-Host ''
Write-Host "Then test from the Mac:  ssh $($env:COMPUTERNAME.ToLower()) hostname"
