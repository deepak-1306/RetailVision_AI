#!/usr/bin/env bash
# Run the React frontend locally without Docker.
set -e
cd "$(dirname "$0")/../frontend"
npm install
npm run dev
