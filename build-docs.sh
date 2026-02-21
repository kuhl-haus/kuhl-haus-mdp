#!/usr/bin/env bash
# build-docs.sh
# Builds the Sphinx documentation locally and opens it in the default browser.
#
# Usage:
#   ./build-docs.sh
#   ./build-docs.sh --clean

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$project_root/docs"
build_dir="$source_dir/_build/html"

clean=false
for arg in "$@"; do
    case "$arg" in
        --clean) clean=true ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

if $clean && [ -d "$source_dir/_build" ]; then
    echo "Cleaning previous build..."
    rm -rf "$source_dir/_build"
fi
echo "Building Sphinx documentation..."
python -m sphinx -b html "$source_dir" "$build_dir"

index_file="$build_dir/index.html"
echo "Opening $index_file"

# Open in default browser (cross-platform)
if command -v xdg-open &>/dev/null; then
    xdg-open "$index_file"
elif command -v open &>/dev/null; then
    open "$index_file"
else
    echo "Could not detect a command to open the browser. Please open manually:"
    echo "  $index_file"
fi
