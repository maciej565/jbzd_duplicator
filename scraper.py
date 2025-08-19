import requests
from bs4 import BeautifulSoup
import os
import time
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://jbzd.com.pl/oczekujace/"
OUTPUT_DIR = "images"
DUPLICATES_FILE = "duplikaty.json"
THREADS = 5  # liczba równoległych wątków

os.makedirs(OUTPUT_DIR, exist_ok=True)
headers = {"User-Agent": "Mozilla/5.0 (compatible; Bot/1.0)"}

START = int(sys.argv[1])
END = int(sys.argv[2])

duplicates = {}
progress = {"completed": 0}
start_time = time.time()

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
            duplicates[img_name] = duplicates.get(img_name, 0) + 1
        else:
            img_data = requests.get(img_url, headers=headers, timeout=10)
            with open(img_path, "wb") as f:
                f.write(img_data.content)

    except Exception as e:
        print(f"[ERR] {url}: {e}")
    finally:
        progress["completed"] += 1
        elapsed = time.time() - start_time
        completed = progress["completed"]
        remaining = END - START + 1 - completed
        if completed > 0:
            sec_per_page = elapsed / completed
            est_remaining = sec_per_page * remaining
            est_min = int(est_remaining // 60)
            est_sec = int(est_remaining % 60)
            print(f"[PROGRESS] {completed}/{END - START + 1} stron, szacowany czas pozostały: {est_min} min {est_sec} s")

with ThreadPoolExecutor(max_workers=THREADS) as executor:
    futures = [executor.submit(fetch_page, i) for i in range(START, END + 1)]
    for _ in as_completed(futures):
        pass

if duplicates:
    with open(DUPLICATES_FILE, "w", encoding="utf-8") as f:
        json.dump(duplicates, f, indent=4, ensure_ascii=False)
