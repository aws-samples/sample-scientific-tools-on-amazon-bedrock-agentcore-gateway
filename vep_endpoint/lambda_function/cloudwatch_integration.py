# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Simplified CloudWatch integration for Lambda function monitoring.

This module provides basic CloudWatch logging and metrics functionality
for the SageMaker async endpoint Lambda function.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any

import boto3

logger = logging.getLogger(__name__)

# Global CloudWatch client for reuse
_cloudwatch_client = None


def get_cloudwatch_client():
    """Get CloudWatch client (lazy initialization)."""
    global _cloudwatch_client
    if _cloudwatch_client is None:
        try:
            _cloudwatch_client = boto3.client('cloudwatch')
        except Exception as e:
            logger.warning(f"Failed to initialize CloudWatch client: {e}")
    return _cloudwatch_client


def put_simple_metric(metric_name: str, value: float, unit: str = 'Count'):
    """
    Put a simple metric to CloudWatch.
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        unit: Metric unit (Count, Milliseconds, Bytes, etc.)
    """
    try:
        cw = get_cloudwatch_client()
        if cw:
            cw.put_metric_data(
                Namespace='SageMaker/AsyncEndpoint',
                MetricData=[{
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': unit,
                    'Dimensions': [
                        {'Name': 'FunctionName', 'Value': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')}
                    ]
                }]
            )
    except Exception as e:
        logger.warning(f"Failed to put metric {metric_name}: {e}")


def log_event(event_type: str, data: Dict[str, Any]):
    """
    Log structured event data.
    
    Args:
        event_type: Type of event being logged
        data: Event data to log
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "data": data
    }
    logger.info(json.dumps(log_entry))