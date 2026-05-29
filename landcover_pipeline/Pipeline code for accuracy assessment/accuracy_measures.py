"""
Accuracy Measures for Multi-class Predictions with Class Mapping

This script computes various accuracy metrics for multi-class classification predictions,
specifically designed to handle cases where multiple input classes map to the same output
band/class. It evaluates predicted class probabilities against true class labels using
a configurable class-to-band mapping.

Key Features:
    - Handles many-to-one class mappings (multiple input classes → single output band)
    - Computes multi-class Brier Score and Brier Skill Score
    - Calculates Jaccard Index (Intersection over Union) for probabilistic predictions
    - Provides per-band performance metrics
    - Identifies and reports unmatched samples (classes not in mapping)
    - Outputs detailed results including reference scores and normalized metrics

Metrics Computed:
    Overall Metrics:
        - Brier Score: Mean squared difference between predicted probabilities and true labels
        - Reference Brier Score: Brier score using mean observed frequency as prediction
        - Maximum Brier Score: Worst-case Brier score (all predictions wrong)
        - Normalized Brier Score: Brier score scaled by maximum possible score
        - Brier Skill Score: Improvement over reference prediction (1=perfect, 0=baseline, <0=worse)
        - Jaccard Index: Overall agreement between predictions and truth
        - Accuracy: Proportion of correct predictions (argmax)

    Per-band Metrics:
        - Per-band Brier Score
        - Per-band Normalized Brier Score
        - Per-band Jaccard Index

Workflow:
    1. Load predictions file (class probabilities across bands)
    2. Load class-to-band mapping file
    3. Extract true class labels from predictions file
    4. Identify and report unmapped samples (classes not in mapping)
    5. Filter to matched samples only
    6. Convert true classes to (possibly multi-hot) encoding using mapping
    7. Compute overall and per-band accuracy metrics
    8. Write detailed results to output file

"""

import pandas as pd
import numpy as np
from landcover_pipeline.quality.utils import convert_column_to_string

# ============================================================================
# Configuration: Input/Output Paths
# ============================================================================

# Pick ONE predictions file (others are commented out):
#predictions_file = '/home/joc/kdrev/Metode/Andre_statistiske_opgaver/AIML4OS/WP7/analysis/data/small_irg_predictions_DK_LUCAS_2022_DK01_EPSG25832.txt'
# predictions_file = '/home/joc/kdrev/Metode/Andre_statistiske_opgaver/AIML4OS/WP7/analysis/data/small_irg_predictions_random_points_nuts2vaerdi=DK01_fid=17_seed=4_coord_class_probs.txt'
# predictions_file = '/home/joc/kdrev/Metode/Andre_statistiske_opgaver/AIML4OS/WP7/analysis/data/small_irg_predictions_LUCAS-Master-Grid_DK01_EPSG25832.txt'

# Pick ONE mapping file (others are commented out):
mapping_file = "./landcover_pipeline/Pipeline code for accuracy assessment/FLAIR_LUCAS_CLASS_MAP.txt"
# mapping_file = '/home/joc/kdrev/Metode/Andre_statistiske_opgaver/AIML4OS/WP7/accuracy assessment/FLAIR_NO_MAP.txt'
# mapping_file = '/home/joc/kdrev/Metode/Andre_statistiske_opgaver/AIML4OS/WP7/accuracy assessment/FLAIR_LUCAS_STRATA_MAP.txt'

# Output file path is derived from predictions file name.
#output_file = predictions_file.replace('.txt', '_accuracy_test.txt')

# Column containing the true class label in the predictions file
true_class_col = "SURVEY_LC1"  
# true_class_col = "real"  
# true_class_col = "STR18" 

# Column names in the mapping file
# NOTE: mapping_band_col values are later compared as STRINGS; ensure the mapping file uses the same convention.
mapping_band_col = "Band"  # Column containing band numbers in mapping file
mapping_class_col = "LUCAS_2022_class"  # Column containing class codes in mapping file
# mapping_class_col = "Class"  # Column containing class codes in mapping file
# mapping_class_col = "LUCAS_2018_stratum"  # Column containing class codes in mapping file

def run_accuracy_measures(predictions_file_input: str):
    #global predictions_file, output_file
    predictions_file = predictions_file_input
    output_file = predictions_file.replace('.txt', '_accuracy_test.txt')

    # ============================================================================
    # Read mapping file (band -> class code mapping)
    # ============================================================================

    print(f"\nRead mapping file:")
    mapping_df = pd.read_csv(mapping_file, delimiter="\t")
    print(f"\nMapping file columns: {mapping_df.columns.tolist()}")
    print(f"Loaded {len(mapping_df)} mapping rows")

    # Convert mapping columns to string so comparisons are consistent
    # (e.g., class codes like 18 vs "18", or band numbers like 1 vs "1")
    mapping_df = convert_column_to_string(mapping_df, mapping_band_col, "Mapping band column")
    mapping_df = convert_column_to_string(mapping_df, mapping_class_col, "Mapping class column")

    # ============================================================================
    # Read predictions file
    # ============================================================================

    print(f"\nRead predictions file:")
    df = pd.read_csv(predictions_file, delimiter="\t")

    # Convert true class column to string to match the mapping format (string comparisons downstream)
    df = convert_column_to_string(df, true_class_col, "True class column")

    # Extract probability columns (these are assumed to be named band_1, band_2, ... etc.)
    band_cols = [col for col in df.columns if col.startswith('band_')]
    n_classes = len(band_cols)

    print(f"\nLoaded {len(df)} predictions with {n_classes} classes:")
    print(f"Band columns: {band_cols}")

    # Convert band columns to numeric (some files may store them as strings)
    df[band_cols] = df[band_cols].apply(pd.to_numeric, errors='coerce')

    # Warn if any probability values could not be converted (become NaN)
    if df[band_cols].isna().any().any():
        print("\nWarning: Some band values could not be converted to numeric and were set to NaN")
        print(f"NaN count per band:\n{df[band_cols].isna().sum()}")

    # ============================================================================
    # Prepare probability matrix (n_samples x n_bands)
    # ============================================================================

    # Extract probabilities into numpy (shape: n_samples x n_classes)
    # NOTE: The script assumes probabilities are stored on a 0-255 scale (e.g., uint8),
    # and converts them to [0,1] by dividing by 255.
    y_probs = df[band_cols].values / 255.0

    # ============================================================================
    # Extract only bands 1-15
    # ============================================================================

    # Extract only bands 1-15 (indices 0-14)
    #
    # IMPORTANT assumption:
    # - The input file contains at least 15 band columns corresponding to band_1..band_15.
    # - If not, indexing here will be wrong or raise errors.
    y_probs_combined = y_probs[:, :15]  # Bands 1-15 (indices 0-14)
    n_classes_combined = y_probs_combined.shape[1]

    print(f"\nExtracted bands 1-15. Number of classes: {n_classes_combined}")

    # ============================================================================
    # Build mapping: band number (string) -> list of class codes (strings)
    # ============================================================================

    band_to_classes = {}
    for _, row in mapping_df.iterrows():
        band_num = row[mapping_band_col]     # band identifier as string
        class_code = row[mapping_class_col]  # class identifier as string

        if band_num not in band_to_classes:
            band_to_classes[band_num] = []
        band_to_classes[band_num].append(class_code)

    print(f"\nCheck unique classes:")
    all_mapped_classes = set()
    for classes_list in band_to_classes.values():
        all_mapped_classes.update(classes_list)

    print(f"\nTotal unique classes in mapping: {len(all_mapped_classes)}")
    print(f"Mapped classes: {sorted(list(all_mapped_classes))}")

    # ============================================================================
    # Extract true class labels, identify unmapped classes, and filter matched samples
    # ============================================================================

    if true_class_col in df.columns:
        y_true = df[true_class_col].values

        # Show what classes exist in the data
        unique_true_classes = set(y_true)
        print(f"\nTotal unique classes in data: {len(unique_true_classes)}")
        print(f"Unique classes (first 20): {sorted(list(unique_true_classes))[:20]}")

        # Classes present in data but missing in mapping (cannot be scored reliably)
        unmapped_classes = unique_true_classes - all_mapped_classes
        print(f"\nClasses in data but not in mapping ({len(unmapped_classes)}):")
        print(sorted(unmapped_classes))

        # Classes in mapping but absent in data (mapping entries unused for this evaluation)
        unused_classes = all_mapped_classes - unique_true_classes
        if unused_classes:
            print(f"\nClasses in mapping but not in data ({len(unused_classes)}):")
            print(sorted(list(unused_classes))[:30])

        # Keep only samples whose true class appears somewhere in the mapping
        mask_matched = np.array([y_true[i] in all_mapped_classes for i in range(len(y_true))])

        print(f"\nFiltering to matched samples only:")
        print(f"  Original samples: {len(y_true)}")
        print(f"  Matched samples: {mask_matched.sum()}")
        print(f"  Unmatched samples: {(~mask_matched).sum()}")

        # Apply mask to both y_true and probabilities
        y_true_matched = y_true[mask_matched]
        y_probs_matched = y_probs_combined[mask_matched]

        # ============================================================================
        # Mapping helper: band index -> band number as string
        # ============================================================================

        def get_band_string(band_idx):
            """
            Convert a band index to its string representation for mapping lookups.

            Returns band indices 0-14 as strings (for bands 1-15).

            IMPORTANT:
            This assumes your mapping file uses these same band identifiers as strings.
            If your mapping file uses 1-indexed band numbers ('1'..'15'), you will need
            to adjust this function accordingly.
            """
            if band_idx < 15:       # indices 0..14 for bands 1-15
                return str(band_idx)
            return None

        # ============================================================================
        # Build "true label" encoding (possibly multi-hot) over combined bands
        # ============================================================================

        # y_true_onehot[i, k] = 1 if the i-th sample's true class maps to combined band k
        # If a class maps to multiple bands, a row can have multiple ones (multi-hot).
        y_true_onehot = np.zeros((len(y_true_matched), n_classes_combined))

        matched_samples = 0
        unmatched_samples = []

        # For each matched sample, find which combined band(s) its class maps to
        for i, true_class in enumerate(y_true_matched):
            matched = False
            for band_idx in range(n_classes_combined):
                band_num = get_band_string(band_idx)

                # If true_class appears in the band, mark this band as "true" for the sample.
                if band_num and band_num in band_to_classes:
                    if true_class in band_to_classes[band_num]:
                        y_true_onehot[i, band_idx] = 1
                        matched = True
                # NOTE: Do NOT break here: a class may legitimately map to multiple bands.

            if matched:
                matched_samples += 1
            else:
                # Even though we filtered "matched classes", a mismatch can still happen if
                # the band indexing convention in get_band_string() does not match mapping bands.
                unmatched_samples.append((i, true_class))

        print(f"\nMatched {matched_samples}/{len(y_true_matched)} samples to bands")
        print(f"One-hot encoding check:")
        print(f"  Samples with 0 bands: {(y_true_onehot.sum(axis=1) == 0).sum()}")
        print(f"  Samples with 1 band: {(y_true_onehot.sum(axis=1) == 1).sum()}")
        print(f"  Samples with 2+ bands: {(y_true_onehot.sum(axis=1) > 1).sum()}")
        print(f"  First 5 rows before normalization:\n{y_true_onehot[:5]}")

        if unmatched_samples:
            print(f"Warning: {len(unmatched_samples)} samples had no matching band")
            print(f"First 5 unmatched: {unmatched_samples[:5]}")

            # Debug helper: show how band indices map to band strings
            print(f"\nDebug: Band index to string mapping:")
            for idx in range(n_classes_combined):
                band_str = get_band_string(idx)
                print(f"  Band index {idx} -> band string '{band_str}'")

        # ============================================================================
        # Normalize multi-hot rows to sum to 1 (so they behave like a distribution)
        # ============================================================================

        # If a class maps to multiple bands, the "true" distribution is split equally among them.
        # Example: if a class maps to 2 bands, each gets 0.5.
        row_sums = y_true_onehot.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1  # avoid division by zero for unmatched rows
        y_true_onehot_normalized = y_true_onehot / row_sums

        # ============================================================================
        # Compute overall Brier score (multi-class)
        # ============================================================================

        # Multi-class Brier: mean over samples of sum_k (p_k - y_k)^2
        brier_score = np.mean(np.sum((y_probs_matched - y_true_onehot_normalized) ** 2, axis=1))

        # Reference prediction uses the observed average frequency per band (climatology baseline)
        reference_probs = np.mean(y_true_onehot_normalized, axis=0)
        reference_pred = np.tile(reference_probs, (len(y_true_matched), 1))
        brier_score_reference = np.mean(np.sum((reference_pred - y_true_onehot_normalized) ** 2, axis=1))

        # Brier Skill Score: improvement over reference baseline
        brier_skill_score = 1 - (brier_score / brier_score_reference) if brier_score_reference > 0 else 0

        # ============================================================================
        # Compute "maximum Brier score" for this dataset under a worst-case prediction
        # ============================================================================

        # For each sample, construct a worst-case prediction:
        # put probability 1 on a band that is NOT among the sample's true band(s).
        worst_case_brier = np.zeros(len(y_true_matched))
        for i in range(len(y_true_matched)):
            true_bands = np.where(y_true_onehot_normalized[i] > 0)[0]

            worst_pred = np.zeros(n_classes_combined)

            # pick the first "wrong" band index not in true_bands
            wrong_idx = None
            for j in range(n_classes_combined):
                if j not in true_bands:
                    wrong_idx = j
                    break

            if wrong_idx is not None:
                worst_pred[wrong_idx] = 1.0

            worst_case_brier[i] = np.sum((worst_pred - y_true_onehot_normalized[i]) ** 2)

        max_brier_score = np.mean(worst_case_brier)

        print(f"\nBrier Score Analysis:")
        print(f"  Actual Brier Score: {brier_score:.6f}")
        print(f"  Reference Brier Score (mean observed frequency per band): {brier_score_reference:.6f}")
        print(f"  Maximum Brier Score: {max_brier_score:.6f}")
        print(f"  Brier Skill Score: {brier_skill_score:.6f}")

        # ============================================================================
        # Per-class Brier score and per-class normalization
        # ============================================================================

        # Mean over samples for each band separately
        per_class_brier = np.mean((y_probs_matched - y_true_onehot_normalized) ** 2, axis=0)

        # Compute per-class maximum Brier score (worst case on samples where that band is true)
        per_class_max_brier = np.zeros(n_classes_combined)
        for band_idx in range(n_classes_combined):
            samples_with_band = y_true_onehot_normalized[:, band_idx] > 0

            if samples_with_band.sum() > 0:
                worst_case_per_class = []
                for i in np.where(samples_with_band)[0]:
                    true_bands = np.where(y_true_onehot_normalized[i] > 0)[0]

                    worst_pred = np.zeros(n_classes_combined)
                    wrong_idx = None
                    for j in range(n_classes_combined):
                        if j not in true_bands:
                            wrong_idx = j
                            break
                    if wrong_idx is not None:
                        worst_pred[wrong_idx] = 1.0

                    worst_case_per_class.append(np.sum((worst_pred - y_true_onehot_normalized[i]) ** 2))

                per_class_max_brier[band_idx] = np.mean(worst_case_per_class) if worst_case_per_class else 2.0
            else:
                # If no sample has this band as true, a default is used
                per_class_max_brier[band_idx] = 2.0

        # Normalize per-band Brier score by per-band max (0=perfect, 1=worst for that band)
        per_class_brier_normalized = per_class_brier / per_class_max_brier

        # ============================================================================
        # Compute accuracy (top-1): argmax band is "correct" if it contains the true class
        # ============================================================================

        # Predicted band index in combined space is argmax over probabilities.
        y_pred_band = np.argmax(y_probs_matched, axis=1)
        correct = 0

        for i, pred_band_idx in enumerate(y_pred_band):
            true_class = y_true_matched[i]
            band_num = get_band_string(pred_band_idx)

            # If the true class is in the predicted band, count as correct
            if band_num and band_num in band_to_classes and true_class in band_to_classes[band_num]:
                correct += 1

        accuracy = correct / len(y_true_matched)

        # ============================================================================
        # Compute "soft" Jaccard Index (IoU) over probabilistic vectors
        # ============================================================================

        # For probabilistic vectors:
        # intersection = sum_k min(p_k, y_k)
        # union        = sum_k max(p_k, y_k)
        intersection = np.sum(np.minimum(y_probs_matched, y_true_onehot_normalized))
        union = np.sum(np.maximum(y_probs_matched, y_true_onehot_normalized))
        jaccard_index = intersection / union if union > 0 else 0

        # Per-class soft Jaccard
        per_class_jaccard = np.zeros(n_classes_combined)
        for band_idx in range(n_classes_combined):
            intersection_class = np.sum(np.minimum(y_probs_matched[:, band_idx], y_true_onehot_normalized[:, band_idx]))
            union_class = np.sum(np.maximum(y_probs_matched[:, band_idx], y_true_onehot_normalized[:, band_idx]))
            per_class_jaccard[band_idx] = intersection_class / union_class if union_class > 0 else 0

        # ============================================================================
        # Write results file
        # ============================================================================

        with open(output_file, 'w') as f:
            f.write(f"Multi-class Brier Score Results (with class mapping)\n")
            f.write(f"====================================================\n\n")
            f.write(f"Predictions file: {predictions_file}\n")
            f.write(f"Mapping file: {mapping_file}\n\n")
            f.write(f"Number of samples (total): {len(df)}\n")
            f.write(f"Number of samples (matched): {len(y_true_matched)}\n")
            f.write(f"Number of classes/bands: {n_classes_combined}\n\n")

            f.write(f"Overall Metrics:\n")
            f.write(f"  Brier Score: {brier_score:.6f}\n")
            f.write(f"  Reference Brier Score (mean observed frequency per band): {brier_score_reference:.6f}\n")
            f.write(f"  Maximum Brier Score: {max_brier_score:.6f}\n")
            f.write(f"  Normalized Brier Score: {brier_score/max_brier_score:.6f} (0=perfect, 1=worst)\n")
            f.write(f"  Brier Skill Score: {brier_skill_score:.6f} (1=perfect, 0=as good as reference, <0=worse than reference)\n")
            f.write(f"  Jaccard Index: {jaccard_index:.6f} (0=no agreement, 1=perfect agreement)\n")
            f.write(f"  Accuracy: {accuracy:.4f}\n\n")

            f.write(f"Per-band Metrics:\n")
            f.write(f"{'Flair class':<15} {'Mapped class(es)':<25} {'Present':<10} {'Brier':<12} {'Norm Brier':<12} {'Jaccard':<12}\n")
            f.write(f"{'':<15} {'':<25} {'in data':<10} {'Score':<12} {'Score':<12} {'Index':<12}\n")
            f.write(f"{'-'*97}\n")

            for i in range(n_classes_combined):
                band_num = str(i)

                # Show up to 3 example class codes for this band
                classes_list = []
                if band_num in band_to_classes:
                    classes_list.extend(band_to_classes[band_num][:3])
                classes_str = ', '.join(classes_list[:3]) + ('...' if len(classes_list) > 3 else '')

                # Check if any class in this band is present in the data
                is_present = 'No'
                if band_num in band_to_classes:
                    for class_code in band_to_classes[band_num]:
                        if class_code in unique_true_classes:
                            is_present = 'Yes'
                            break

                f.write(
                    f"{band_num:<15} {classes_str:<25} {is_present:<10} "
                    f"{per_class_brier[i]:<12.6f} {per_class_brier_normalized[i]:<12.6f} {per_class_jaccard[i]:<12.6f}\n"
                )

            # Record any classes found in data but absent from mapping
            if unmapped_classes:
                f.write(f"\n\nClasses in data but not in mapping ({len(unmapped_classes)}):\n")
                f.write(f"{', '.join(sorted(unmapped_classes))}\n")

        print(f"\nResults written to {output_file}")
        print(f"Overall Brier Score: {brier_score:.6f}")
        print(f"Reference Brier Score: {brier_score_reference:.6f}")
        print(f"Brier Skill Score: {brier_skill_score:.6f}")
        print(f"Maximum Brier Score: {max_brier_score:.6f}")
        print(f"Normalized Brier Score: {brier_score/max_brier_score:.6f}")
        print(f"Overall Jaccard Index: {jaccard_index:.6f}")
        print(f"Accuracy: {accuracy:.4f}")
    else:
        # If the configured true class column doesn't exist in the predictions file, bail out with context
        print(f"Error: Column '{true_class_col}' not found in the data.")
        print(f"Available columns: {df.columns.tolist()}")

    return output_file


if __name__ == "__main__":
    run_accuracy_measures()
