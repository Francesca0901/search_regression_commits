# filter out commits which BIC and BFC both contain change of C files, and changed lines(+ and -) are less than 100.
# input: regression_commits.csv file 
# oputput: filtered_regression_commits.csv file

import csv
import os
import time 
import requests

# Get GitHub token from environment
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("Please set the GITHUB_TOKEN environment variable")

def fetch_commit_files(repo_full_name: str, commit_sha: str):
    """
    Fetch details for a single commit from GitHub, returning its 'files' list.
    Each file item typically has {filename, additions, deletions, changes, patch, ...}.
    """
    url = f"https://api.github.com/repos/{repo_full_name}/commits/{commit_sha}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    while True:  # Loop to retry in case of rate limits
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 404:
            print(f"[SKIP] Commit {commit_sha} not found in {repo_full_name}")
            return []
        elif resp.status_code == 403:
            print("[WAIT] Rate limit exceeded. Waiting for 60 seconds...")
            time.sleep(60)  # Wait 60 seconds before retrying
            continue  # Retry request
        
        resp.raise_for_status()
        return resp.json().get("files", [])

def filter_commits(repo: str, BIC_sha: str, BFC_sha: str):
    if not BIC_sha or not BFC_sha:
        print(f"[SKIP] {repo}: Missing BIC or BFC SHA.")
        return

    # Check if BIC contains any C files
    BIC_files = fetch_commit_files(repo, BIC_sha)
    BIC_file_paths = [file["filename"] for file in BIC_files]
    BIC_file_paths = [path for path in BIC_file_paths if path.endswith(".c")]
    if not BIC_file_paths:
        print(f"[SKIP] {repo}: BIC {BIC_sha} does not contain any C files.")
        return
    
    # Check if BFC contains any C files
    BFC_files = fetch_commit_files(repo, BFC_sha)
    BFC_file_paths = [file["filename"] for file in BFC_files]
    BFC_file_paths = [path for path in BFC_file_paths if path.endswith(".c")]
    if not BFC_file_paths:
        print(f"[SKIP] {repo}: BFC {BFC_sha} does not contain any C files.")
        return
    
    # Check if BIC contains less than 100 lines of changes(+ and -)
    BIC_changes = sum(file["changes"] for file in BIC_files)
    if BIC_changes > 100:
        print(f"[SKIP] {repo}: BIC {BIC_sha} has more than 100 lines of changes.")
        return
    
    # Check if BFC contains less than 100 lines of changes(+ and -)
    BFC_changes = sum(file["changes"] for file in BFC_files)
    if BFC_changes > 100:
        print(f"[SKIP] {repo}: BFC {BFC_sha} has more than 100 lines of changes.")
        return
    
    output_file = "filtered_regression_commits.csv"
    
    # Ensure output CSV has a header if empty
    if not os.path.exists(output_file) or os.stat(output_file).st_size == 0:
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["repo", "BIC_sha", "BFC_sha"])  # Add CSV Header

    with open(output_file, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([repo, BIC_sha, BFC_sha])

def main(csv_path: str):
    with open(csv_path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)

        for row in reader:
            if not row:
                continue
            project_name = row[0].strip()
            repo = project_name
            BIC_sha = row[1]
            BFC_sha = row[2]
            print(f"\n[INFO] Processing {repo} ...")
            filter_commits(repo, BIC_sha, BFC_sha)

if __name__ == "__main__":
    main("regression_commits.csv")
