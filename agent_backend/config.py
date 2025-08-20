from dotenv import load_dotenv
import os

load_dotenv() # Load environment variables from .env file

openrouter_api_key = os.getenv("ROUTER_API_KEY")
database_url = os.getenv("DATABASE_URL")
serper_api_key = os.getenv("SERPER_API_KEY")
exa_key = os.getenv("EXA_API_KEY")
langfuse_Key = os.getenv("Langfuse_API_KEY")
Host = os.getenv("Host")
