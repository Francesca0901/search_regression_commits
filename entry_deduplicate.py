# I want to write a script to deduplicate the entries in the csv file.

import pandas as pd

def deduplicate_csv(input_file, output_file):
    """
    Read a CSV file and remove duplicate entries based on the first column."
    """
    # Read the CSV file into a DataFrame
    df = pd.read_csv(input_file, header=None)

    # Remove duplicates based on the first column
    df_deduplicated = df.drop_duplicates(subset=[1,2])

    # Write the deduplicated DataFrame
    df_deduplicated.to_csv(output_file, index=False, header=False)
    print(f"Deduplicated CSV saved as {output_file}")

if __name__ == "__main__":
    # Specify the input and output file paths
    input_file = "regression_chains.csv"
    output_file = "regression_chains_de.csv"

    # Call the deduplication function
    deduplicate_csv(input_file, output_file)
    