param(
    [ValidateSet('full','first')][string]$Variant = 'full',
    [string]$PicoSdkPath = $env:PICO_SDK_PATH,
    [string]$ToolchainPath = $env:PICO_TOOLCHAIN_PATH
)
$ErrorActionPreference = 'Stop'
if (-not $PicoSdkPath) { throw 'Set PICO_SDK_PATH, or pass -PicoSdkPath.' }
$projectDir = Split-Path $PSScriptRoot -Parent
$buildDir = Join-Path $projectDir "build/$Variant"
$cmakeArgs = @('-S', $projectDir, '-B', $buildDir, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release', '-DPICO_BOARD=pico', "-DOCARINA_SONG_VARIANT=$Variant", "-DPICO_SDK_PATH=$PicoSdkPath")
if ($ToolchainPath) { $cmakeArgs += "-DPICO_TOOLCHAIN_PATH=$ToolchainPath" }
& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed.' }
& cmake --build $buildDir --parallel
if ($LASTEXITCODE -ne 0) { throw 'Firmware build failed.' }
Write-Host "UF2: $buildDir/pico_ocarina.uf2"
