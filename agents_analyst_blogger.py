import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
from pytz import timezone
from dotenv import load_dotenv


import vk
import requests
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler

# ======================
# --- ЗАГРУЗКА ОКРУЖЕНИЯ ---
# ======================

load_dotenv()

VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN") or "vk1.a.XXX"
VK_API_VERSION = os.getenv("VK_API_VERSION")
VK_GROUP_SCREEN_NAME = os.getenv("VK_GROUP_SCREEN_NAME")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")  # Твоя группа ВК

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN") 
TG_CHAT_ID = os.getenv("TG_CHAT_ID")  # Твой Telegram-чат

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VK_BLOG_GROUP = os.getenv("VK_BLOG_GROUP")

# ======================
# --- ЛОГГЕР ---
# ======================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("village_agent_scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================
# --- VK Analytics Agent ---
# ======================

class VKAnalyticsAgent:
    """Собирает метрики и дает рекомендации"""
    def __init__(self, access_token: str, api_version: str, group_screen_name: str, gemini_api_key: str):
        self.api = vk.API(access_token=access_token, v=api_version)
        self.group_screen_name = group_screen_name

        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    def fetch_posts_last_week(self) -> List[dict]:
        group_info = self.api.groups.getById(group_id=self.group_screen_name)[0]
        owner_id = -group_info["id"]
        week_ago = int((datetime.now() - timedelta(days=7)).timestamp())

        posts = []
        offset = 0
        count = 100

        while True:
            batch = self.api.wall.get(owner_id=owner_id, offset=offset, count=count)
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

        logger.info(f"Собрано постов за неделю: {len(posts)}")
        
        group_info = self.api.groups.getById(group_id=VK_BLOG_GROUP)[0]
        owner_id = -group_info["id"]
        week_ago = int((datetime.now() - timedelta(days=7)).timestamp())

        blog_posts = []
        offset = 0
        count = 100

        while True:
            batch = self.api.wall.get(owner_id=owner_id, offset=offset, count=count)
            if not batch["items"]:
                break
            for item in batch["items"]:
                if item["date"] < week_ago:
                    break
                blog_posts.append(item)
            if any(item["date"] < week_ago for item in batch["items"]):
                break
            offset += count
            time.sleep(0.34)

        return posts, blog_posts

    def get_best_topics_and_times(self, posts: List[dict], blog_posts: List[dict]) -> Tuple[List[str], List[str]]:
        """Рекомендует список тем и оптимальное время публикации"""
        posts_summary = []
        date_today = datetime.now().date()
        full_posts = [f'Список новостей за неделю в Граховском районе и не только. Выпуск за {date_today}']
        for p in posts:
            text = p["text"].replace("\n", " ").strip()
            likes = p["likes"]["count"]
            reposts = p["reposts"]["count"]
            views = p.get("views", {}).get("count", 0)
            date = datetime.fromtimestamp(p["date"]).strftime('%Y-%m-%d %H:%M')
            full_posts.append(text)
            posts_summary.append(
                f"{date} | «{text[:80]}...» | Лайки: {likes} | Репосты: {reposts} | Просмотры: {views}"
            )
        if datetime.now().weekday() == 2:
            with open(f'data/week_{date_today}.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(full_posts))
        combined_text = "\n".join(posts_summary)
        if len(combined_text) > 2000:
            combined_text = combined_text[:2000]
        blog_post_summary = []
        for p in blog_posts:
            text = p["text"].replace("\n", " ").strip()
            likes = p["likes"]["count"]
            reposts = p["reposts"]["count"]
            views = p.get("views", {}).get("count", 0)
            date = datetime.fromtimestamp(p["date"]).strftime('%Y-%m-%d %H:%M')
            full_posts.append(text)
            blog_post_summary.append(
                f"{date} | «{text[:80]}...» | Лайки: {likes} | Репосты: {reposts} | Просмотры: {views}"
            )
        combined_blog = '\n'.join(blog_post_summary)
        if len(blog_post_summary) > 1000:
            blog_post_summary = blog_post_summary[:1000]
        prompt = (
            "Ты аналитик SMM. Вот посты за неделю:\n"
            f"{combined_text}\n\n"
            "Дай список 5 интересных тем и лучшее время публикации для каждой (утро/день/вечер, будни/выходные). "
            "Формат: тема | время"
        )

        response_txt = self.model.generate_content(prompt).text.strip()
        blog_post_summary = f'\nА эти посты ты уже писал:\n{blog_post_summary}'
        response_txt += blog_post_summary
        lines = response_txt.splitlines()

        topics, timings = [], []
        for line in lines:
            if "|" in line:
                topic, timing = line.split("|", 1)
                topics.append(topic.strip())
                timings.append(timing.strip())

        logger.info(f"Аналитик рекомендует: {topics} / {timings}")
        return topics, timings


# ======================
# --- Village Content Generator ---
# ======================

class VillageContentGenerator:
    """Блоггер с ориентацией по времени и аналитикой"""
    def __init__(self, gemini_api_key: str, analytics_agent: VKAnalyticsAgent):
        self.api_key = gemini_api_key
        self.analytics_agent = analytics_agent

        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

        self.system_prompt = """
        Ты — блоггер из деревни Иван. Пиши теплые, жизненные посты без пафоса.
        Формат — история или размышление без вопросов к читателю.
        Объем — 600-800 символов.
        """

    def get_season(self):
        month = datetime.now().month
        if month in [12, 1, 2]:
            return 'Зима'
        elif month in [3, 4, 5]:
            return 'Весна'
        elif month in [6, 7, 8]:
            return 'Лето'
        elif month in [9, 10, 11]:
            return 'Осень'

    def _get_time_context(self) -> str:
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()

        if hour < 10:
            day_part = "утро"
        elif 10 <= hour < 17:
            day_part = "день"
        else:
            day_part = "вечер"

        weekend = "выходные" if weekday >= 5 else "будни"
        season = self.get_season()
        return f"{day_part}, {weekend}, {season}"

    def generate_post(self, topic: str) -> str:
        time_context = self._get_time_context()
        prompt = (
            f"{self.system_prompt}\n\n"
            f"Тема: {topic}\n"
            f"Сейчас: {time_context}\n\n"
            "Напиши пост."
        )

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Ошибка генерации поста: {e}")
            return f"Сегодня поговорим о {topic}."

    def post_to_vk(self, text: str):
        try:
            vk_signature = "\n\n👉 Подписаться на Сельский Блогер: https://t.me/selhozblogger"
            
            response = self.analytics_agent.api.wall.post(
                owner_id=VK_GROUP_ID,
                from_group=1,
                message=f"{text}{vk_signature}"
            )
            logger.info(f"Пост опубликован в VK: {response}")
        except Exception as e:
            logger.error(f"Ошибка публикации в VK: {e}")

    def post_to_telegram(self, text: str):
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        telegram_signature = "\n\n<a href=\"https://t.me/selhozblogger\">👉 Подписаться на Сельский Блогер</a>"
        payload = {
            "chat_id": TG_CHAT_ID,
            "text": f"{text}{telegram_signature}",
            "parse_mode": "HTML",
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Пост опубликован в Telegram: {response.json()}")
        except Exception as e:
            logger.error(f"Ошибка публикации в Telegram: {e}")

    def run_posting_cycle(self):
        """Запрашивает новые темы, пишет пост и публикует"""
        posts, blog_posts = self.analytics_agent.fetch_posts_last_week()
        topics, timings = self.analytics_agent.get_best_topics_and_times(posts, blog_posts)
        
        if not topics:
            logger.warning("Нет рекомендаций от аналитика, публикую на общую тему.")
            topic = "деревенская жизнь"
        else:
            topic = topics[0]

        post = self.generate_post(topic)
        self.post_to_vk(post)
        self.post_to_telegram(post)


# ======================
# --- Шедулер ---
# ======================

def start_scheduler():
    vk_agent = VKAnalyticsAgent(
        access_token=VK_ACCESS_TOKEN,
        api_version=VK_API_VERSION,
        group_screen_name=VK_GROUP_SCREEN_NAME,
        gemini_api_key=GEMINI_API_KEY
    )

    blogger = VillageContentGenerator(
        gemini_api_key=GEMINI_API_KEY,
        analytics_agent=vk_agent
    )

    scheduler = BackgroundScheduler(timezone=timezone('Europe/Moscow'))

    # Расписание: утром, днем, вечером по будням
    scheduler.add_job(blogger.run_posting_cycle, 'cron', day_of_week='mon-fri', hour=6)
    scheduler.add_job(blogger.run_posting_cycle, 'cron', day_of_week='mon-fri', hour=12)
    scheduler.add_job(blogger.run_posting_cycle, 'cron', day_of_week='mon-fri', hour=18)

    # В выходные только утром
    scheduler.add_job(blogger.run_posting_cycle, 'cron', day_of_week='sat,sun', hour=10)

    scheduler.start()
    logger.info("Шедулер запущен.")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    start_scheduler()