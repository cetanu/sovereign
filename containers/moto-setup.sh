#!/bin/bash
set -e

moto_server -H 0.0.0.0 -p $MOTO_PORT &
PID=$!

echo "Waiting for moto server to be ready..."
for i in {1..30}; do
    if curl -s -f http://localhost:$MOTO_PORT/ > /dev/null 2>&1; then
        echo "Moto server is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Moto server failed to start within 30 seconds"
        exit 1
    fi
    echo "Waiting for moto server... ($i/30)"
    sleep 1
done

echo "Creating S3 bucket: $S3_BUCKET_NAME"
aws --endpoint-url=http://localhost:$MOTO_PORT s3 mb s3://$S3_BUCKET_NAME --region $AWS_DEFAULT_REGION || {
    echo "Warning: Failed to create bucket $S3_BUCKET_NAME, it may already exist"
}

echo "Verifying S3 bucket exists..."
aws --endpoint-url=http://localhost:$MOTO_PORT s3 ls s3://$S3_BUCKET_NAME > /dev/null || {
    echo "Error: S3 bucket $S3_BUCKET_NAME does not exist or is not accessible"
    exit 1
}

echo "Moto server is ready and configured"

wait $PID
