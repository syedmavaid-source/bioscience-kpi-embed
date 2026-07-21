import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

WORKSPACE_ID = "2605787000000006705"
ORG_ID = "786385719"


def _creds():
    return {
        "client_id": os.environ["ZOHO_CLIENT_ID"],
        "client_secret": os.environ["ZOHO_CLIENT_SECRET"],
        "refresh_token": os.environ["ZOHO_REFRESH_TOKEN"],
    }


def access_token():
    cfg = _creds()
    params = {
        "grant_type": "refresh_token",
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "refresh_token": cfg["refresh_token"],
    }
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request("https://accounts.zoho.com/oauth/v2/token", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())["access_token"]


def _get(url, token):
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Zoho-oauthtoken {token}")
    req.add_header("ZANALYTICS-ORGID", ORG_ID)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def export_view(view_id, token):
    """Export a view's data, sync first, falling back to async bulk export."""
    base = "https://analyticsapi.zoho.com/restapi/v2"
    params = urllib.parse.urlencode({"CONFIG": json.dumps({"responseFormat": "json"})})
    try:
        result = _get(f"{base}/workspaces/{WORKSPACE_ID}/views/{view_id}/data?{params}", token)
        return result.get("data")
    except urllib.error.HTTPError:
        pass
    start = _get(f"{base}/bulk/workspaces/{WORKSPACE_ID}/views/{view_id}/data?{params}", token)
    job_id = start["data"]["jobId"]
    download_url = None
    for _ in range(60):
        status = _get(f"{base}/bulk/workspaces/{WORKSPACE_ID}/exportjobs/{job_id}", token)
        code = status["data"]["jobStatus"]
        if code == "JOB COMPLETED":
            download_url = status["data"]["downloadUrl"]
            break
        if code == "JOB FAILED":
            raise RuntimeError(f"Export job failed: {status}")
        time.sleep(1)
    if not download_url:
        raise TimeoutError("Export job did not complete in time")
    result = _get(download_url, token)
    data = result.get("data")
    return data.get("rows") if isinstance(data, dict) else data
