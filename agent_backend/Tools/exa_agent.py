from exa_py import Exa
from dotenv import load_dotenv

import os

# Use .env to store your API key or paste it directly into the code
load_dotenv()
exa = Exa(os.getenv('EXA_API_KEY'))

result = exa.stream_answer(
  "What are the latest findings on gut microbiome's influence on mental health?",
  text=True,
)

for chunk in result:
  print(chunk, end='', flush=True)