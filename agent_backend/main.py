from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Routes import routes  # your existing routes
from agno.playground import Playground
from Agent.Global_Agent import web_agent, judge_agent  # your agents

app = FastAPI()

# CORS setup to allow Next.js frontend
origins = [
    "http://localhost:3000",  # Next.js dev server
    "http://127.0.0.1:3000",  # sometimes used
    # Add production URLs here when deploying
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include your existing API routes
app.include_router(routes.router)

# Create agno playground app
playground_app = Playground(agents=[web_agent, judge_agent])
agno_app = playground_app.get_app()

# Mount playground at a specific path, e.g., /playground
app.mount("/playground", agno_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
