import requests
import pandas as pd
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def requests_session_with_retry(total_retries=3, backoff=0.3, status_forcelist=(429,500,502,503,504)):
    session = requests.Session()
    retries = Retry(total=total_retries, backoff_factor=backoff, status_forcelist=status_forcelist, raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def get_token_safe(base, client_id, client_secret):
    session = requests_session_with_retry()
    url = f"{base}/oauth2/token"
    resp = session.post(url, data={"client_id": client_id, "client_secret": client_secret}, timeout=20)
    if resp.status_code != 200:
        raise Exception(f"Token error {resp.status_code}: {resp.text}")
    data = resp.json()
    token = data.get("access_token") or data.get("accessToken")  # fallback
    if not token:
        raise Exception(f"Token not present in response: {data}")
    return token

def get_all_device_ids(base, token, max_ids=2000):
    session = requests_session_with_retry()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base}/devices/queries/devices/v1"
    resp = session.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Devices IDs error {resp.status_code}: {resp.text}")
    ids = resp.json().get("resources", [])
    if not ids:
        return []
    # limit to max_ids for safe handling
    return ids[:max_ids]

def get_device_details(base, token, ids_list):
    session = requests_session_with_retry()
    headers = {"Authorization": f"Bearer {token}"}
    results = []
    chunk_size = 400
    for i in range(0, len(ids_list), chunk_size):
        chunk = ids_list[i:i+chunk_size]
        ids_param = ",".join(chunk)
        url = f"{base}/devices/entities/devices/v2?ids={ids_param}"
        resp = session.get(url, headers=headers, timeout=60)
        if resp.status_code != 200:
            raise Exception(f"Devices details error {resp.status_code}: {resp.text}")
        resources = resp.json().get("resources", [])
        results.extend(resources)
    df = pd.json_normalize(results)
    return df
