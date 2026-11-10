#!/usr/bin/env bash
set -euo pipefail
variant="${1:-full}"
case "$variant" in full|first) ;; *) echo 'Usage: scripts/build.sh [full|first]' >&2; exit 2;; esac
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${PICO_SDK_PATH:?Set PICO_SDK_PATH to the Pico SDK 2.1.1 directory}"
args=(-S "$project_dir" -B "$project_dir/build/$variant" -G Ninja -DCMAKE_BUILD_TYPE=Release -DPICO_BOARD=pico "-DOCARINA_SONG_VARIANT=$variant" "-DPICO_SDK_PATH=$PICO_SDK_PATH")
if [[ -n "${PICO_TOOLCHAIN_PATH:-}" ]]; then args+=("-DPICO_TOOLCHAIN_PATH=$PICO_TOOLCHAIN_PATH"); fi
cmake "${args[@]}"
cmake --build "$project_dir/build/$variant" --parallel
printf 'UF2: %s/build/%s/pico_ocarina.uf2\n' "$project_dir" "$variant"
