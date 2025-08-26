# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import base64
import time
import argparse
from datetime import datetime
import sys

lambda_client = boto3.client("lambda")


def invoke_lambda_tool(function_name, tool_name, event_data):
    """Helper function to invoke Lambda with proper context setup."""
    # Add tool name to event
    event_data["tool_name"] = tool_name

    # Context with tool name (simulated for direct Lambda invocation)
    context_custom = {"bedrockagentcoreToolName": tool_name}

    response = lambda_client.invoke(
        FunctionName=function_name,
        Payload=json.dumps(event_data),
        ClientContext=base64.b64encode(
            json.dumps({"custom": context_custom}).encode()
        ).decode(),
    )

    return json.loads(response["Payload"].read())


def print_separator(title):
    """Print a formatted separator."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="🧬 SageMaker Async Inference Lambda Function Demo",
        epilog="""
Examples:
  %(prog)s protein-agent-1756142024-async-endpoint-lambda
  %(prog)s my-function --sequence "MKTVRQERLK" --max-attempts 30
  
To find your Lambda function name:
  aws lambda list-functions --query 'Functions[?contains(FunctionName, `async-endpoint`)].FunctionName' --output table
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("function_name", help="Name of the Lambda function to invoke")

    parser.add_argument(
        "--sequence",
        default="MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG",
        help="Protein sequence to analyze (default: sample sequence)",
    )

    parser.add_argument(
        "--max-attempts",
        type=int,
        default=20,
        help="Maximum polling attempts for results (default: 20)",
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=15,
        help="Initial polling interval in seconds (default: 15)",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print("🧬 SageMaker Async Inference Lambda Function Demo")
    print("This example demonstrates both invoke_endpoint and get_results tools")
    print(f"🔧 Using Lambda function: {args.function_name}")

    # Verify the function exists
    try:
        lambda_client.get_function(FunctionName=args.function_name)
        print("✅ Lambda function found and accessible")
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"❌ Lambda function '{args.function_name}' not found")
        print(
            "💡 Make sure the function name is correct and you have the right AWS permissions"
        )
        return 1
    except Exception as e:
        print(f"❌ Error accessing Lambda function: {e}")
        return 1

    # Step 1: Invoke the endpoint
    print_separator("STEP 1: INVOKING SAGEMAKER ENDPOINT")

    # Event payload for invoke_endpoint
    invoke_event = {"sequence": args.sequence}

    print(f"🔬 Protein sequence: {invoke_event['sequence']}")
    print(f"📏 Sequence length: {len(invoke_event['sequence'])} amino acids")
    print("\n🚀 Invoking SageMaker async endpoint...")

    invoke_result = invoke_lambda_tool(
        args.function_name, "invoke_endpoint", invoke_event
    )

    print(f"📊 Lambda Response Status: 200")

    if invoke_result.get("success") and "data" in invoke_result:
        output_id = invoke_result["data"]["output_id"]
        s3_output_path = invoke_result["data"]["s3_output_path"]
        estimated_completion = invoke_result["data"]["estimated_completion_time"]

        print(f"✅ Success! Async inference request submitted")
        print(f"🆔 Output ID: {output_id}")
        print(f"📁 Output will be available at: {s3_output_path}")
        print(f"⏱️  Estimated completion: {estimated_completion}")

        # Step 2: Poll for results
        print_separator("STEP 2: POLLING FOR RESULTS")

        max_attempts = args.max_attempts  # Maximum polling attempts
        poll_interval = args.poll_interval  # Seconds between polls
        attempt = 1

        print(
            f"🔄 Starting to poll for results (max {max_attempts} attempts, {poll_interval}s intervals)"
        )

        while attempt <= max_attempts:
            print(
                f"\n📡 Polling attempt {attempt}/{max_attempts} at {datetime.now().strftime('%H:%M:%S')}"
            )

            # Event payload for get_results - use output ID
            results_event = {"output_id": output_id}  # Pass the output ID

            results_response = invoke_lambda_tool(
                args.function_name, "get_results", results_event
            )

            if results_response.get("success") and "data" in results_response:
                data = results_response["data"]
                status = data.get("status")

                if status == "completed":
                    print_separator("🎉 RESULTS READY!")

                    results = data.get("results", {})
                    completion_time = data.get("completion_time")

                    print(f"✅ Prediction completed successfully!")
                    print(f"⏰ Completion time: {completion_time}")
                    print(f"📊 Results summary:")

                    if isinstance(results, dict):
                        if "heatmap" in results:
                            heatmap = results["heatmap"]
                            print(
                                f"   🔥 Heatmap dimensions: {len(heatmap)} x {len(heatmap[0]) if heatmap else 0}"
                            )

                        if "outliers" in results:
                            outliers = results["outliers"]
                            print(f"   📈 Number of outliers detected: {len(outliers)}")

                            # Show top 5 most beneficial and harmful mutations
                            if outliers:
                                print(f"\n   🔝 Top beneficial mutations:")
                                beneficial = [
                                    o
                                    for o in outliers
                                    if isinstance(o, str) and float(o.split()[-1]) > 0
                                ]
                                beneficial.sort(
                                    key=lambda x: float(x.split()[-1]), reverse=True
                                )
                                for i, mutation in enumerate(beneficial[:3]):
                                    print(f"      {i+1}. {mutation}")

                                print(f"\n   ⚠️  Most harmful mutations:")
                                harmful = [
                                    o
                                    for o in outliers
                                    if isinstance(o, str) and float(o.split()[-1]) < 0
                                ]
                                harmful.sort(key=lambda x: float(x.split()[-1]))
                                for i, mutation in enumerate(harmful[:3]):
                                    print(f"      {i+1}. {mutation}")

                        print(
                            f"\n📁 Full results available at: {data.get('s3_output_path')}"
                        )
                    else:
                        print(f"   📄 Results type: {type(results)}")
                        print(f"   📏 Results size: {len(str(results))} characters")

                    break

                elif status == "in_progress":
                    message = data.get("message", "Prediction in progress")
                    estimated_completion = data.get("estimated_completion")
                    check_interval = data.get("check_interval_seconds", poll_interval)

                    print(f"⏳ {message}")
                    if estimated_completion:
                        print(f"⏰ Estimated completion: {estimated_completion}")

                    # Update poll interval based on server recommendation
                    if check_interval != poll_interval:
                        poll_interval = check_interval
                        print(f"🔄 Updated poll interval to {poll_interval} seconds")

                elif status == "failed":
                    print_separator("❌ PREDICTION FAILED")

                    error_details = data.get("error_details", {})
                    failure_time = data.get("failure_time")
                    s3_failure_path = data.get("s3_failure_path")

                    print(f"💥 Prediction failed at: {failure_time}")
                    print(f"📁 Failure details at: {s3_failure_path}")

                    if isinstance(error_details, dict):
                        error_message = error_details.get(
                            "error_message", "No error message available"
                        )
                        error_type = error_details.get(
                            "error_type", "Unknown error type"
                        )
                        print(f"🔍 Error type: {error_type}")
                        print(f"💬 Error message: {error_message}")

                    break

            elif not results_response.get("success"):
                error_code = results_response.get("error_code", "UNKNOWN_ERROR")
                error_message = results_response.get(
                    "message", "Unknown error occurred"
                )

                print(f"❌ Error checking results: {error_code}")
                print(f"💬 Error message: {error_message}")

                # Some errors are retryable, others are not
                if error_code in ["S3_SERVICE_UNAVAILABLE", "BOTO_CONNECTION_ERROR"]:
                    print(f"🔄 Retryable error, continuing to poll...")
                else:
                    print(f"🛑 Non-retryable error, stopping polling")
                    break

            # Wait before next attempt (unless this was the last attempt)
            if attempt < max_attempts:
                print(f"⏸️  Waiting {poll_interval} seconds before next check...")
                time.sleep(poll_interval)

            attempt += 1

        if attempt > max_attempts:
            print_separator("⏰ POLLING TIMEOUT")
            print(f"🕐 Reached maximum polling attempts ({max_attempts})")
            print(f"💡 The prediction may still be running. You can:")
            print(f"   1. Check manually later using output ID: {output_id}")
            print(f"   2. Check S3 directly at: {s3_output_path}")
            print(f"   3. Increase max_attempts in the script for longer polling")

    else:
        print(f"❌ Failed to invoke endpoint")
        print(f"💬 Error: {invoke_result.get('message', 'Unknown error')}")
        if "error_code" in invoke_result:
            print(f"🔍 Error code: {invoke_result['error_code']}")


if __name__ == "__main__":
    exit_code = main()
    if exit_code:
        sys.exit(exit_code)
