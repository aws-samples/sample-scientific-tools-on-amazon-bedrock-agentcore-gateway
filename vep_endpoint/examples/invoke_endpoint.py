#!/usr/bin/env python3
"""
Example script for invoking the SageMaker Async Inference endpoint.

This script demonstrates how to:
1. Upload input data to S3
2. Invoke the async endpoint
3. Poll for results
4. Handle errors and retries
"""

import boto3
import json
import time
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import argparse
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SageMakerAsyncClient:
    """Client for interacting with SageMaker Async Inference endpoints."""

    def __init__(self, endpoint_name: str, bucket_name: str, region: str = "us-east-1"):
        """
        Initialize the async client.

        Args:
            endpoint_name: Name of the SageMaker endpoint
            bucket_name: S3 bucket name for input/output
            region: AWS region
        """
        self.endpoint_name = endpoint_name
        self.bucket_name = bucket_name
        self.region = region

        # Initialize AWS clients
        self.sagemaker = boto3.client("sagemaker-runtime", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)

    def upload_input(
        self, data: Dict[str, Any], input_key: Optional[str] = None
    ) -> str:
        """
        Upload input data to S3.

        Args:
            data: Input data dictionary
            input_key: Optional custom S3 key (auto-generated if None)

        Returns:
            S3 URI of uploaded data
        """
        if input_key is None:
            timestamp = int(time.time())
            input_key = f"async-inference-input/{timestamp}.json"

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=input_key,
                Body=json.dumps(data, indent=2),
                ContentType="application/json",
            )

            s3_uri = f"s3://{self.bucket_name}/{input_key}"
            logger.info(f"Input data uploaded to: {s3_uri}")
            return s3_uri

        # nosemgrep logging-error-without-handling
        except Exception as e:
            logger.error(f"Failed to upload input data: {e}")
            raise

    def invoke_async(self, input_location: str) -> str:
        """
        Invoke the async endpoint.

        Args:
            input_location: S3 URI of input data

        Returns:
            S3 URI where results will be stored
        """
        try:
            response = self.sagemaker.invoke_endpoint_async(
                EndpointName=self.endpoint_name,
                InputLocation=input_location,
                ContentType="application/json",
            )

            output_location = response["OutputLocation"]
            logger.info(
                f"Async invocation started. Results will be at: {output_location}"
            )
            return output_location

        # nosemgrep logging-error-without-handling
        except Exception as e:
            logger.error(f"Failed to invoke async endpoint: {e}")
            raise

    def wait_for_results(
        self, output_location: str, max_wait: int = 300, poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Poll for async inference results.

        Args:
            output_location: S3 URI where results will be stored
            max_wait: Maximum wait time in seconds
            poll_interval: Polling interval in seconds

        Returns:
            Results dictionary
        """
        parsed = urlparse(output_location)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")

        logger.info(f"Waiting for results at {output_location}")

        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = self.s3.get_object(Bucket=bucket, Key=key)
                results = json.loads(response["Body"].read())
                logger.info("Results retrieved successfully")
                return results

            except self.s3.exceptions.NoSuchKey:
                logger.debug(
                    f"Results not ready yet, waiting {poll_interval} seconds..."
                )
                # nosemgrep arbitrary-sleep
                time.sleep(poll_interval)
                continue

            except Exception as e:
                logger.error(f"Error retrieving results: {e}")
                raise

        raise TimeoutError(f"Results not available within {max_wait} seconds")

    def predict(self, data: Dict[str, Any], max_wait: int = 300) -> Dict[str, Any]:
        """
        Complete prediction workflow: upload, invoke, wait for results.

        Args:
            data: Input data dictionary
            max_wait: Maximum wait time for results

        Returns:
            Prediction results
        """
        # Upload input data
        input_location = self.upload_input(data)

        # Invoke async endpoint
        output_location = self.invoke_async(input_location)

        # Wait for and return results
        return self.wait_for_results(output_location, max_wait)


def create_sample_input() -> Dict[str, Any]:
    """Create sample input data for AMPLIFY model."""
    return {"sequence": "FVNQHLCGSHLVEALYLVCGERGFFYTPKT"}  # Human insulin B chain


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Invoke SageMaker Async Inference endpoint"
    )
    parser.add_argument(
        "--endpoint-name", required=True, help="SageMaker endpoint name"
    )
    parser.add_argument("--bucket-name", required=True, help="S3 bucket name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--input-file", help="JSON file with input data")
    parser.add_argument(
        "--max-wait", type=int, default=300, help="Maximum wait time in seconds"
    )

    args = parser.parse_args()

    # Initialize client
    client = SageMakerAsyncClient(
        endpoint_name=args.endpoint_name,
        bucket_name=args.bucket_name,
        region=args.region,
    )

    # Prepare input data
    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as f:
            input_data = json.load(f)
    else:
        input_data = create_sample_input()
        logger.info("Using sample input data")

    try:
        # Run prediction
        logger.info("Starting async prediction...")
        results = client.predict(input_data, max_wait=args.max_wait)

        # Display results
        print("\n" + "=" * 50)
        print("PREDICTION RESULTS")
        print("=" * 50)
        print(json.dumps(results, indent=2))

    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
