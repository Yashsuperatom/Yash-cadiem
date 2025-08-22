import requests
import os
from dotenv import load_dotenv

load_dotenv()

class SerperTool:
    name = "Serper Search"
    description = "Searches for keywords on Serper"

    def search(self, query: str):
        """Search Serper.dev for a given query"""
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            raise ValueError("API Key is not set for Serper")

        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        payload = {"q": query}

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise RuntimeError(
                f"Serper API returned {response.status_code}: {response.text}"
            )

        return response.json()

if __name__ == "__main__":
    serper = SerperTool()
    user_query = input("Enter your search query: ")  
    result = serper.search(user_query)               
    print(result)
