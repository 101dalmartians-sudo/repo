import json
import os
import urllib.request
import urllib.error

ORG = "aspireacademy"
REPO = "repo"
PRIVATE = False


def get_auth_token():
    for key in ["GITHUB_TOKEN", "GH_TOKEN", "GITHUB_API_TOKEN"]:
        token = os.environ.get(key)
        if token:
            return token
    raise RuntimeError(
        "No GitHub token found. Set GITHUB_TOKEN, GH_TOKEN, or GITHUB_API_TOKEN."
    )


def create_repo():
    token = get_auth_token().strip()
    url = f"https://api.github.com/orgs/{ORG}/repos"
    payload = {
        "name": REPO,
        "private": PRIVATE,
        "description": "Aspire Academy Django portal",
        "auto_init": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.load(resp)
            print("Repository created:", result.get("html_url"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        print("GitHub API error:", exc.code, exc.reason)
        print(body)
        raise


if __name__ == "__main__":
    create_repo()
