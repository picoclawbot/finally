#!/bin/bash

# FinAlly Start Script
IMAGE_NAME="finally-app"
CONTAINER_NAME="finally-container"
PORT=8000

echo "🚀 Starting FinAlly — AI Trading Workstation..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️ .env file not found. Creating a mock one..."
    echo "OPENROUTER_API_KEY=your_key_here" > .env
    echo "LLM_MOCK=true" >> .env
fi

# Build image if it doesn't exist or --build flag is passed
if [[ "$(docker images -q $IMAGE_NAME 2> /dev/null)" == "" ]] || [[ "$1" == "--build" ]]; then
    echo "📦 Building Docker image..."
    docker build -t $IMAGE_NAME .
fi

# Stop existing container if running
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo "🛑 Stopping existing container..."
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
fi

# Run container
echo "🏃 Running container on port $PORT..."
docker run -d \
    --name $CONTAINER_NAME \
    -p $PORT:8000 \
    --env-file .env \
    -v $(pwd)/db:/app/db \
    $IMAGE_NAME

echo "✅ FinAlly is live at http://localhost:$PORT"

# Open browser if on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 2
    open "http://localhost:$PORT"
fi
