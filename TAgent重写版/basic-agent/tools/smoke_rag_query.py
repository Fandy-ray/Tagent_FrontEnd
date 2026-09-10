import requests
import json

# 测试 API
url = "http://127.0.0.1:5000/rag/query"
data = {
    "user_question": "什么是系统教学仿真？"
}

print("发送请求...")
response = requests.post(url, json=data)

if response.status_code == 200:
    result = response.json()
    print("\n=== 返回结果 ===")
    print(f"状态码: {result['code']}")
    print(f"消息: {result['msg']}")
    print(f"\n问题: {result['data']['user_question']}")
    print(f"\n回答: {result['data']['final_answer']}")
    print(f"\n步骤日志:")
    for log in result['data']['step_log']:
        print(f"  - {log}")
    print(f"\n检索到的上下文: {result['data']['retrieved_context']}")
else:
    print(f"请求失败: {response.status_code}")
    print(response.text)