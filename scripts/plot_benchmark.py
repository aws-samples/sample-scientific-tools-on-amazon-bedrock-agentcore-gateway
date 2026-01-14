#!/usr/bin/env python3

"""
Plot benchmark results from the SageMaker Lambda benchmark.

This script reads the CSV output from benchmark.py and creates a dot plot
showing the relationship between sequence length and processing time.
"""

import pandas as pd
import matplotlib.pyplot as plt
import argparse
import sys
from pathlib import Path


def plot_benchmark_results(csv_file: str, output_file: str = None):
    """
    Plot benchmark results as a dot plot.
    
    Args:
        csv_file: Path to the CSV file with benchmark results
        output_file: Optional output file for the plot (PNG format)
    """
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file)
        
        # Filter only completed tests
        completed_df = df[df['status'] == 'completed'].copy()
        
        if completed_df.empty:
            print("❌ No completed tests found in the CSV file")
            return
        
        # Convert total_time from seconds to minutes
        completed_df['total_time_minutes'] = completed_df['total_time'] / 60
        
        # Create the plot
        plt.figure(figsize=(10, 6))
        
        # Create dot plot
        plt.scatter(completed_df['sequence_length'], completed_df['total_time_minutes'], 
                   color='blue', s=60, alpha=0.7, edgecolors='darkblue', linewidth=1)
        
        # Customize the plot
        plt.xlabel('Sequence Length (amino acids)', fontsize=12)
        plt.ylabel('Total Time (minutes)', fontsize=12)
        plt.title('SageMaker Lambda Performance: Processing Time vs Sequence Length', fontsize=14, pad=20)
        plt.grid(True, alpha=0.3)
        
        # Format x-axis to show comma-separated numbers
        ax = plt.gca()
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
        
        # Add some styling
        plt.tight_layout()
        
        # Add trend line if we have enough points
        if len(completed_df) > 2:
            z = np.polyfit(completed_df['sequence_length'], completed_df['total_time_minutes'], 1)
            p = np.poly1d(z)
            plt.plot(completed_df['sequence_length'], p(completed_df['sequence_length']), 
                    "r--", alpha=0.8, linewidth=2, label=f'Trend line (slope: {z[0]:.4f} min/aa)')
            plt.legend()
        
        # Show some statistics on the plot
        max_time = completed_df['total_time_minutes'].max()
        max_length = completed_df['sequence_length'].max()
        
        stats_text = f"Max time: {max_time:.1f} min\nMax length: {max_length:,} aa\nCompleted tests: {len(completed_df)}"
        plt.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # Save or show the plot
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"📊 Plot saved to: {output_file}")
        else:
            plt.show()
        
        # Print summary statistics
        print("\n📈 Benchmark Summary:")
        print(f"   Completed tests: {len(completed_df)}")
        print(f"   Sequence length range: {completed_df['sequence_length'].min():,} - {completed_df['sequence_length'].max():,} amino acids")
        print(f"   Processing time range: {completed_df['total_time_minutes'].min():.1f} - {completed_df['total_time_minutes'].max():.1f} minutes")
        print(f"   Average processing time: {completed_df['total_time_minutes'].mean():.1f} minutes")
        
        if len(completed_df) > 1:
            # Calculate scaling characteristics
            time_per_aa = completed_df['total_time_minutes'] / completed_df['sequence_length']
            print(f"   Time per amino acid: {time_per_aa.mean():.6f} ± {time_per_aa.std():.6f} minutes/aa")
        
    except FileNotFoundError:
        print(f"❌ CSV file not found: {csv_file}")
        print("💡 Make sure you've run the benchmark script first")
    except Exception as e:
        print(f"❌ Error plotting results: {e}")


def find_latest_benchmark_csv():
    """Find the most recent benchmark CSV file in the current directory."""
    csv_files = list(Path('.').glob('benchmark_*.csv'))
    if not csv_files:
        return None
    
    # Sort by modification time and return the most recent
    return str(sorted(csv_files, key=lambda x: x.stat().st_mtime)[-1])


def main():
    parser = argparse.ArgumentParser(
        description="Plot SageMaker Lambda benchmark results",
        epilog="""
Examples:
  %(prog)s                                    # Use latest benchmark CSV
  %(prog)s benchmark_20250828_151203.csv     # Use specific CSV file
  %(prog)s --output benchmark_plot.png       # Save plot to file
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        'csv_file', 
        nargs='?', 
        help='CSV file with benchmark results (default: latest benchmark_*.csv)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output file for the plot (PNG format)'
    )
    
    args = parser.parse_args()
    
    # Determine which CSV file to use
    if args.csv_file:
        csv_file = args.csv_file
    else:
        csv_file = find_latest_benchmark_csv()
        if not csv_file:
            print("❌ No benchmark CSV files found in current directory")
            print("💡 Run the benchmark script first or specify a CSV file")
            return 1
        print(f"📊 Using latest benchmark file: {csv_file}")
    
    # Check if file exists
    if not Path(csv_file).exists():
        print(f"❌ File not found: {csv_file}")
        return 1
    
    # Create the plot
    plot_benchmark_results(csv_file, args.output)
    
    return 0


if __name__ == "__main__":
    import numpy as np  # Import here to avoid dependency issues if not installed
    sys.exit(main())