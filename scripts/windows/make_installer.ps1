
```powershell
# path: scripts/windows/make_installer.ps1
param(
  [string]$StagingDir = ".\staging",
  [string]$OutMsix = ".\M1.msix",
  [string]$PfxPath = "",
  [string]$PfxPass = ""
)

Write-Host "== MinuteOne (M1) MSIX packer =="

# 1) Prepare staging
New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null
# (In a real build, copy backend/, ui/, config/, models/ into VFS/ProgramFilesX64/M1/)
New-Item -ItemType Directory -Force -Path "$StagingDir\VFS\ProgramFilesX64\M1" | Out-Null
Copy-Item -Recurse -Force ..\backend, ..\ui, ..\config, ..\models, ..\exports "$StagingDir\VFS\ProgramFilesX64\M1" -ErrorAction SilentlyContinue

# 2) Ensure manifest exists
$manifest = Join-Path $StagingDir "AppxManifest.xml"
if (!(Test-Path $manifest)) {
@"
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         IgnorableNamespaces="uap">
  <Identity Name="com.minuteone.m1" Publisher="CN=MinuteOne LLC" Version="0.1.0.0" />
  <Properties>
    <DisplayName>MinuteOne (M1)</DisplayName>
    <PublisherDisplayName>MinuteOne</PublisherDisplayName>
    <Logo>Assets\Square150x150Logo.png</Logo>
  </Properties>
  <Resources>
    <Resource Language="en-us" />
  </Resources>
  <Applications>
    <Application Id="M1" Executable="python.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="MinuteOne (M1)" Square150x150Logo="Assets\Square150x150Logo.png" Square44x44Logo="Assets\Square44x44Logo.png" Description="Offline-first bedside assistant" />
    </Application>
  </Applications>
</Package>
"@ | Out-File -Encoding utf8 $manifest
}

# 3) Pack
if (Get-Command MakeAppx.exe -ErrorAction SilentlyContinue) {
  & MakeAppx.exe pack /d $StagingDir /p $OutMsix
} else {
  Write-Warning "MakeAppx.exe not found. Install Windows 10 SDK."
}

# 4) Sign (optional)
if ($PfxPath -and (Test-Path $PfxPath) -and (Get-Command signtool.exe -ErrorAction SilentlyContinue)) {
  & signtool.exe sign /fd SHA256 /f $PfxPath /p $PfxPass $OutMsix
} else {
  Write-Warning "Skipping signing (no PFX or signtool)."
}
Write-Host "Done -> $OutMsix"
