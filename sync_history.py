import requests
import base64
import json
import time
import os

APP_ID = os.environ.get("FEISHU_APP_ID")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN")
TABLE_ID = os.environ.get("FEISHU_TABLE_ID")
GITHUB_PAT = os.environ.get("GH_PAT")

REPO_OWNER = "QWHistory"                  
REPO_NAME = "school-history-data"  

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

def download_file(token, file_token, filename):
    url = f"{FEISHU_API}/drive/v1/medias/{file_token}/download"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return base64.b64encode(res.content).decode('utf-8')
    return None

def get_github_file(file_path):
    """获取 GitHub 上已有的文件内容，用于合并数据"""
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

def extract_text(field_value):
    """飞书富文本提取纯文本的辅助函数"""
    if isinstance(field_value, list):
        return "".join([item.get("text", "") for item in field_value if isinstance(item, dict) and item.get("type") == "text"])
    elif isinstance(field_value, str):
        return field_value
    return ""

def main():
    print("1. 正在获取飞书 Token...")
    token = get_feishu_token()
    
    print("2. 正在查询待同步的记录...")
    records = fetch_approved_records(token)
    print(f"✅ 找到 {len(records)} 条待同步记录。")

    if not records:
        return

    # 拉取现有的 data.json，准备合并
    existing_data, data_sha = get_github_file("data.json")
    if not isinstance(existing_data, list):
        existing_data = []

    for record in records:
        record_id = record["record_id"]
        fields = record["fields"]
        
        # --- 处理附件 ---
        attachments = fields.get("附件", [])
        attachment_paths = []
        for att in attachments:
            file_token = att["file_token"]
            filename = att["name"]
            print(f"   -> 正在下载并上传附件: {filename} ...")
            
            b64_data = download_file(token, file_token, filename)
            if b64_data:
                github_path = f"images/{filename}"
                success = push_to_github(github_path, b64_data, f"Upload {filename} from Feishu")
                if success:
                    print(f"      ✅ 附件已上传至 GitHub")
                    attachment_paths.append(github_path)

               # --- 处理数据并合并 (动态提取所有列) ---
        print(f"   -> 正在处理数据...")
        
        # 先放几个基础的核心字段（保持和之前兼容）
        data_entry = {
            "id": record_id,
            "attachments": attachment_paths
        }

        # 动态遍历飞书返回的所有字段（这就是完整数据了！）
        for key, value in fields.items():
            if key == "附件":
                continue # 附件已经处理过了
                
            # 如果发现是富文本格式，自动提取纯文本
            if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict) and "text" in value[0]:
                data_entry[key] = extract_text(value)
            else:
                # 如果是数字、时间戳、纯文本等，直接原样保留
                data_entry[key] = value

        existing_data.append(data_entry)

        # --- 清理飞书 ---
        print(f"   -> 正在从飞书清理该记录...")
        delete_feishu_record(token, record_id)

    # --- 统一推送 data.json ---
    print("3. 正在更新 GitHub 上的 data.json...")
    # 按照时间倒序排列（最新的在最前）
    existing_data.sort(key=lambda x: x.get("time", 0), reverse=True)
    
    json_str = json.dumps(existing_data, ensure_ascii=False, indent=2)
    json_b64 = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    
    push_to_github("data.json", json_b64, "Update data.json with new approved records", data_sha)
    print("🎉 全部同步完成！")

if __name__ == "__main__":
    main()
