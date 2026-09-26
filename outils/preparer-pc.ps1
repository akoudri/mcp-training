#Requires -RunAsAdministrator
# Préparation d'un PC Windows pour la formation PHAROS : WSL2 + Ubuntu 24.04 + VS Code.
$ErrorActionPreference = "Stop"

$virt = (Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled
if (-not $virt) {
    Write-Error "La virtualisation est désactivée dans le BIOS/UEFI : l'activer (Intel VT-x / AMD-V), puis relancer."
}

wsl --install --no-distribution
wsl --set-default-version 2
wsl --install -d Ubuntu-24.04

Write-Host ""
Write-Host "==> VS Code et extension Remote-WSL"
$codeCmd = "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd"
if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install -e --id Microsoft.VisualStudioCode --accept-package-agreements --accept-source-agreements
    if (Test-Path $codeCmd) {
        & $codeCmd --install-extension ms-vscode-remote.remote-wsl
    } else {
        Write-Warning "VS Code introuvable à $codeCmd : l'installer depuis https://code.visualstudio.com puis lancer : code --install-extension ms-vscode-remote.remote-wsl"
    }
} else {
    Write-Host "winget introuvable : installer VS Code manuellement depuis https://code.visualstudio.com,"
    Write-Host "puis lancer : code --install-extension ms-vscode-remote.remote-wsl"
}

Write-Host ""
Write-Host "Redémarrer le PC si Windows le demande, puis ouvrir « Ubuntu 24.04 », créer l'utilisateur,"
Write-Host "et lancer dans Ubuntu :"
Write-Host "  curl -fsSL https://raw.githubusercontent.com/akoudri/pharos-labs/main/outils/preparer-pc.sh | bash"
Write-Host "(dépôt privé : copier le script depuis la clé USB du formateur si l'accès GitHub n'est pas configuré)"
Write-Host ""
Write-Host "Ensuite, dans VS Code : « Remote-WSL: Open Folder in WSL » > ~/pharos-labs."
