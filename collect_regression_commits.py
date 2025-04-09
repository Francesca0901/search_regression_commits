import csv
import re
import os
import requests
import time

# Get GitHub token from environment
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("Please set the GITHUB_TOKEN environment variable")

# Borrowed from Minecraft project
bug0_keywords = [
    "fixed ", " bug", "fixes ", "fix ", " fix", " fixed", " fixes", "crash", "solves", " resolves",
    "resolves ", " issue", "issue ", "regression", "fall back", "assertion", "coverity", "reproducible",
    "stack-wanted", "steps-wanted", "testcase", "failur", "fail", "npe ", " npe", "except", "broken",
    "differential testing", "error", "hang ", " hang", "test fix", "steps to reproduce", "crash",
    "assertion", "failure", "leak", "stack trace", "heap overflow", "freez", "problem ", " problem",
    " overflow", "overflow ", "avoid ", " avoid", "workaround ", " workaround", "break ", " break",
    " stop", "stop "
]

bug1_keywords = [
    "introduced by", "regression by", "caused by", "regressed by"
]

def parse_repo_full_name(repo_name: str) -> str:
    """
    Nothing to do so far.
    """
    return repo_name

def get_commits(repo: str, page: int = 1, per_page: int = 100):
    """
    Fetch commits from a repo's default branch.
    """
    url = f"https://api.github.com/repos/{repo}/commits"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    params = {
        "per_page": per_page,
        "page": page
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 403:
        print("[WAIT] Rate limit hit, waiting for 60 seconds...")
        time.sleep(60)
        return get_commits(repo, page, per_page)
    elif response.status_code == 401:
        print("[SKIP] 401 Unauthorized: Check your GitHub token!")
        print(f"Response: {response.text}")
        return []
    elif response.status_code == 404:
        print(f"[SKIP] 404 Not Found: Repository {repo} does not exist or is private.")
        print(f"Response: {response.text}")
        return []
    response.raise_for_status()
    return response.json()

def get_commit_message(repo: str, commit_sha: str) -> str:
    """
    Fetch commit message for a given commit hash from the GitHub API.
    Returns an empty string if the commit is invalid or not found.
    """
    # Quick sanity check for commit hash length, in case it's obviously invalid
    if len(commit_sha) < 7:
        # Often short SHAs won't match the full commit in remote
        # If your data includes shorter SHAs, remove or adjust this check
        print(f"[SKIP] Commit hash '{commit_sha}' seems invalid.")
        return ""

    url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        print(f"[SKIP] Commit {commit_sha} not found in {repo}")
        return ""
    elif response.status_code == 403:
        print("[WAIT] Rate limit hit, waiting for 60 seconds...")
        time.sleep(60)
        return get_commit_message(repo, commit_sha)
    elif response.status_code == 401:
        print("[SKIP] 401 Unauthorized: Check your GitHub token!")
        print(f"Response: {response.text}")
        return ""
    elif response.status_code == 422:
        print(f"[SKIP] 422 Unprocessable Entity: {repo} might be empty or a redirect.")
        print(f"Response: {response.text}")
        return ""
    response.raise_for_status()
    return response.json().get("commit", {}).get("message", "") or ""

def commit_contains_bug0(commit_msg: str) -> bool:
    """ 
    Check if the mentioned BIC for bug1 is a bug fix commit.
    """
    lower_msg = commit_msg.lower()
    return any(keyword in lower_msg for keyword in bug0_keywords)

# def collect_regression_chain(repo: str, max_commits=200):
#     """
#     Search for commits that match bug1_keywords. 
#     Extract from the commit message the bug-introducing commit, 
#     fetch that commit message, and see if it has bug0_keywords.
#     """
#     found_count = 0
#     page = 1

#     while found_count < max_commits:
#         commits = get_commits(repo, page=page, per_page=100)
#         if not commits:
#             break

#         for commit_obj in commits:
#             msg = commit_obj["commit"]["message"].lower()
#             if any(k in msg for k in bug1_keywords):
#                 match = re.search(
#                     r"(?:regression by|regressed by|introduced by|caused by)\s*([a-f0-9]+)",
#                     msg, re.IGNORECASE
#                 )
#                 if match:
#                     bug_commit_hash = match.group(1)
#                     bug_msg = get_commit_message(repo, bug_commit_hash)
#                     # I should save commit message to a file here, but forgot to do so in the first run, so I will do another function just to collect messges
#                     if bug_msg and commit_contains_bug0(bug_msg):
#                         found_count += 1
#                         print(f"[FOUND] {repo}: Regression commit {commit_obj['sha']} references to FIX commit {bug_commit_hash}")
#                         with open("regression_commits3.csv", "a", newline="", encoding="utf-8") as csvfile:
#                             writer = csv.writer(csvfile)
#                             writer.writerow([repo, commit_obj["sha"], bug_commit_hash])
#                         if found_count >= max_commits:
#                             break
#         page += 1


# from regression_commits_all.csv, find the regression chain
def collect_regression_chain(path: str, max_commits=200):
    with open(path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        # Skip the CSV header row
        next(reader, None)

        for row in reader:
            if not row:
                continue
            project_name = row[0].strip()
            repo = parse_repo_full_name(project_name)
            if not repo:
                continue
            print(f"\n[INFO] Collecting {repo} regression chain...")
            bfc_commit_sha = row[1].strip()
            bic_commit_sha = row[2].strip()
            commit_msg = get_commit_message(repo, bic_commit_sha)
            if commit_msg and commit_contains_bug0(commit_msg):
                with open("regression_chain.csv", "a", newline="", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([repo, bic_commit_sha, commit_msg, bfc_commit_sha])

def collect_all_regression(repo: str, max_commits=500) -> int:
    """
    Search for commits that match bug1_keywords. 
    Extract from the commit message the bug-introducing commit.
    This is for calculating the percentage of regression commits that reference a bug fix commit.
    """
    found_count = 0
    page = 1

    while found_count < max_commits:
        commits = get_commits(repo, page=page, per_page=100)
        if not commits:
            break

        for commit_obj in commits:
            msg = commit_obj["commit"]["message"].lower()
            if any(k in msg for k in bug1_keywords):
                match = re.search(
                    r"(?:regression by|regressed by|introduced by|caused by)\s*([a-f0-9]+)",
                    msg, re.IGNORECASE
                )
                if match:
                    bug_commit_hash = match.group(1)
                    bug_msg = get_commit_message(repo, bug_commit_hash)
                    if bug_msg:
                        found_count+=1
                        print(f"[FOUND] {repo}: Regression commit {commit_obj['sha']} references to commit {bug_commit_hash}")
                        with open("regression_commits_all_3.csv", "a", newline="", encoding="utf-8") as csvfile:
                            writer = csv.writer(csvfile)
                            writer.writerow([repo, commit_obj["sha"], bug_commit_hash])
                        if found_count >= max_commits:
                            break
        page += 1

    return found_count

def collect_commit_message(csv_path: str):
    """
    Fetch commit message for all the regression in regression_commits_all.csv
    """
    with open(csv_path, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        # Skip the CSV header row
        next(reader, None)

        for row in reader:
            if not row:
                continue
            project_name = row[0].strip()
            repo = parse_repo_full_name(project_name)
            if not repo:
                continue
            print(f"\n[INFO] Collecting {repo} commit message...")
            bfc_commit_sha = row[1].strip()
            bic_commit_sha = row[2].strip()
            commit_msg = get_commit_message(repo, bic_commit_sha)
            if commit_msg:
                with open("commit_messages.csv", "a", newline="", encoding="utf-8") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([repo, bic_commit_sha, commit_msg, bfc_commit_sha])

def main(project_path: str):
    with open(project_path, "r", newline="", encoding="utf-8") as projectsfile:
        reader = csv.reader(projectsfile)
        # Skip the CSV header row
        next(reader, None)

        # all_regression_count = 0

        for row in reader:
            if not row:
                continue
            project_name = row[0].strip()
            repo = parse_repo_full_name(project_name)
            if not repo:
                continue
            print(f"\n[INFO] Processing {repo} ...")
            collect_all_regression(repo)
        
        # based on the collected regression commits, find regression chains
        collect_regression_chain(repo)

if __name__ == "__main__":
    PROJECT_PATH = "filtered_projects3.csv" 
    main(PROJECT_PATH)
