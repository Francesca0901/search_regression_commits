"""
This script aims at collecting C projects on github with more than 1000 stars and filtering them by commit count.
output: filtered_projects.csv
"""

import requests
import csv
import time
import pandas as pd
import os

GITHUB_API_URL = "https://api.github.com"
# Get GitHub token from environment
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("Please set the GITHUB_TOKEN environment variable")

""" 
Search GitHub for C projects with 1000+ stars.
However, because we can only get 1000 results at a time,
I am going to use upperbound to gradually fetch the projects.
"""
def search_c_projects():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    params = {
        "q": "stars:<1381 language:C",
        "sort": "stars",
        "order": "desc",
        "per_page": 50
    }
    
    projects = []
    page = 1

    while len(projects) < 1000:  # Limit to 1000 projects
        print(f"Fetching page {page}...")
        response = requests.get(f"{GITHUB_API_URL}/search/repositories", headers=headers, params={**params, "page": page})
        if response.status_code == 403:
            print("Rate limit exceeded. Try again later.")
            break
        elif response.status_code == 422:
            print(response.json())
            break
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            break
        for repo in items:
            projects.append({
                "name": repo["full_name"],
                "stars": repo["stargazers_count"],
                "commits_url": repo["commits_url"].split("{")[0]
            })
        page += 1
        time.sleep(1)

    return projects

def get_commit_count(repo_full_name, attempt=1, max_attempts=5):
    """
    Retrieves commit count for a repo via /stats/contributors endpoint.
    Try up to max_attempts times if a 202 status indicates stats are still being generated.
    202 -> the repository is too large and GitHub is still processing stats
    403 -> rate limit or permission issue
    """
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    url = f"{GITHUB_API_URL}/repos/{repo_full_name}/stats/contributors"

    response = requests.get(url, headers=headers)

    if response.status_code == 202:
        # GitHub is still generating contributor stats
        print(f"[WAIT] GitHub is processing stats for {repo_full_name}, attempt #{attempt}")
        time.sleep(20)

        if attempt < max_attempts:
            return get_commit_count(repo_full_name, attempt + 1, max_attempts)
        else:
            print(f"[SKIP] Stats not ready after {max_attempts} attempts for {repo_full_name}. Skipping.")
            return None

    if response.status_code == 403:
        print(f"[SKIP] Skipping {repo_full_name} due to rate limits or permission.")
        return None

    response.raise_for_status()
    contributors = response.json()

    if not contributors:
        print(f"[WARNING] No commit data for {repo_full_name}")
        return None

    total_commits = sum(contributor["total"] for contributor in contributors)
    return total_commits


def collect_projects():
    projects = search_c_projects()
    
    with open("projects3.csv", "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["name", "stars", "commits"])

        for project in projects:
            commit_count = get_commit_count(project["name"])
            if commit_count:
                writer.writerow([project["name"], project["stars"], commit_count])
                print(f"Saved {project['name']} with {commit_count} commits.")

def filter_projects():
    df = pd.read_csv("projects3.csv")

    median_commits = df["commits"].median()
    print(f"Median commits: {median_commits}")

    # Apply filtering: Keep projects with commit count in [500, 25000]
    filtered_df = df[(df["commits"] >= 500) & (df["commits"] < 25000)]
    filtered_df.to_csv("filtered_projects3.csv", index=False)
    print(f"Filtered dataset saved as 'filtered_projects3.csv'")

if __name__ == "__main__":
    # Fetch projects and commit counts
    # collect_projects()
    # Filter by commit count
    filter_projects()
