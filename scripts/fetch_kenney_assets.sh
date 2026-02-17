#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ASSET_DIR="$BASE_DIR/app/assets/kenney"
mkdir -p "$ASSET_DIR"

cd "$ASSET_DIR"

curl -L -o kenney_mini-characters.zip "https://kenney.nl/media/pages/assets/mini-characters-1/a745467fe1-1721210573/kenney_mini-characters.zip"
curl -L -o kenney_furniture-kit.zip "https://kenney.nl/media/pages/assets/furniture-kit/e56d2a9828-1677580847/kenney_furniture-kit.zip"
curl -L -o kenney_food-kit.zip "https://kenney.nl/media/pages/assets/food-kit/719eef5f43-1719418518/kenney_food-kit.zip"

mkdir -p mini-characters furniture-kit food-kit
unzip -o kenney_mini-characters.zip -d mini-characters >/dev/null
unzip -o kenney_furniture-kit.zip -d furniture-kit >/dev/null
unzip -o kenney_food-kit.zip -d food-kit >/dev/null

echo "Assets ready under: $ASSET_DIR"
