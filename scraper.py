import requests
from bs4 import BeautifulSoup
import os
import time
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import subprocess
import threading

# ---- Parametry ----
BASE_URL = "https://jbzd.com.pl/oczekujace/"
THREADS = 5  # liczba równoległych wątków

START = int(sys.argv[1])
END = int(sys.argv[2])

# folder output z timestampem
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
OUTPUT_DIR = f"images_run_{timestamp}"
os.makedirs(OUTPUT_DIR, exist_ok=True)
DUPLICATES_FILE = os.path.join(OUTPUT_DIR, "duplikaty.json")

headers = {"User-Agent": "Mozilla/5.0 (compatible; Bot/1.0)"}
duplicates = {}
progress = {"completed": 0}
start_time = time.time()
progress_lock = threading.Lock()

# ---- Funkcje ----
def print_progress_bar(completed, total, bar_length=30):
    fraction = completed / total
    filled_length = int(bar_length * fraction)
    bar = "█" * filled_length + "-" * (bar_length - filled_length)
    elapsed = time.time() - start_time
    if completed > 0:
        sec_per_page = elapsed / completed
        est_remaining = sec_per_page * (total - completed)
        est_min = int(est_remaining // 60)
        est_sec = int(est_remaining % 60)
    else:
        est_min = est_sec = 0
    print(f"[{bar}] {completed}/{total} | szac. czas: {est_min}m {est_sec}s", end="\r")

def fetch_page(i):
    global duplicates
    url = f"{BASE_URL}{i}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img", class_="article-image")
        if not img_tag:
            return

        img_url = img_tag["src"]
        img_name = os.path.basename(img_url.split("?")[0])
        img_path = os.path.join(OUTPUT_DIR, img_name)

        if os.path.exists(img_path):
            with progress_lock:
                duplicates[img_name] = duplicates.get(img_name, 0) + 1
        else:
            img_data = requests.get(img_url, headers=headers, timeout=10)
            with open(img_path, "wb") as f:
                f.write(img_data.content)

    except Exception as e:
        print(f"[ERR] {url}: {e}")
    finally:
        with progress_lock:
            progress["completed"] += 1

# ---- Pobieranie wielowątkowe ----
with ThreadPoolExecutor(max_workers=THREADS) as executor:
    futures = [executor.submit(fetch_page, i) for i in range(START, END + 1)]

    total = END - START + 1
    while progress["completed"] < total:
        with progress_lock:
            print_progress_bar(progress["completed"], total)
        time.sleep(1)

    # końcowy update
    print_progress_bar(progress["completed"], total)
    print()

# ---- Zapis duplikatów ----
if duplicates:
    with open(DUPLICATES_FILE, "w", encoding="utf-8") as f:
        json.dump(duplicates, f, indent=4, ensure_ascii=False)
    print(f"✅ Zapisano duplikaty do {DUPLICATES_FILE}")
else:
    print("✅ Brak duplikatów")

# ---- Commit i push do repo (GitHub Actions) ----
try:
    repo_dir = os.getcwd()
    subprocess.run(["git", "config", "user.name", "github-actions"], check=True)
    subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True)

    subprocess.run(["git", "add", OUTPUT_DIR], check=True, cwd=repo_dir)

    commit_msg = f"Pobrano obrazki {timestamp} ({START}-{END})"
    subprocess.run(["git", "commit", "-m", commit_msg], check=True, cwd=repo_dir)

    remote_url = f"https://x-access-token:{os.environ['GITHUB_TOKEN']}@github.com/{os.environ['GITHUB_REPOSITORY']}.git"

    # Pull/rebase przed push, aby uniknąć konfliktów
    subprocess.run(["git", "pull", "--rebase", remote_url, "main"], check=True, cwd=repo_dir)
    subprocess.run(["git", "push", remote_url, "HEAD:main"], check=True, cwd=repo_dir)

    print(f"✅ Zapisano wyniki w repozytorium: {commit_msg}")

except subprocess.CalledProcessError as e:
    print(f"[ERR] Git: {e}")
