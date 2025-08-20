import os
from dotenv import load_dotenv
from langfuse_client import get_client
from config import Host,langfuse_Key

load_dotenv()  # load .env variables

SECRET_KEY = os.getenv(langfuse_Key)
HOST = os.getenv("LANGFUSE_HOST", Host)

# Initialize Langfuse client
lf_client = get_client(secret_key=SECRET_KEY, host=HOST)
