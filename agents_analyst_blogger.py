import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
from pytz import timezone
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO


import vk
import requests
import google.generativeai as _genai
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

        _genai.configure(api_key=gemini_api_key)
        self.model = _genai.GenerativeModel("gemini-2.0-flash")

    def fetch_posts_last_week(self) -> Tuple[List[dict], List[dict]]:
        group_info = self.api.groups.getById(group_id=self.group_screen_name)[0]
        owner_id = -group_info["id"]
        week_ago = int((datetime.now() - timedelta(days=7)).timestamp())

        posts = []
        offset = 0
        count = 100

        while True:
            batch = self.api.wall.get(owner_id=owner_id, offset=offset, count=count)
            if not batch.get("items"):
                break

            new_items = [item for item in batch["items"] if item["date"] >= week_ago]
            posts.extend(new_items)

            if all(item["date"] < week_ago for item in batch["items"]):
                break

            offset += count
            time.sleep(0.34)

        logger.info(f"Собрано постов за неделю из основной группы: {len(posts)}")

        # Вторая группа
        group_info = self.api.groups.getById(group_id=VK_BLOG_GROUP)[0]
        owner_id = -group_info["id"]
        offset = 0

        blog_posts = []
        while True:
            batch = self.api.wall.get(owner_id=owner_id, offset=offset, count=count)
            if not batch.get("items"):
                break

            new_items = [item for item in batch["items"] if item["date"] >= week_ago]
            blog_posts.extend(new_items)

            if all(item["date"] < week_ago for item in batch["items"]):
                break

            offset += count
            time.sleep(0.34)

        logger.info(f"Собрано постов за неделю из блога: {len(blog_posts)}")

        return posts, blog_posts

    def get_best_topics_and_times(self, posts: List[dict], blog_posts: List[dict]) -> Tuple[List[str], List[str]]:
        """Рекомендует список тем и оптимальное время публикации"""
        posts_summary = []
        date_today = datetime.now().date()
        full_posts = [f'Список новостей за неделю в Граховском районе и не только. Выпуск за {date_today}']
        # print('-------')
        # print(len(posts))
        # print('-------')
        for p in posts:
            text = p["text"].replace("\n", " ").strip()
            likes = p["likes"]["count"]
            reposts = p["reposts"]["count"]
            views = p.get("views", {}).get("count", 0)
            date = datetime.fromtimestamp(p["date"]).strftime('%Y-%m-%d %H:%M')
            # print(text[:80])
            
            like_str = f"| Лайки: {likes} | Репосты: {reposts} | Просмотры: {views}"
            full_posts.append(f"{text}\n{like_str}")
            like_str = f"{date} | «{text[:80]}...» " + like_str
            posts_summary.append(
                like_str
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
        if len(combined_blog) > 1000:
            combined_blog = combined_blog[:1000]
        prompt = (
            "Ты аналитик SMM. Вот посты за неделю:\n"
            f"{combined_text}\n\n"
            "Дай только список 5 интересных тем и лучшее время публикации для каждой (день/вечер, будни/выходные).\n"
            "Формат: тема | время\n"
            "Дополнительные рекомендации не нужны.\n"
        )
        # print('----------------------')
        # print(prompt)
        # print('----------------------')
        
        
        # blog_post_summary = f'{blog_post_summary}'
        # prompt += blog_post_summary
        response_txt = self.model.generate_content(prompt).text.strip()
        # print('----------------------')
        # print(response_txt)
        # print('----------------------')
        # lines = response_txt.splitlines()

        # topics, timings = [], []
        # for line in lines:
        #     if "|" in line:
        #         topic, timing = line.split("|", 1)
        #         topics.append(topic.strip())
        #         timings.append(timing.strip())

        # logger.info(f"Аналитик рекомендует: {topics} / {timings}")
        
        return response_txt, combined_blog


# ======================
# --- Village Content Generator ---
# ======================

class VillageContentGenerator:
    """Блоггер с ориентацией по времени и аналитикой"""
    def __init__(self, gemini_api_key: str, analytics_agent: VKAnalyticsAgent):
        self.api_key = gemini_api_key
        self.analytics_agent = analytics_agent

        _genai.configure(api_key=gemini_api_key)
        self.model = _genai.GenerativeModel('gemini-1.5-flash')

        self.system_prompt = """
        Ты — блоггер из деревни Иван. Пиши теплые, жизненные посты без пафоса.
        Формат — история или размышление без вопросов к читателю.
        Объем — 400-500 символов.
        """

    def generate_image_post(self, topic: str, save_path: str = "data/post_image.png") -> Tuple[str, str]:
        """
        Генерирует пост с изображением по теме.
        Возвращает текст поста и путь к сохраненному изображению.
        """
        from google import genai
        time_context = self._get_time_context()
        client_ = genai.Client(api_key=GEMINI_API_KEY)

        prompt = (
            f"Ты — художник из деревни. "
            f"Создай 3D-иллюстрацию на тему: {topic}. "
            f"Контекст: {time_context}. "
            "Сцена должна быть доброй, деревенской, с природой, животными или людьми."
        )
        

        try:
            
            response = client_.models.generate_content(
                model="gemini-2.0-flash-preview-image-generation",
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE']
                )
            )
            image = None
            text = "Скоро появится чудесное изображение деревенской жизни."

            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    text = part.text.strip()
                elif part.inline_data is not None:
                    image = Image.open(BytesIO(part.inline_data.data))
                    image.save(save_path)
            return text, save_path
        except Exception as e:
            logger.error(f"Ошибка генерации изображения: {e}")
            return f"Сегодня поговорим о {topic}.", None


    def get_season(self):
        month = datetime.now().month
        if month in [12]:
            return 'Декабрь зима'
        elif month in [1]:
            return 'Январь зима'
        elif month in [2]:
            return 'Февраль зима'
        elif month in [3]:
            return 'Март весна'
        elif month in [4]:
            return 'Апрель весна'
        elif month in [5]:
            return 'Май весна'
        elif month in [6]:
            return 'Июнь лето'
        elif month in [7]:
            return 'Июль лето'
        elif month in [8]:
            return 'Август лето'
        elif month in [9]:
            return 'Сентябрь осень'
        elif month in [10]:
            return 'Октябрь осень'
        elif month in [11]:
            return 'Ноябрь осень'

    def _get_time_context(self) -> str:
        now = datetime.now()
        hour = now.hour + 3
        weekday = now.weekday()
        if hour < 8:
            day_part = "утро"
        elif 9 <= hour < 17:
            day_part = "день"
        else:
            day_part = "вечер"

        weekend = "выходные" if weekday >= 5 else "будни"
        season = self.get_season()
        return f"{day_part}, {weekend}, {season}"

    def generate_post(self, topic: str,  old_blog_posts: str) -> str:
        time_context = self._get_time_context()
        prompt = (
            f"{self.system_prompt}\n\n"
            f"Сейчас: {time_context}\n\n"
            f"Аналитика контента:\n"
            f"Тема|Рекомендация времени для публикации\n"
            f"{topic}\n"
            f"А эти посты ты уже писал: {old_blog_posts}\n"
            "Напиши пост."
        )
        # print("=================")
        # print(prompt)
        # print("==================")
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Ошибка генерации поста: {e}")
            return f"Сегодня поговорим о {topic}."
        
    def post_image_to_vk(self, text: str, image_path: str):
        # 1. Получить upload_url
        upload_url_resp = requests.get("https://api.vk.com/method/photos.getWallUploadServer", params={
            "access_token": VK_ACCESS_TOKEN,
            "v": VK_API_VERSION,
            "group_id": VK_GROUP_ID,
        }).json()

        upload_url = upload_url_resp["response"]["upload_url"]

        # 2. Загрузить фото
        with open(image_path, "rb") as img_file:
            upload_resp = requests.post(upload_url, files={"photo": img_file}).json()

        # 3. Сохранить фото
        save_photo_resp = requests.get("https://api.vk.com/method/photos.saveWallPhoto", params={
            "access_token": VK_ACCESS_TOKEN,
            "v": VK_API_VERSION,
            "group_id": VK_GROUP_ID,
            "photo": upload_resp["photo"],
            "server": upload_resp["server"],
            "hash": upload_resp["hash"],
        }).json()

        photo_info = save_photo_resp["response"][0]
        attachment = f"photo{photo_info['owner_id']}_{photo_info['id']}"

        # 4. Опубликовать пост
        vk_signature = "\n\n👉 Подписывайтесь на нас!"
        post_resp = requests.get("https://api.vk.com/method/wall.post", params={
            "access_token": VK_ACCESS_TOKEN,
            "v": VK_API_VERSION,
            "owner_id": f"-{VK_GROUP_ID}",
            "message": text + vk_signature,
            "attachments": attachment,
            "from_group": 1,
        }).json()

        logger.info(f"Фото-пост опубликован в ВК: {post_resp}")

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

    def post_image_to_telegram(self, text: str, image_path: str):
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
        telegram_signature = "\n\n<a href=\"https://t.me/selhozblogger\">👉 Подписаться на Сельский Блогер</a>"
        data = {
            "chat_id": TG_CHAT_ID,
            "caption": f"{text}{telegram_signature}",
            "parse_mode": "HTML"
        }
        try:
            with open(image_path, "rb") as photo:
                files = {"photo": photo}
                response = requests.post(url, data=data, files=files)
                response.raise_for_status()
                logger.info(f"Фото-пост опубликован в Telegram: {response.json()}")
        except Exception as e:
            logger.error(f"Ошибка публикации фото в Telegram: {e}")

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
        topics, old_blog_posts = self.analytics_agent.get_best_topics_and_times(posts, blog_posts)
        
        if not topics:
            logger.warning("Нет тем для фото-поста.")
            return
    
        # topic = topics[0]
        if not topics:
            logger.warning("Нет рекомендаций от аналитика, публикую на общую тему.")
            topic = "деревенская жизнь"
        else:
            topic = topics
        # text, image_path = self.generate_image_post(topic)
        
        # if image_path:
        #     self.post_image_to_telegram(text, image_path)
        #     self.post_image_to_vk(text, image_path)
        # else:
        #     self.post_to_telegram(text)
        #     self.post_to_vk(text)
        post = self.generate_post(topic,  old_blog_posts)
        # print('-------------------')
        # print(post)
        # print('-------------------')
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
    scheduler.add_job(blogger.run_posting_cycle, 'cron', day_of_week='mon-fri', hour=7)
    scheduler.add_job(blogger.run_posting_cycle, 'cron', day_of_week='mon-fri', hour=14)
    scheduler.add_job(blogger.run_posting_cycle, 'cron', day_of_week='mon-fri', hour=19)

    # В выходные только утром
    scheduler.add_job(blogger.run_posting_cycle, 'cron', day_of_week='sat,sun', hour=11)

    scheduler.start()
    logger.info("Шедулер запущен.")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    start_scheduler()