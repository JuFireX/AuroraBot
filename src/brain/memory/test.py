import json
import os
import requests
from dotenv import load_dotenv

from src.brain.memory import UnifiedMemoryManager


def test_deepseek_direct_api(prompt_context: str, current_query: str) -> None:
    """直接使用 requests 测试 DeepSeek API 的连通性，并喂入完整的记忆上下文"""
    print("=== 开始直接测试 DeepSeek API 并喂入提示词 ===\n")
    
    # 确保加载 .env
    load_dotenv()
    
    api_key = os.getenv("MEM0_LLM_API_KEY")
    base_url = os.getenv("MEM0_LLM_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("MEM0_LLM_MODEL", "deepseek-chat")

    if not api_key:
        print("错误: 未在 .env 中找到 MEM0_LLM_API_KEY")
        return

    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # 构建一个完整的请求体，让大模型基于上下文回答问题
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个贴心的私人助理。请严格根据用户提供的【上下文】来回答用户的问题。如果上下文中没有信息，你可以结合常识回答。"},
            {"role": "user", "content": prompt_context + f"\n\n请根据上面的背景信息回答：{current_query}"}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }

    print("正在发送请求给 DeepSeek，请稍候...\n")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status() 
        
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        
        print("✅ DeepSeek 基于记忆的回答:")
        print(f"🤖 Assistant:\n{reply}")
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ API 请求失败，状态码: {response.status_code}")
        print(f"错误详情: {response.text}")
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
        
    print("\n==========================================\n")


def main() -> None:
    # 1. 初始化统一记忆管理器
    memory_manager = UnifiedMemoryManager()
    user_id = "test_user_001"

    print("=== 开始模拟对话并写入记忆 ===\n")

    # 模拟第 1 轮对话
    msg2 = "zzk是个萝莉控"
    print(f"User: {msg2}")
    memory_manager.process_interaction(content=msg2, role="user", user_id=user_id)
    memory_manager.process_interaction(content="没问题，zzk是萝莉控已记录。", role="assistant", user_id=user_id)

    print("\n=== 记忆写入完成，开始模拟 Agent 检索上下文 ===\n")

    # 模拟 Agent 在回答新问题前，向系统索要上下文
    current_query = "zzk喜欢什么类型的女生"
    print(f"当前用户新问题: {current_query}")
    
    # 2. 一键提取包含三级缓存的综合上下文
    context = memory_manager.retrieve_context(current_query=current_query, user_id=user_id)
    prompt_text = context.to_prompt_text()

    # 3. 打印最终生成给大模型的 Prompt 文本
    print("\n---------------- 最终提取出的 Prompt 如下 ----------------\n")
    print(prompt_text)
    print("\n----------------------------------------------------------\n")

    # 4. 把整理好的上下文 Prompt 喂给 DeepSeek 看它的反应
    test_deepseek_direct_api(prompt_text, current_query)


if __name__ == "__main__":
    main()