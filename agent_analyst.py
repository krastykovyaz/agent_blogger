import vk
import os
import time
from datetime import datetime, timedelta
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Конфигурация ---
ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN")
API_VERSION = os.getenv("VK_API_VERSION")
GROUP_SCREEN_NAME = os.getenv("VK_GROUP_SCREEN_NAME")

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # должен быть установлен в окружении

# --- Инициализация VK API ---
api = vk.API(access_token=ACCESS_TOKEN, v=API_VERSION)
group_info = api.groups.getById(group_id=GROUP_SCREEN_NAME)[0]
group_id = group_info["id"]
owner_id = -group_id

# --- Получаем посты за последнюю неделю ---
week_ago = int((datetime.now() - timedelta(days=7)).timestamp())
posts = []
offset = 0
count = 100

while True:
    batch = api.wall.get(owner_id=owner_id, offset=offset, count=count)
    if not batch["items"]:
        break
    for item in batch["items"]:
        if item["date"] < week_ago:
            break
        posts.append(item)
    if any(item["date"] < week_ago for item in batch["items"]):
        break
    offset += count
    time.sleep(0.34)

print(f"Собрано постов: {len(posts)}")

# --- Формируем текст для Gemini с метриками ---
posts_summary = []
for p in posts:
    text = p["text"].replace("\n", " ").strip()
    likes = p["likes"]["count"]
    reposts = p["reposts"]["count"]
    views = p.get("views", {}).get("count", 0)
    posts_summary.append(f"Текст: «{text[:100]}...» | Лайки: {likes} | Репосты: {reposts} | Просмотры: {views}")

combined_text = "\n\n".join(posts_summary)
if len(combined_text) > 3000:  # ограничим размер
    combined_text = combined_text[:3000] + "\n...[текст обрезан]"

# --- Инициализация Gemini через genai SDK ---
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.0-flash")

# --- Формируем промпт ---
prompt = (
    "Ты аналитик, который кратко подводит итоги по группе ВКонтакте с учетом лайков, репостов и просмотров.\n"
    "Проанализируй и дай саммари по этим постам и их метрикам:\n" + combined_text
)

# --- Запрос к Gemini ---
response = model.generate_content(prompt)
summary = response.text

print("\n--- Gemini аналитика ---\n")
print(summary)