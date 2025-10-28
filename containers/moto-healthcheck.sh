#!/bin/bash

if ! curl -s -f http://localhost:$MOTO_PORT/ > /dev/null 2>&1; then
    echo "Moto server is not responding"
    exit 1
fi

if ! aws --endpoint-url=http://localhost:$MOTO_PORT s3 ls s3://$S3_BUCKET_NAME > /dev/null 2>&1; then
    echo "S3 bucket $S3_BUCKET_NAME is not accessible"
    exit 1
fi

echo "Moto service is healthy and ready"
exit 0
