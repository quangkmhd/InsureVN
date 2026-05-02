import os
from langchain.chat_models import init_chat_model

# Fake an ollama init
try:
    llm = init_chat_model("ollama:gemma4:31b-cloud", base_url="http://test.com")
    print("Success:", type(llm))
except Exception as e:
    print("Error:", e)
