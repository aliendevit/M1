# path: scripts/init_db.py
import os
from backend.db.repo import Repo

def main():
    os.makedirs("data", exist_ok=True)
    Repo().close()
    print("Initialized data/chart.sqlite from backend/db/schema.sql")

if __name__ == "__main__":
    main()
