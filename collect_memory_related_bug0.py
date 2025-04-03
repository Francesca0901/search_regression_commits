"""
This script aims at filtering out which bic are aiming at fixing memory related bugs.
So far we considering bug types as follows:
- Null pointer dereference
- Out of bound write
- Out of bound read
- Use after free
- Memory leak
- Double free
- Devide by zero
"""

import csv
import re
import os
import requests
import time

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("Please set the GITHUB_TOKEN environment variable")

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

########################################################################
# - Use r"heap(?:\W+\w+){0,5}\W+overflow" to limit how far apart the words can be. Here we set 5.
########################################################################
memory_bug_patterns = {
    "Null pointer dereference": [
        r"\bnull[- ]pointer[- ]dereference\b",
        r"\bnull(?:\W+\w+){0,5}\W*(?:pointer|dereference|ptr)\b",
        r"\b(?:pointer|dereference|ptr)(?:\W+\w+){0,5}\W*null\b",
        r"\bsegfault\b(?:\W+\w+){0,10}\bnull\b",
        r"\bnil(?:\W+\w+){0,3}\W*pointer\b",
        r"\bSIGSEGV\b",
    ],
    "Overflow": [
        # Out-of-bound write patterns
        r"buffer[- ]overflow",
        r"\b(?:global|stack|heap|buffer|stack|heap)(?:\W+\w+){0,5}\W+overflow\b",
        r"\b(?:invalid|illegal)(?:\W+\w+){0,5}\W+write",
        r"\b(?:buffer|array|memory)(?:\W+\w+){0,5}\W+overrun\b",
        r"\binvalid(?:\W+\w+){0,5}\W+address\b",
        r"\bexceed(?:s|ing)?(?:\W+\w+){0,5}\W+allocated(?:\W+\w+){0,5}\W+memory\b",
        r"\boverflow(?:\W+\w+){0,5}\W+in(?:\W+\w+){0,5}\W+write",
        r"\bindex(?:\W+\w+){0,5}\W+-\d+\b",
        # Out-of-bound read patterns
        r"\b(?:invalid|illegal)(?:\W+\w+){0,5}\W+(?:read|access)",
        r"\baccess(?:\W+\w+){0,5}\W+violation(?:\W+\w+){0,5}\W+reading\b",
        r"\buninitialized(?:\W+\w+){0,5}\W+memory(?:\W+\w+)\b",
        r"\b(?:stack|heap)(?:\W+\w+){0,5}\W+corruption\b",
        r"\binvalid(?:\W+\w+){0,5}\W+free",
        # Other overflow patterns
        # "To make sure the valid buffer be accessed only.""
        r"\b(?:as|en|in)?sure(?:\W+\w+){0,5}\W+(?:valid|legal)(?:\W+\w+){0,5}\W+(?:access|read|write)"
    ],
    "Integer overflow/wraparound": [
        r"integer[- ]overflow",
        r"integer[- ]underflow",
        r"\barithmetic(?:\W+\w+){0,5}\W+error\b",
        r"\bwrap(?:\W+\w+){0,5}\W+around\b",
        r"\binteger(?:\W+\w+){0,5}\W+overflow\b",
        r"\binteger(?:\W+\w+){0,5}\W+underflow\b",
    ],
    "Use after free": [
        r"use[- ]after[- ]free", 
        r"\bUAF\b",
        r"\b(?:access|use|dereference)(?:\W+\w+){0,5}\W+(?:freed|deleted|released)(?:\W+\w+){0,5}\W+memory\b",
        r"\b(?:pointer|ptr)(?:\W+\w+){0,5}\W+to(?:\W+\w+){0,5}\W+freed(?:\W+\w+){0,5}\W+object",
        r"\bdangling(?:\W+\w+){0,5}\W+pointer\b", 
        r"\bdangling(?:\W+\w+){0,5}\W+reference\b"
    ],
    "Memory leak": [
        r"memory[- ]leak",
        r"\b(?:memory|resource)(?:\W+\w+){0,5}\W+leak(?:s|ed)?\b",
        # Direct leak of 7 byte(s) in 1 object(s) allocated from:
        r"\bdirect(?:\W+\w+){0,5}\W+leak(?:s|ed)?\b",
        r"\ballocated(?:\W+\w+){0,5}\W+memory(?:\W+\w+){0,5}\W+not(?:\W+\w+){0,5}\W+freed\b",
        r"\b(?:unreleased|unfreed)(?:\W+\w+){0,5}\W+(?:memory|blocks)\b",
        r"\bleak(?:s|ed)?(?:\W+\w+){0,5}\W+\d+(?:\W+\w+){0,5}\W+bytes\b",
        r"\bno(?:\W+\w+){0,5}\W+free(?:\W+\w+){0,5}\W+for(?:\W+\w+){0,5}\W+alloc",
    ],
    "Double free": [
        r"\bdouble[- ]free\b",
        r"\bmultiple(?:\W+\w+){0,5}\W+free\b",
        r"\bfree(?:\W+\w+){0,5}\W+non-allocated(?:\W+\w+){0,5}\W+memory\b",
        # r"\bdouble(?:\W+\w+){0,5}\W+free\b",
        r"\bcorrupted(?:\W+\w+){0,5}\W+double-linked(?:\W+\w+){0,5}\W+list\b",
    ],
    "Divide by zero": [
        r"\bdivide[d]?(?:\W+\w+){0,5}\W+by(?:\W+\w+){0,5}\W+(?:zero|0)\b",
        r"\bdivision(?:\W+\w+){0,5}\W+by(?:\W+\w+){0,5}\W+(?:zero|0)\b",
        r"\bmodulo(?:\W+\w+){0,5}\W+by(?:\W+\w+){0,5}\W+zero\b",
    ],
    # In order to catch all memory related vulnerability, also consider sanitizer report as an indicator
    "AddressSanitizer report": [
        r"\baddresssanitizer\b",
        r"\basan:\s",
        r"==\d+==.*addresssanitizer",
        r"\bubsan\b",
        r"\btsan\b",
    ],
    "Generic Memory Errors": [
        r"\binvalid(?:\W+\w+){0,5}\W+(?:memory(?:\W+\w+){0,5})?access\b",
        r"\baccess(?:\W+\w+){0,5}\W+violation\b"
    ],
}

def match_memory_bug_type(text: str):
    """
    Return matched bug types from a commit message or bug report content.

    Each 'bug_type' might have multiple possible regex patterns.
    """
    matched = []
    lower_text = text.lower()
    for bug_type, patterns in memory_bug_patterns.items():
        for pattern in patterns:
            # re.IGNORECASE might overlap with text.lower() but it's fine
            if re.search(pattern, lower_text, flags=re.IGNORECASE):
                matched.append(bug_type)
                # Avoid labeling the same bug_type multiple times, but different types can be labeled on the same commit
                break 
    return matched

def fetch_commit_message(repo: str, sha: str) -> str:
    """
    Fetch the commit message for a given (repo, commit SHA).
    """
    url = f"https://api.github.com/repos/{repo}/commits/{sha}"
    response = requests.get(url, headers=HEADERS)
    while response.status_code == 403:  # Rate limit
        print("[WAIT] Rate limit hit. Sleeping for 60s...")
        time.sleep(60)
        response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"[ERROR] Could not fetch commit {sha} from {repo}")
        return ""
    return response.json().get("commit", {}).get("message", "") or ""

# def fetch_linked_issue_content(commit_msg: str, repo: str) -> str:
#     """
#     Try to find the FIRST GitHub issue or pull request link in the commit message
#     and fetch its content. If your messages often link multiple issues,
#     you can extend this to parse all.
#     """
#     issue_match = re.search(r"https://github.com/([\w\-_]+)/([\w\-_]+)/(issues|pull)/(\d+)", commit_msg)
#     if not issue_match:
#         return ""

#     # The link might reference a different repo than 'repo', so we need to fetch it separately
#     gh_user_or_org, gh_repo_name, issue_type, number = issue_match.groups()
#     repo_full = f"{gh_user_or_org}/{gh_repo_name}"
#     url = f"https://api.github.com/repos/{repo_full}/{issue_type}/{number}"
    
#     response = requests.get(url, headers=HEADERS)
#     while response.status_code == 403:  # Rate limit
#         print("[WAIT] Rate limit hit. Sleeping for 60s...")
#         time.sleep(60)
#         response = requests.get(url, headers=HEADERS)
#     if response.status_code != 200:
#         print(f"[WARN] Couldn't fetch linked {issue_type} #{number} from {repo_full}")
#         return ""
    
#     print(f"[INFO] Fetched linked {issue_type} #{number} from {repo_full}") # Debug
#     return response.json().get("body", "") or ""

def fetch_issue_content(repo: str, issue_number: str) -> str:
    """
    Fetch the title and body of a GitHub issue (or PR) from the same or a specified repo.
    Return the combined title + body string.
    """
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    response = requests.get(url, headers=HEADERS)
    while response.status_code == 403:  # Rate limit
        print("[WAIT] Rate limit hit. Sleeping for 60s...")
        time.sleep(60)
        response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"[WARN] Could not fetch issue/PR #{issue_number} from {repo}")
        return ""

    data = response.json()
    issue_title = data.get("title") or ""
    issue_body = data.get("body") or ""
    
    combined_issue_text = issue_title + "\n" + issue_body
    return combined_issue_text


def fetch_linked_issue_content(commit_msg: str, repo: str) -> str:
    """
    1) Try to find the FIRST GitHub issue or PR link in the commit message
       matching https://github.com/<owner>/<repo>/(issues|pull)/<number>
       and return its content.
    2) If no direct link is found, look for references of the form:
         fix #123, fixes #123, close #123, closes #123, etc.
       in the same repo, and fetch that issue content.
    """
    # 1) Check for direct GitHub issue/PR link
    issue_match = re.search(
        r"https://github\.com/([\w\-_]+)/([\w\-_]+)/(issues|pull)/(\d+)", 
        commit_msg, 
        flags=re.IGNORECASE
    )
    if issue_match:
        gh_user_or_org, gh_repo_name, issue_type, number = issue_match.groups()
        repo_full = f"{gh_user_or_org}/{gh_repo_name}"
        print(f"[INFO] Fetched linked {issue_type} #{number} from {repo_full}")
        return fetch_issue_content(repo_full, number)
    
    # 2) If no direct link, try references like "fix #123" or "closes #123" for the SAME repo
    #    We'll capture variations: fix, fixes, fixed, close, closes, closed, resolve, resolves, resolved
    issue_reference_match = re.search(
        r"(?:fix(?:ed|es)?|close(?:d|s)?|resolve(?:d|s)?)\s*#(\d+)",
        commit_msg, 
        flags=re.IGNORECASE
    )
    if issue_reference_match:
        number = issue_reference_match.group(1)
        # print(f"[INFO] Found commit message referencing issue #{number} in {repo}")
        return fetch_issue_content(repo, number)
    
    # If nothing is found, return empty
    return ""

def collect_memory_related_regression(csv_path: str, output_path: str):
    """
    `regresion_commit_all.csv` is in the format:
        repo, BFC_sha, BIC_sha
    For each row:
      1) Fetch BIC commit message
      2) Attempt to fetch linked issue text
      3) Match memory bug types
      4) If matched, write to `output_path`
         Format: [repo, BIC_sha, bug_types]
    """
    with open(csv_path, "r", newline="", encoding="utf-8") as infile, \
         open(output_path, "w", newline="", encoding="utf-8") as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        writer.writerow(["repo", "BIC_sha", "bug_types"])

        next(reader, None)  # regresion_commit_all.csv contains first row, so skip it
        for row in reader:
            if len(row) < 3:
                continue
            repo, _, bic_sha = row
            print(f"[INFO] Checking {repo} BIC: {bic_sha}")
            
            commit_msg = fetch_commit_message(repo, bic_sha)
            if not commit_msg:
                continue 

            # Check linked bug content in commit message
            linked_bug_text = fetch_linked_issue_content(commit_msg, repo)
            # if linked_bug_text:
            #     print(f"  -> Linked issue text: {linked_bug_text[:50]}...")  # Debug

            # Combine commit message + linked issue text
            combined_text = commit_msg + "\n" + linked_bug_text

            # Identify bug types
            bug_types = match_memory_bug_type(combined_text)
            if bug_types:
                # Save to CSV
                writer.writerow([
                    repo,
                    bic_sha,
                    "; ".join(bug_types)
                ])
                print(f"  -> Matched memory bug(s): {bug_types}")

if __name__ == "__main__":
    collect_memory_related_regression(
        csv_path="regression_commits_all_3.csv",
        output_path="memory_related_bugs_3.csv"
    )