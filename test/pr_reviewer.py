import os
import sys
import json
import requests

def main():
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_number = os.environ.get("PR_NUMBER")
    gh_token = os.environ.get("GITHUB_TOKEN")

    if not all([repo, pr_number, gh_token]):
        print("Missing required environment variables.")
        sys.exit(1)

    # 1. Fetch the Pull Request Diff from GitHub
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    diff_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    diff_resp = requests.get(diff_url, headers=headers)
    diff_resp.raise_for_status()
    diff_text = diff_resp.text

    # 2. Define your mandatory checklist
    checklist = """
    1. Are there unit tests for the new logic?
    2. Is the README.md updated if any core functionality changed?
    3. Are there zero hardcoded secrets or credentials?
    4. Is the code free of debugging print() statements?
    """
    
    prompt = f"""
    You are a strict but helpful expert code reviewer. Review the following code diff against this checklist:
    {checklist}

    PR Diff:
    {diff_text}

    Respond in strictly valid JSON format with exactly two keys:
    - "passed": boolean (true if ALL checklist items are satisfied by this diff, false otherwise)
    - "comment": string (Detailed markdown-formatted feedback explaining what passed, what failed, and why)
    """

    # 3. Analyze the diff with GitHub Models API (gpt-4o-mini)
    ai_url = "https://models.inference.ai.azure.com/chat/completions"
    ai_headers = {
        "Authorization": f"Bearer {gh_token}",
        "Content-Type": "application/json"
    }
    ai_data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a code reviewer that outputs ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    ai_resp = requests.post(ai_url, headers=ai_headers, json=ai_data)
    if not ai_resp.ok:
        print(f"Failed to get AI review: {ai_resp.text}")
        sys.exit(1)

    try:
        content = ai_resp.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
    except (KeyError, json.JSONDecodeError):
        print("Failed to parse AI response as JSON.")
        sys.exit(1)

    passed = result.get("passed", False)
    comment = result.get("comment", "No feedback provided.")

    # 4. Post the review as a comment on the PR
    comment_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    post_headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json"
    }
    
    status_icon = "✅" if passed else "❌"
    final_comment = f"### AI PR Review {status_icon}\n\n{comment}"
    requests.post(comment_url, headers=post_headers, json={"body": final_comment})

    # 5. Reject the PR if it fails the checklist
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()