param(
    [string]$PicoSdkPath = $env:PICO_SDK_PATH,
    [string]$ToolchainPath = $env:PICO_TOOLCHAIN_PATH
)
$ErrorActionPreference = 'Stop'
if (-not $PicoSdkPath) { throw 'Set PICO_SDK_PATH, or pass -PicoSdkPath.' }
$PicoSdkPath = (Resolve-Path -LiteralPath $PicoSdkPath).Path
if ($ToolchainPath) { $ToolchainPath = (Resolve-Path -LiteralPath $ToolchainPath).Path }
$projectDir = Split-Path $PSScriptRoot -Parent
$buildDir = Join-Path $projectDir 'build/pico'
$cmakeArgs = @('-S', $projectDir, '-B', $buildDir, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release', '-DPICO_BOARD=pico', "-DPICO_SDK_PATH=$PicoSdkPath")
if ($ToolchainPath) { $cmakeArgs += "-DPICO_TOOLCHAIN_PATH=$ToolchainPath" }
& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed.' }
& cmake --build $buildDir --parallel
if ($LASTEXITCODE -ne 0) { throw 'Firmware build failed.' }
Write-Host "UF2: $buildDir/pico_ocarina.uf2"
