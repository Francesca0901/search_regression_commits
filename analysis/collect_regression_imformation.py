"""
This script aims at collecting lifecycle information for regression commits.
input: regression_commits_filtered.csv
output: regression_information.csv
"""

import csv
import datetime
import os
import requests
import time
from datetime import datetime

GITHUB_API_URL = "https://api.github.com"
# Get GitHub token from environment
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("Please set the GITHUB_TOKEN environment variable")

"""
Fetch commit metadata from GitHub.
Return a tuple: (commit data dict, files list)
commit_data_dict includes keys like:
{
    "sha": "xxxx",
    "commit": {
        "author": {
            "name": "...",
            "email": "...",
            "date": "2023-01-01T12:34:56Z"
        },
        ...
    },
    ...
}
"""
def fetch_commit_details(repo_name: str, commit_sha: str):
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
        data = resp.json()
        commit_files = data.get("files", [])
        return data, commit_files
    
"""
Collect regression lifecycle.
"""
def collect_regression_information():
    with open("regression_commits_tail.csv", "r", newline="") as infile, \
         open("regression_information.csv", "a", newline="", encoding="utf-8") as outfile:
        
        reader = csv.DictReader(infile)
        fieldnames = [
            "repo", 
            "fix_period",
            "BIC_sha", 
            "BIC_time", 
            "BIC_files_count", 
            "BIC_file_changes", 
            "BFC_sha", 
            "BFC_time", 
            "BFC_files_count",
            "BFC_file_changes",
            "LOC"
        ]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            repo = row["repo"]
            BIC_sha = row["BIC_sha"]
            BFC_sha = row["BFC_sha"]
            fix_period = 0
            BIC_time_str = 0
            BIC_files_count = 0
            BIC_file_changes = 0
            BFC_time_str = 0
            BFC_files_count = 0
            BFC_file_changes = 0
            LOC = 0

            # Fetch BIC details
            BIC_data, BIC_files = fetch_commit_details(repo, BIC_sha)
            BIC_time_str = BIC_data["commit"]["author"]["date"]
            BIC_files_count = len(BIC_files)
            BIC_file_changes = sum(file["changes"] for file in BIC_files)
            # Fetch LOC
            LOC = fetch_repo_LOC(repo)

            # Fetch BFC details
            BFC_data, BFC_files = fetch_commit_details(repo, BFC_sha)
            BFC_time_str = BFC_data["commit"]["author"]["date"]
            BFC_files_count = len(BFC_files)
            BFC_file_changes = sum(file["changes"] for file in BFC_files)
            

            try:
                bic_datetime = datetime.fromisoformat(BIC_time_str.replace("Z",""))
                bfc_datetime = datetime.fromisoformat(BFC_time_str.replace("Z",""))
                fix_period = (bfc_datetime - bic_datetime).days
            except ValueError: # Invalid date
                pass

            writer.writerow({
                "repo": repo,
                "fix_period": fix_period,
                "BIC_sha": BIC_sha,
                "BIC_time": BIC_time_str,
                "BIC_files_count": BIC_files_count,
                "BIC_file_changes": BIC_file_changes,
                "BFC_sha": BFC_sha,
                "BFC_time": BFC_time_str,
                "BFC_files_count": BFC_files_count,
                "BFC_file_changes": BFC_file_changes,
                "LOC": LOC
            })


def fetch_repo_LOC(repo_name: str):
    url = f"{GITHUB_API_URL}/repos/{repo_name}/languages"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    while True:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 403:
            print("[WAIT] Rate limit exceeded. Waiting for 60 seconds...")
            time.sleep(60)
            continue
        resp.raise_for_status()
        data = resp.json()
        return data.get("C", 0)

if __name__ == "__main__":
    collect_regression_information()
