import os, time
from fastapi import FastAPI
from strands import Agent
from langchain_openai import ChatOpenAI
from prometheus_client import Counter, start_http_server
import boto3

# Prometheus metric (tokens processed per second proxy via count)
TOKENS = Counter("tokens_processed_total", "Total tokens processed")
app = FastAPI()

# Optional: DynamoDB-backed memory (simple example)
TABLE = os.getenv("AGENT_MEMORY_TABLE", "StrandAgentMemory")
REGION = os.getenv("AWS_REGION", "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE)

def memory_backend(key, val=None):
    if val is None:
        resp = table.get_item(Key={"id": key})
        return resp.get("Item", {}).get("state")
    table.put_item(Item={"id": key, "state": val})

agent = Agent(
    llm=ChatOpenAI(model="gpt-4o"),
    tools=[],
    memory_backend=memory_backend,
)

@app.on_event("startup")
def _metrics():
    # Expose Prometheus metrics on a side port for scraping (e.g., 9091)
    start_http_server(9091)

@app.post("/query")
async def query(payload: dict):
    t0 = time.time()
    result = await agent.run(payload["message"])
    # crude token estimate; replace with your tokenizer/LLM usage accounting
    tokens = max(1, len(result.split()) // 3)
    TOKENS.inc(tokens)
    return {"response": result, "latency_ms": int((time.time() - t0) * 1000)}