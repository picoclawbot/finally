#!/bin/bash

# FinAlly Stop Script
CONTAINER_NAME="finally-container"

echo "🛑 Stopping FinAlly..."

if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
    echo "✅ Container stopped and removed."
else
    echo "ℹ️ Container is not running."
fi
