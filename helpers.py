async def send_long_message(bot, chat_id, text):
    max_length = 4096
    # Dela upp texten i segment om max_length
    for i in range(0, len(text), max_length):
        await bot.send_message(chat_id, text[i:i+max_length])

def convert_keys_to_str(d):
    if isinstance(d, dict):
        return {str(k): convert_keys_to_str(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [convert_keys_to_str(item) for item in d]
    else:
        return d



