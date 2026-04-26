class Config:
    # DeepSeek API 配置（可替换为其他模型）
    deepseek_api_key: str = "sk-你的API密钥"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # 群聊配置
    ai_group_whitelist: list = []  # 空列表表示所有群都响应
    ai_at_only: bool = True  # True=只在被@时回复，False=响应所有消息

    class Config:
        extra = "ignore"
