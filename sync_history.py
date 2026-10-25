import os
import base64
import json
import requests

# ================= 配置区 (通过 GitHub Actions Secrets 注入) =================
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
FEISHU_APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN")
FEISHU_TABLE_ID = os.environ.get("FEISHU_TABLE_ID")
GITHUB_PAT = os.environ.get("GH_PAT")

REPO_OWNER = "QWHistory"
REPO_NAME = "school-history-data"
FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
# =============================================================================

def get_tenant_access_token():
    """获取飞书 tenant_access_token，有效期 2 小时"""
    endpoint = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
    response = requests.post(endpoint, json={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }).json()
    return response.get("tenant_access_token")

def fetch_approved_records(token):
    """查询审批状态为「通过」的多维表格记录"""
    endpoint = f"{FEISHU_API_BASE}/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records/search"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "filter": {
            "conjunction": "and",
            "conditions": [
                {"field_name": "审批状态", "operator": "is", "value": ["通过"]}
            ]
        }
    }
    response = requests.post(endpoint, headers=headers, json=payload).json()
    return response.get("data", {}).get("items", [])

def download_feishu_file(token, file_token):
    """下载飞书附件，返回 Base64 编码的字符串"""
    endpoint = f"{FEISHU_API_BASE}/drive/v1/medias/{file_token}/download"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        return base64.b64encode(response.content).decode("utf-8")
    return None

def get_github_file(file_path):
    """读取 GitHub 仓库中已有文件的内容及 SHA，用于后续更新"""
    endpoint = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_PAT}",
        "Accept": "application/vnd.github+json"
    }
    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content), data["sha"]
    return [], None

def push_to_github(file_path, base64_content, commit_message, sha=None):
    """向 GitHub 仓库提交文件（创建或更新）"""
    endpoint = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_PAT}",
        "Accept": "application/vnd.github+json"
    }
    payload = {"message": commit_message, "content": base64_content}
    if sha:
        payload["sha"] = sha
    response = requests.put(endpoint, headers=headers, json=payload)
    return response.status_code in [200, 201]

def delete_feishu_record(token, record_id):
    """删除飞书多维表格中的指定记录，保持表格轻量"""
    endpoint = f"{FEISHU_API_BASE}/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_TABLE_ID}/records/batch_delete"
    headers = {"Authorization": f"Bearer {token}"}
    requests.post(endpoint, headers=headers, json={"records": [record_id]})

def extract_plain_text(field_value):
    """将飞书富文本字段（字典列表）转换为纯文本"""
    if not field_value:
        return ""
    if isinstance(field_value, str):
        return field_value.strip()
    if isinstance(field_value, list):
        return "".join(
            item.get("text", "")
            for item in field_value
            if isinstance(item, dict) and item.get("type") == "text"
        ).strip()
    if isinstance(field_value, dict) and field_value.get("text"):
        return field_value["text"].strip()
    return str(field_value).strip()

def main():
    print("[1/3] Fetching Feishu tenant_access_token...")
    token = get_tenant_access_token()
    if not token:
        print("[ERROR] Failed to obtain token. Check FEISHU_APP_ID and FEISHU_APP_SECRET.")
        return

    print("[2/3] Querying approved records...")
    records = fetch_approved_records(token)
    print(f"[OK] Found {len(records)} record(s) to sync.")

    if not records:
        return

    existing_data, data_sha = get_github_file("data.json")
    if not isinstance(existing_data, list):
        existing_data = []

    for record in records:
        record_id = record["record_id"]
        fields = record["fields"]

        # --- 处理附件（限制大小、类型，并使用 UID 前缀防覆盖）---
        attachments = fields.get("附件", [])
        attachment_paths = []

        for att in attachments:
            file_token = att["file_token"]
            original_name = att["name"]
            file_size = att.get("size", 0)

            # 跳过超过 5 MB 的文件
            if file_size > 5 * 1024 * 1024:
                print(f"  [SKIP] {original_name}: exceeds 5 MB limit")
                continue

            # 仅允许白名单内的扩展名
            ext = original_name.split(".")[-1].lower() if "." in original_name else ""
            allowed_exts = {"jpg", "jpeg", "png", "gif", "webp", "svg",
                            "pdf", "doc", "docx", "xls", "xlsx",
                            "txt", "md", "zip"}
            if ext not in allowed_exts:
                print(f"  [SKIP] {original_name}: unsupported file type")
                continue

            # 文件名加入 record_id 前缀，确保全局唯一
            safe_name = f"{record_id}_{original_name}"
            print(f"  [DOWNLOAD] {safe_name} ...")

            b64_data = download_feishu_file(token, file_token)
            if b64_data:
                github_path = f"images/{safe_name}"
                success = push_to_github(github_path, b64_data, f"Upload {safe_name}")
                if success:
                    print(f"  [OK] Uploaded {safe_name}")
                    attachment_paths.append(github_path)
                else:
                    print(f"  [ERROR] Failed to upload {safe_name}")

        # --- 构建数据条目（保持原有字段结构）---
        data_entry = {
            "id": record_id,
            "attachments": attachment_paths
        }

        for key, value in fields.items():
            if key == "附件":
                continue
            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict) and "text" in value[0]:
                data_entry[key] = extract_plain_text(value)
            else:
                data_entry[key] = value

        existing_data.append(data_entry)
        delete_feishu_record(token, record_id)

    # --- 更新 data.json ---
    print("[3/3] Updating data.json on GitHub...")
    existing_data.sort(
        key=lambda x: x.get("开始时间") or x.get("投稿时间") or 0,
        reverse=True
    )

    json_str = json.dumps(existing_data, ensure_ascii=False, indent=2)
    json_b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

    push_to_github("data.json", json_b64, "Update data.json", data_sha)
    print("[DONE] Sync completed successfully.")

if __name__ == "__main__":
    main()
