#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for variant in full first; do
  build_dir="$project_dir/out/native-$variant"
  cmake -S "$project_dir" -B "$build_dir" -G Ninja -DOCARINA_HOST_TESTS=ON "-DOCARINA_SONG_VARIANT=$variant" -DCMAKE_BUILD_TYPE=Debug
  cmake --build "$build_dir" --parallel
  ctest --test-dir "$build_dir" --output-on-failure
done
