from dotenv import load_dotenv
load_dotenv()
from services.groq_client import chat_with_tools

question = "Is Rahul present today?"
answer = chat_with_tools(question)
print("\nQuestion:", question)
print("Answer:", answer)