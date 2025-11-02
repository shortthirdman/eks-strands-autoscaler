import os, json, time
import boto3
from strands import Agent
from langchain_openai import ChatOpenAI

QUEUE_URL = os.environ["SQS_QUEUE_URL"]
REGION = os.getenv("AWS_REGION", "us-east-1")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "10"))
sqs = boto3.client("sqs", region_name=REGION)

agent = Agent(
    llm=ChatOpenAI(model="gpt-4o"),
    tools=[],
)

def handle_message(body: dict):
    # do long-running work, write to S3/Dynamo, etc.
    prompt = body.get("prompt", "Say hello")
    return agent.run(prompt)

if __name__ == "__main__":
    while True:
        resp = sqs.receive_message(
            QueueUrl=QUEUE_URL, MaxNumberOfMessages=5, WaitTimeSeconds=10
        )
        for m in resp.get("Messages", []):
            try:
                out = handle_message(json.loads(m["Body"]))
                print("RESULT:", out)
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=m["ReceiptHandle"])
            except Exception as e:
                print("ERR:", e)
        time.sleep(POLL_SECONDS)