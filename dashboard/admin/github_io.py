"""
GitHub Contents API helper.
==========================
Commits a file to a GitHub repo via the Contents API, authenticated with a
fine-grained Personal Access Token.

Used by the Streamlit admin form to commit manual_inputs.csv back to the
repo. The cron workflow then picks up the new CSV on the next run and
recomputes the Engine A score.

Usage:
    from github_io import commit_file_to_repo
    success, err = commit_file_to_repo(
        content="...",
        repo_path="data/core/manual_inputs.csv",
        commit_msg="Manual inputs: 2 field updates",
        token=st.secrets["GH_PAT"],
        owner="abhiarjun231-netizen",
        repo="Engine-A-Dashboard-v2",
    )

The PAT must have Contents: write permission on the target repo.
"""
import base64

import requests


GITHUB_API = "https://api.github.com"
USER_AGENT = "engine-a-dashboard/1.0"
HTTP_TIMEOUT = 20


def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }


def get_file_sha(repo_path, token, owner, repo, branch="main"):
    """
    Return (sha, error). sha is None if file doesn't exist yet (that's not an error).
    Error is only returned for actual API failures.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{repo_path}"
    try:
        r = requests.get(
            url, headers=_headers(token),
            params={"ref": branch}, timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as e:
        return None, f"Network error on GET: {e}"

    if r.status_code == 200:
        try:
            return r.json().get("sha"), None
        except ValueError:
            return None, "GitHub returned 200 but non-JSON body"
    if r.status_code == 404:
        return None, None     # file doesn't exist yet — fine, we'll create it
    if r.status_code == 401:
        return None, "401 Unauthorized — PAT is invalid or expired"
    if r.status_code == 403:
        return None, "403 Forbidden — PAT lacks Contents:write on this repo"
    return None, f"GET {r.status_code}: {r.text[:200]}"


def commit_file_to_repo(content, repo_path, commit_msg, token, owner, repo, branch="main"):
    """
    Create or update a file in a GitHub repo via Contents API.
    
    Returns (success: bool, error_message: str or None).
    On success: error_message is None.
    On failure: success is False, error_message has the GitHub API response.
    """
    if not token:
        return False, "No GH_PAT provided (Streamlit secret missing)"
    if not content:
        return False, "Empty content — refusing to commit"

    # Step 1: get existing SHA (None if first time)
    sha, err = get_file_sha(repo_path, token, owner, repo, branch)
    if err:
        return False, err

    # Step 2: build payload
    payload = {
        "message": commit_msg,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    # Step 3: PUT
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{repo_path}"
    try:
        r = requests.put(
            url, headers=_headers(token),
            json=payload, timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as e:
        return False, f"Network error on PUT: {e}"

    if r.status_code in (200, 201):
        return True, None
    if r.status_code == 401:
        return False, "401 Unauthorized — PAT invalid or expired"
    if r.status_code == 403:
        return False, "403 Forbidden — PAT lacks Contents:write"
    if r.status_code == 409:
        return False, "409 Conflict — SHA mismatch (someone else committed first); retry"
    if r.status_code == 422:
        return False, f"422 Validation error: {r.text[:300]}"
    return False, f"PUT {r.status_code}: {r.text[:300]}"
