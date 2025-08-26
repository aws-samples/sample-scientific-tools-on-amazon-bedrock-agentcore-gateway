# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import os

import numpy as np
import torch
from matplotlib import pyplot as plt
from transformers import AutoModel, AutoTokenizer

logging.basicConfig(level=logging.INFO)


def identify_outliers_percentile(heatmap, low_percentile=1, high_percentile=99):
    """Identify outliers using percentile thresholds"""
    flat_values = heatmap.flatten()
    low_threshold = np.percentile(flat_values, low_percentile)
    print(f"Low threshold: {low_threshold}")
    high_threshold = np.percentile(flat_values, high_percentile)
    print(f"High threshold: {high_threshold}")

    high_outliers = []
    low_outliers = []
    print(f"Heatmap shape is {heatmap.shape}")
    for i in range(heatmap.shape[0]):
        for j in range(heatmap.shape[1]):
            value = heatmap[i, j]
            if value >= high_threshold:
                high_outliers.append((i, j, value))
            elif value <= low_threshold:
                low_outliers.append((i, j, value))
    combined_outliers = low_outliers + high_outliers
    return sorted(combined_outliers, key=lambda x: x[2])


def model_fn(model_dir):
    """
    This function loads the AMPLIFY model and tokenizer.
    The model is moved to the GPU to support Flash Attention.
    """
    logging.info("[custom] model_fn: Starting the model loading process...")

    try:
        model_id = os.getenv("AMPLIFY_MODEL_ID", "chandar-lab/AMPLIFY_350M")
        logging.info(f"[custom] model_fn: Model id is {model_id}")

        model = AutoModel.from_pretrained(model_id, trust_remote_code=True)
        logging.info(f"[custom] model_fn: Successfully loaded the model: {model}")

        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        logging.info(
            f"[custom] model_fn: Successfully loaded the tokenizer: {tokenizer}"
        )

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        logging.info(f"[custom] model_fn: Moved model to {device} device")

        return model, tokenizer, device

    except Exception as e:
        logging.error(
            f"[custom] model_fn: Error occurred while loading the model and tokenizer: {str(e)}",
            exc_info=True,
        )
        raise e


def input_fn(request_body, content_type="application/json"):
    """
    Pre-processes the input data. Assumes the input is JSON.
    The input should contain a protein sequence.
    """
    logging.info("input_fn: Received input")
    if content_type == "application/json":
        input_data = json.loads(request_body)
        sequence = input_data["sequence"]
        return sequence
    else:
        raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, model_artifacts):
    """
    Tokenizes the input protein sequence and runs inference on the model.
    The model is already loaded on the GPU for inference.
    Adapted from https://huggingface.co/blog/AmelieSchreiber/mutation-scoring#log-likelihood-ratios-and-point-mutations
    """
    import time

    start_time = time.time()

    logging.info("predict_vep_fn: Running inference")
    model, tokenizer, device = model_artifacts
    sequence_length = len(input_data)
    logging.info(input_data)
    logging.info(f"Sequence length is {sequence_length}")

    # Log GPU memory if available
    if torch.cuda.is_available():
        logging.info(
            f"GPU memory before inference: {torch.cuda.memory_allocated()/1024**2:.1f}MB"
        )

    input_ids = tokenizer.encode(input_data, return_tensors="pt")
    logging.info(f"Encoded sequence shape is {input_ids.shape}")

    input_ids = input_ids.to(device)

    # Define standard AAs
    amino_acids = list("ACDEFGHIKLMNPQRSTVWY")
    amino_acid_mapping = {
        "A": "Ala",  # Alanine
        "C": "Cys",  # Cysteine
        "D": "Asp",  # Aspartic acid
        "E": "Glu",  # Glutamic acid
        "F": "Phe",  # Phenylalanine
        "G": "Gly",  # Glycine
        "H": "His",  # Histidine
        "I": "Ile",  # Isoleucine
        "K": "Lys",  # Lysine
        "L": "Leu",  # Leucine
        "M": "Met",  # Methionine
        "N": "Asn",  # Asparagine
        "P": "Pro",  # Proline
        "Q": "Gln",  # Glutamine
        "R": "Arg",  # Arginine
        "S": "Ser",  # Serine
        "T": "Thr",  # Threonine
        "V": "Val",  # Valine
        "W": "Trp",  # Tryptophan
        "Y": "Tyr",  # Tyrosine
    }

    amino_acid_3 = [
        "Ala",
        "Cys",
        "Asp",
        "Glu",
        "Phe",
        "Gly",
        "His",
        "Ile",
        "Lys",
        "Leu",
        "Met",
        "Asn",
        "Pro",
        "Gln",
        "Arg",
        "Ser",
        "Thr",
        "Val",
        "Trp",
        "Tyr",
    ]

    # Initialize heatmap
    heatmap = np.zeros((20, sequence_length))
    masked_input_ids = input_ids.clone()
    logging.info("Beginning analysis")

    # Process positions with progress logging
    for position in range(1, sequence_length + 1):
        # Log progress every 50 positions to avoid log spam
        if position % 50 == 0 or position == 1:
            elapsed = time.time() - start_time
            logging.info(
                f"Processing position {position}/{sequence_length} (elapsed: {elapsed:.1f}s)"
            )

        # Mask the target position
        masked_input_ids[0, position] = tokenizer.mask_token_id

        # Get logits for the masked token
        with torch.no_grad():
            logits = model(masked_input_ids).logits

        # Calculate log probabilities
        probabilities = torch.nn.functional.softmax(logits[0, position], dim=0)
        log_probabilities = torch.log(probabilities)

        # Get the log probability of the wild-type residue
        wt_residue = input_ids[0, position].item()
        log_prob_wt = log_probabilities[wt_residue].item()

        # Calculate LLR for each variant
        for i, amino_acid in enumerate(amino_acids):
            log_prob_mt = log_probabilities[
                tokenizer.convert_tokens_to_ids(amino_acid)
            ].item()
            heatmap[i, position - 1] = log_prob_mt - log_prob_wt

        # Clear cache periodically to prevent memory buildup
        if position % 100 == 0:
            torch.cuda.empty_cache()

    outliers = identify_outliers_percentile(heatmap)
    hgvs_outliers = []

    for outlier in outliers:
        aa_end = amino_acid_3[outlier[0]]
        pos = outlier[1]
        score = outlier[2]
        aa_start = amino_acid_mapping[input_data[pos]]
        hgvs_outliers.append((aa_start + str(pos) + aa_end + " " + str(score)))

    total_time = time.time() - start_time
    logging.info(f"Inference completed in {total_time:.1f} seconds")

    return (heatmap, hgvs_outliers)


def output_fn(prediction, accept="application/json"):
    """
    Post-processes the output, returning the model's predictions.
    Converts the output to a JSON-serializable format.
    """
    logging.info("output_fn: Formatting output")
    if accept == "application/json":
        return (
            json.dumps({"heatmap": prediction[0].tolist(), "outliers": prediction[1]}),
            accept,
        )
    else:
        raise ValueError(f"Unsupported accept type: {accept}")