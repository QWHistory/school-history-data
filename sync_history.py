import requests
import base64
import json
import time
import os

# ================= 🛑 配置区 =================
APP_ID = os.environ.get("FEISHU_APP_ID")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN")
TABLE_ID = os.environ.get("FEISHU_TABLE_ID")

GITHUB_PAT = os.environ.get("GH_PAT")
REPO_OWNER = "QWHistory"
REPO_NAME = "school-history-data"
# ============================================

FEISHU_API = "https://open.feishu.cn/open-apis"

def get_feishu_token():
    url = f"{FEISHU_API}/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()
    return res.get("tenant_access_token")

def fetch_approved_records(token):
    url = f"{FEISHU_API}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/search"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "filter": {
            "conjunction": "and",
            "conditions": [
                {"field_name": "审批状态", "operator": "is", "value": ["通过"]}
            ]
        }
    }
    res = requests.post(url, headers=headers, json=payload).json()
    return res.get("data", {}).get("items", [])

def download_file(token, file_token):
    url = f"{FEISHU_API}/drive/v1/medias/{file_token}/download"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return base64.b64encode(res.content).decode('utf-8')
    return None

def get_github_file(file_path):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {"Authorization": f"Bearer {GITHUB_PAT}", "Accept": "application/vnd.github+json"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        data = res.json()
        content = base64.b64decode(data["content"]).decode('utf-8')
        return json.loads(content), data["sha"]
    return [], None

def push_to_github(file_path, base64_content, commit_message, sha=None):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {"Authorization": f"Bearer {GITHUB_PAT}", "Accept": "application/vnd.github+json"}
    payload = {"message": commit_message, "content": base64_content}
    if sha:
        payload["sha"] = sha
    res = requests.put(url, headers=headers, json=payload)
    return res.status_code in [200, 201]

def delete_feishu_record(token, record_id):
    url = f"{FEISHU_API}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/batch_delete"
    headers = {"Authorization": f"Bearer {token}"}
    requests.post(url, headers=headers, json={"records": [record_id]})

def extract_text(val):
    if not val: return ""
    if isinstance(val, str): return val.strip()
    if isinstance(val, list): return "".join([item.get("text", "") for item in val if isinstance(item, dict) and item.get("type") == "text"]).strip()
    if isinstance(val, dict) and val.get("text"): return val.get("text").strip()
    return str(val).strip()

def main():
    print("1. 正在获取飞书 Token...")
    token = get_feishu_token()
    if not token:
        print("❌ Token 获取失败")
        return
        
    print("2. 正在查询待同步的记录...")
    records = fetch_approved_records(token)
    print(f"✅ 找到 {len(records)} 条待同步记录。")

    if not records: return

    existing_data, data_sha = get_github_file("data.json")
    if not isinstance(existing_data, list): existing_data = []

    for record in records:
        record_id = record["record_id"]
        fields = record["fields"]
        
        # --- 处理附件 (加入防覆盖、防爆限制) ---
        attachments = fields.get("附件", [])
        attachment_paths = []
        
        for att in attachments:
            file_token = att["file_token"]
            original_name = att["name"]
            file_size = att.get("size", 0)
            
            # 1. 限制大小 (最大 5MB)
            if file_size > 5 * 1024 * 1024:
                print(f"      ⚠️ 跳过 {original_name}：文件超过 5MB")
                continue
            
            # 2. 限制格式白名单
            ext = original_name.split(".")[-1].lower() if "." in original_name else ""
            if ext not in ["jpg", "jpeg", "png", "gif", "webp", "svg", "pdf", "doc", "docx", "xls", "xlsx", "txt", "md", "zip"]:
                print(f"      ⚠️ 跳过 {original_name}：不支持的格式")
                continue
                
            # 3. 生成绝对不重复的安全文件名 (UID_原名)
            safe_name = f"{record_id}_{original_name}"
            print(f"   -> 正在下载并上传: {safe_name} ...")
            
            b64_data = download_file(token, file_token)
            if b64_data:
                github_path = f"images/{safe_name}"
                success = push_to_github(github_path, b64_data, f"Upload {safe_name}")
                if success:
                    print(f"      ✅ 附件已上传")
                    attachment_paths.append(github_path)

        # --- 处理数据 ---
        data_entry = {
            "id": record_id,
            "attachments": attachment_paths
        }

        for key, value in fields.items():
            if key == "附件": continue
            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict) and "text" in value[0]:
                data_entry[key] = extract_text(value)
            else:
                data_entry[key] = value

        existing_data.append(data_entry)
        delete_feishu_record(token, record_id)

    # --- 更新 data.json ---
    print("3. 正在更新 data.json...")
    existing_data.sort(key=lambda x: x.get("开始时间") or x.get("投稿时间") or 0, reverse=True)
    
    json_str = json.dumps(existing_data, ensure_ascii=False, indent=2)
    json_b64 = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    
    push_to_github("data.json", json_b64, "Update data.json", data_sha)
    print("🎉 全部同步完成！")

if __name__ == "__main__":
    main()
