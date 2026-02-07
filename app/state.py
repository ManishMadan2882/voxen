import json
from pathlib import Path

from dotenv import load_dotenv

from app.llm import LLMClient, LLMConfig

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"

knowledge = json.loads((DATA_DIR / "knowledge.json").read_text())
orders = json.loads((DATA_DIR / "orders.json").read_text())

sessions = {}
llm_client = LLMClient(LLMConfig.from_env())
