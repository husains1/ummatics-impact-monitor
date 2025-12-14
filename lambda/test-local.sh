#!/bin/bash
# Test sentiment Lambda function locally with Docker

set -e

echo "=== Testing Sentiment Lambda Locally ==="

# Build the image
echo "Building Docker image..."
cd lambda
docker build -t sentiment-lambda-test .

# Test with sample data
echo ""
echo "Running test invocation..."
docker run --rm \
    -p 9000:8080 \
    sentiment-lambda-test &

CONTAINER_PID=$!

# Wait for container to start
sleep 3

# Test invocation
echo ""
echo "Sending test request..."
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
    -d '{
        "texts": [
            "I love this product! It is amazing!",
            "This is terrible and I hate it.",
            "The weather is okay today."
        ]
    }' | python3 -m json.tool

echo ""
echo ""

# Cleanup
kill $CONTAINER_PID 2>/dev/null || true

echo "Test complete!"
