#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Benchmark script for SageMaker Async Inference Lambda Function.

This script tests the Lambda function with sequences of increasing length
to measure performance characteristics and scaling behavior.
"""

import boto3
import json
import base64
import time
import argparse
from datetime import datetime
import sys
import csv
from typing import Dict, Any, List, Optional

lambda_client = boto3.client("lambda")

# Base sequence to concatenate for testing (100 amino acids)
BASE_SEQUENCE = "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSIC"


def invoke_lambda_tool(function_name: str, tool_name: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
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


def print_separator(title: str) -> None:
    """Print a formatted separator."""
    print(f"\n{'='*80}")
    print(f" {title}")
    print(f"{'='*80}")


def generate_test_sequence(copies: int) -> str:
    """Generate test sequence by concatenating base sequence."""
    return BASE_SEQUENCE * copies


def run_single_benchmark(
    function_name: str, 
    copies: int, 
    max_attempts: int = 30, 
    poll_interval: int = 15
) -> Dict[str, Any]:
    """
    Run a single benchmark test with specified sequence length.
    
    Args:
        function_name: Lambda function name
        copies: Number of times to concatenate base sequence
        max_attempts: Maximum polling attempts
        poll_interval: Polling interval in seconds
        
    Returns:
        Dictionary with benchmark results
    """
    sequence = generate_test_sequence(copies)
    sequence_length = len(sequence)
    
    print(f"\n🧬 Testing with {copies} copies ({sequence_length:,} amino acids)")
    
    # Record start time
    start_time = time.time()
    
    # Step 1: Invoke endpoint
    invoke_event = {"sequence": sequence}
    
    try:
        invoke_result = invoke_lambda_tool(function_name, "invoke_endpoint", invoke_event)
        
        if not invoke_result.get("success") or "data" not in invoke_result:
            return {
                "copies": copies,
                "sequence_length": sequence_length,
                "status": "failed",
                "error": invoke_result.get("message", "Unknown error"),
                "invoke_time": time.time() - start_time,
                "total_time": None,
                "completion_time": None
            }
        
        output_id = invoke_result["data"]["output_id"]
        invoke_time = time.time() - start_time
        
        print(f"✅ Endpoint invoked successfully in {invoke_time:.2f}s")
        print(f"🆔 Output ID: {output_id}")
        
        # Step 2: Poll for results
        poll_start_time = time.time()
        attempt = 1
        
        while attempt <= max_attempts:
            results_event = {"output_id": output_id}
            results_response = invoke_lambda_tool(function_name, "get_results", results_event)
            
            if results_response.get("success") and "data" in results_response:
                data = results_response["data"]
                status = data.get("status")
                
                if status == "completed":
                    total_time = time.time() - start_time
                    poll_time = time.time() - poll_start_time
                    completion_time = data.get("completion_time")
                    
                    print(f"🎉 Completed in {total_time:.2f}s (polling: {poll_time:.2f}s)")
                    
                    return {
                        "copies": copies,
                        "sequence_length": sequence_length,
                        "status": "completed",
                        "invoke_time": invoke_time,
                        "poll_time": poll_time,
                        "total_time": total_time,
                        "completion_time": completion_time,
                        "attempts": attempt,
                        "results_summary": _extract_results_summary(data.get("results", {}))
                    }
                
                elif status == "failed":
                    total_time = time.time() - start_time
                    error_details = data.get("error_details", {})
                    
                    return {
                        "copies": copies,
                        "sequence_length": sequence_length,
                        "status": "failed",
                        "error": error_details.get("error_message", "Prediction failed"),
                        "invoke_time": invoke_time,
                        "total_time": total_time,
                        "completion_time": None,
                        "attempts": attempt
                    }
                
                elif status == "in_progress":
                    if attempt % 5 == 0:  # Print progress every 5 attempts
                        elapsed = time.time() - start_time
                        print(f"⏳ Still processing... ({elapsed:.0f}s elapsed, attempt {attempt})")
            
            # Wait before next attempt
            if attempt < max_attempts:
                time.sleep(poll_interval)
            
            attempt += 1
        
        # Timeout
        total_time = time.time() - start_time
        return {
            "copies": copies,
            "sequence_length": sequence_length,
            "status": "timeout",
            "error": f"Timeout after {max_attempts} attempts",
            "invoke_time": invoke_time,
            "total_time": total_time,
            "completion_time": None,
            "attempts": max_attempts
        }
        
    except Exception as e:
        total_time = time.time() - start_time
        return {
            "copies": copies,
            "sequence_length": sequence_length,
            "status": "error",
            "error": str(e),
            "invoke_time": None,
            "total_time": total_time,
            "completion_time": None
        }


def _extract_results_summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Extract summary information from results."""
    summary = {}
    
    if isinstance(results, dict):
        if "heatmap" in results:
            heatmap = results["heatmap"]
            if heatmap:
                summary["heatmap_dimensions"] = f"{len(heatmap)}x{len(heatmap[0]) if heatmap else 0}"
        
        if "outliers" in results:
            outliers = results["outliers"]
            summary["outlier_count"] = len(outliers) if outliers else 0
    
    return summary


def save_results_to_csv(results: List[Dict[str, Any]], filename: str) -> None:
    """Save benchmark results to CSV file."""
    if not results:
        return
    
    fieldnames = [
        "copies", "sequence_length", "status", "invoke_time", "poll_time", 
        "total_time", "completion_time", "attempts", "error", "heatmap_dimensions", "outlier_count"
    ]
    
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            row = result.copy()
            
            # Flatten results_summary
            if "results_summary" in row:
                summary = row.pop("results_summary")
                row.update(summary)
            
            # Ensure all fields are present
            for field in fieldnames:
                if field not in row:
                    row[field] = None
            
            writer.writerow(row)
    
    print(f"📊 Results saved to: {filename}")


def print_summary_table(results: List[Dict[str, Any]]) -> None:
    """Print a summary table of benchmark results."""
    print_separator("BENCHMARK SUMMARY")
    
    print(f"{'Copies':<8} {'Length':<10} {'Status':<12} {'Invoke':<8} {'Total':<8} {'Outliers':<10}")
    print("-" * 70)
    
    for result in results:
        copies = result["copies"]
        length = f"{result['sequence_length']:,}"
        status = result["status"]
        
        invoke_time = f"{result['invoke_time']:.1f}s" if result.get("invoke_time") else "N/A"
        total_time = f"{result['total_time']:.1f}s" if result.get("total_time") else "N/A"
        
        outliers = result.get("results_summary", {}).get("outlier_count", "N/A")
        outliers_str = str(outliers) if outliers != "N/A" else "N/A"
        
        print(f"{copies:<8} {length:<10} {status:<12} {invoke_time:<8} {total_time:<8} {outliers_str:<10}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="🧬 SageMaker Async Inference Lambda Benchmark Tool",
        epilog="""
Examples:
  %(prog)s protein-agent-1756142024-async-endpoint-lambda
  %(prog)s my-function --max-copies 10 --max-attempts 20
  %(prog)s my-function --start-copies 5 --max-copies 15 --output benchmark_results.csv
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("function_name", help="Name of the Lambda function to benchmark")

    parser.add_argument(
        "--start-copies",
        type=int,
        default=1,
        help="Starting number of sequence copies (default: 1)"
    )

    parser.add_argument(
        "--max-copies",
        type=int,
        default=20,
        help="Maximum number of sequence copies (default: 20)"
    )

    parser.add_argument(
        "--max-attempts",
        type=int,
        default=30,
        help="Maximum polling attempts per test (default: 30)"
    )

    parser.add_argument(
        "--poll-interval",
        type=int,
        default=15,
        help="Polling interval in seconds (default: 15)"
    )

    parser.add_argument(
        "--output",
        help="Output CSV file for results (default: benchmark_TIMESTAMP.csv)"
    )

    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Continue benchmarking even if a test fails"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    print("🧬 SageMaker Async Inference Lambda Benchmark Tool")
    print(f"🔧 Lambda function: {args.function_name}")
    print(f"📏 Base sequence length: {len(BASE_SEQUENCE)} amino acids")
    print(f"🔢 Testing {args.start_copies} to {args.max_copies} copies")
    print(f"📊 Total sequence lengths: {args.start_copies * len(BASE_SEQUENCE):,} to {args.max_copies * len(BASE_SEQUENCE):,} amino acids")

    # Verify the function exists
    try:
        lambda_client.get_function(FunctionName=args.function_name)
        print("✅ Lambda function found and accessible")
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"❌ Lambda function '{args.function_name}' not found")
        return 1
    except Exception as e:
        print(f"❌ Error accessing Lambda function: {e}")
        return 1

    # Prepare output filename
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"benchmark_{timestamp}.csv"

    print_separator("STARTING BENCHMARK")

    results = []
    
    for copies in range(args.start_copies, args.max_copies + 1):
        try:
            result = run_single_benchmark(
                args.function_name, 
                copies, 
                args.max_attempts, 
                args.poll_interval
            )
            results.append(result)
            
            # Check if we should continue on failure
            if result["status"] in ["failed", "error", "timeout"] and not args.continue_on_failure:
                print(f"\n❌ Test failed for {copies} copies. Stopping benchmark.")
                print(f"💡 Use --continue-on-failure to continue despite failures")
                break
                
        except KeyboardInterrupt:
            print(f"\n⏹️  Benchmark interrupted by user")
            break
        except Exception as e:
            print(f"\n💥 Unexpected error during benchmark: {e}")
            if not args.continue_on_failure:
                break

    # Save and display results
    if results:
        save_results_to_csv(results, output_file)
        print_summary_table(results)
        
        # Calculate some statistics
        completed_results = [r for r in results if r["status"] == "completed"]
        if completed_results:
            print_separator("PERFORMANCE STATISTICS")
            
            avg_invoke_time = sum(r["invoke_time"] for r in completed_results) / len(completed_results)
            avg_total_time = sum(r["total_time"] for r in completed_results) / len(completed_results)
            
            print(f"📈 Completed tests: {len(completed_results)}/{len(results)}")
            print(f"⚡ Average invoke time: {avg_invoke_time:.2f}s")
            print(f"⏱️  Average total time: {avg_total_time:.2f}s")
            
            # Find scaling characteristics
            if len(completed_results) > 1:
                min_length = min(r["sequence_length"] for r in completed_results)
                max_length = max(r["sequence_length"] for r in completed_results)
                min_time = min(r["total_time"] for r in completed_results)
                max_time = max(r["total_time"] for r in completed_results)
                
                print(f"📏 Length range: {min_length:,} - {max_length:,} amino acids")
                print(f"⏰ Time range: {min_time:.1f}s - {max_time:.1f}s")
                
                if max_length > min_length:
                    scaling_factor = (max_time / min_time) / (max_length / min_length)
                    print(f"📊 Scaling factor: {scaling_factor:.2f}x (time increase per length increase)")
    else:
        print("❌ No results to save")

    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code:
        sys.exit(exit_code)