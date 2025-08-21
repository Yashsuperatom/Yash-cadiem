from dotenv import load_dotenv
import os

load_dotenv() # Load environment variables from .env file

openrouter_api_key = os.getenv("ROUTER_API_KEY")
database_url = os.getenv("DATABASE_URL")