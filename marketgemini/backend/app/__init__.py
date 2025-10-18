from pathlib import Path
from dotenv import load_dotenv

# project root: .../marketgemini/.env  (app/ is two levels down from root)
ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV, override=True)
