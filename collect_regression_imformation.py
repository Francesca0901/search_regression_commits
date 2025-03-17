# input: filtered_regression_commits.csv
# output: regression_information.csv

import csv
import os
import requests
import time

GITHUB_API_URL = "https://api.github.com"
# Get GitHub token from environment
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("Please set the GITHUB_TOKEN environment variable")

def fetch_commit_files(repo_name: str, commit_sha: str):
    url = f"{GITHUB_API_URL}/repos/{repo_name}/commits/{commit_sha}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    while True:  # Loop to retry in case of rate limits
        resp = requests.get(url, headers=headers)
        
        if resp.status_code == 404:
            print(f"[SKIP] Commit {commit_sha} not found in {repo_name}")
            return []
        elif resp.status_code == 403:
            print("[WAIT] Rate limit exceeded. Waiting for 60 seconds...")
            time.sleep(60)  # Wait 60 seconds before retrying
            continue
        
        resp.raise_for_status()
        return resp.json().get("files", [])
    
def collect_regression_information():
    with open("filtered_regression_commits.csv", "r", newline="") as infile:
        reader = csv.DictReader(infile)
        with open("regression_information.csv", "w", newline="") as outfile:
            writer = csv.writer(outfile)
            writer.writerow(["repo", "regression_commit_sha", "bug_commit_sha", "bug_file_paths", "bug_file_changes"])
            
            for row in reader:
                repo = row["repo"]
                regression_commit_sha = row["regression_commit_sha"]
                bug_commit_sha = row["bug_commit_sha"]
                
                bug_files = fetch_commit_files(repo, bug_commit_sha)
                bug_file_paths = [file["filename"] for file in bug_files]
                bug_file_changes = sum(file["changes"] for file in bug_files)
                
                writer.writerow([repo, regression_commit_sha, bug_commit_sha, bug_file_paths, bug_file_changes])
                print(f"[INFO] Fetched bug files for {repo}: {bug_file_paths}")