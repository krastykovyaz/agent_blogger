import requests
import json
import time
import random
import schedule
import datetime
import os
from typing import Dict, List, Optional
import logging
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('village_blogger.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class VillageContentGenerator:
    """Генератор контента с использованием Gemini API"""
    
    def __init__(self, gemini_api_key: str):
        self.model = None
        self.api_key = gemini_api_key
        
        if not gemini_api_key:
            logger.warning("Gemini API ключ не установлен, используем только резервные посты")
            return
            
        try:
            genai.configure(api_key=gemini_api_key)
            
            # Try different ways to initialize the model based on library version
            try:
                # New version (1.0.0+)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("Gemini AI успешно инициализирован (новая версия)")
            except AttributeError:
                try:
                    # Try older version method
                    self.model = genai.GenerativeModel("gemini-2.0-flash")
                    logger.info("Gemini AI успешно инициализирован (старая версия)")
                except AttributeError:
                    logger.warning("Не удалось инициализировать GenerativeModel, попробуем альтернативный метод")
                    self.model = None
                    
        except Exception as e:
            logger.error(f"Ошибка инициализации Gemini AI: {e}")
            self.model = None
        
        self.system_prompt = """
        Ты — блоггер, который пишет интересные, душевные и полезные посты для жителей сельской местности. 
        Твоя задача — делиться новостями, советами, историями и полезными лайфхаками для жизни в деревне или селе.
        
        Пиши простым, дружелюбным и понятным языком, добавляй эмоции, диалоги, личные наблюдения или местные выражения. 
        Посты должны быть теплыми, вызывать чувство уюта и отклик у людей старшего поколения и молодежи из сельской местности.
        
        В конце добавляй вопрос или приглашение к обсуждению, чтобы люди охотно писали комментарии.
        Используй эмодзи, но умеренно, чтобы текст оставался «домашним».
        
        Длина поста: 800-1200 символов.
        """
    
    def generate_post(self, topic: str, season: str = None) -> str:
        """Генерирует пост на заданную тему"""
        if not self.model:
            logger.warning("Gemini API недоступен, используем резервный пост")
            return self._get_fallback_post(topic)
            
        current_season = season or self._get_current_season()
        
        prompt = f"""
        {self.system_prompt}
        
        Напиши пост на тему: {topic}
        Текущий сезон: {current_season}
        
        Сделай пост живым, с конкретными деталями и личной историей.
        """
        
        try:
            response = self.model.generate_content(prompt)
            if response and hasattr(response, 'text') and response.text:
                logger.info(f"Контент успешно сгенерирован для темы: {topic}")
                return response.text
            elif response and hasattr(response, 'candidates') and response.candidates:
                # Try alternative response format
                text = response.candidates[0].content.parts[0].text
                logger.info(f"Контент успешно сгенерирован для темы: {topic}")
                return text
            else:
                logger.warning("Пустой ответ от Gemini API")
                return self._get_fallback_post(topic)
                
        except Exception as e:
            logger.error(f"Ошибка генерации контента: {e}")
            return self._get_fallback_post(topic)
    
    def _get_current_season(self) -> str:
        month = datetime.datetime.now().month
        if month in [12, 1, 2]:
            return "зима"
        elif month in [3, 4, 5]:
            return "весна"
        elif month in [6, 7, 8]:
            return "лето"
        else:
            return "осень"
    
    def _get_fallback_post(self, topic: str) -> str:
        """Резервный пост если API недоступен"""
        fallback_posts = {
            "сезонные работы в огороде": "🌱 Доброе утро, дорогие соседи! Сегодня с самого утра в огороде копошусь. Погода хорошая, самое время для садовых дел. Помидоры уже подвязываю, а огурцы только-только всходят. А что у вас нового на грядках? Поделитесь своими успехами! 😊",
            "домашние заготовки и консервация": "🥒 Заготавливаю на зиму огурчики по бабушкиному рецепту. Секрет в том, чтобы добавить листик хрена для хруста и немного дубовых листьев для аромата! Банки уже стерилизованы, рассол готов. А какие у вас любимые рецепты заготовок на зиму? 🌿",
            "народные рецепты и кулинария": "🍞 Сегодня пекла хлеб на закваске - такой аромат по всему дому! Бабушка всегда говорила: хлеб в доме - это благополучие и достаток. А у кого какие секреты домашней выпечки есть? Поделитесь рецептиками! 🥖",
            "деревенские истории и случаи": "😄 Вчера такая история приключилась! Соседский кот Васька умудрился залезть в курятник и устроить там переполох. Куры кудахчут, кот мяукает, а я с веником бегаю. В итоге все живы-здоровы, только нервы потрепали друг другу! А у вас какие забавные случаи бывают? 🐱",
            "практические советы для дома": "🔧 Делюсь полезным советом: чтобы москитная сетка дольше служила, протирайте её слабым раствором уксуса - и комары меньше липнут, и сетка не желтеет. Проверено на своем опыте! А какие у вас есть проверенные лайфхаки для дома? 🏠",
            "животноводство и птицеводство": "🐔 Курочки мои сегодня особенно активно несутся - видимо, погода им нравится! Свежие яички к завтраку - что может быть лучше? Главное - хорошо кормить и содержать в чистоте. А у кого какая живность во дворе? Расскажите! 🥚",
            "местные традиции и обычаи": "🎭 Скоро у нас в селе ярмарка народных промыслов будет. Бабушки готовят свои коврики и вязаные изделия, мужики деревянные поделки мастерят. Хорошо, что традиции живы! А в ваших краях какие народные праздники отмечают? 🎨",
            "общее": "☀️ Какое же прекрасное утро сегодня! Птички поют, воздух свежий, роса на траве блестит. Выйдешь на крыльцо - и душа радуется. Живем в раю, только не всегда это замечаем. А что вас сегодня порадовало? Поделитесь хорошим настроением! 🌸"
        }
        
        # Если точной темы нет, ищем по ключевым словам
        for key in fallback_posts:
            if any(word in topic.lower() for word in key.split()):
                return fallback_posts[key]
        
        return fallback_posts["общее"]

class VKPoster:
    """Класс для работы с VK API"""
    
    def __init__(self, access_token: str, group_id: str):
        if not access_token or not group_id:
            raise ValueError("VK access token и group ID обязательны")
            
        self.access_token = access_token
        self.group_id = group_id.replace('-', '')  # Убираем минус если есть
        self.api_version = '5.131'
        self.base_url = 'https://api.vk.com/method/'
    
    def post_to_wall(self, message: str, attachments: str = None) -> bool:
        """Публикует пост на стену сообщества"""
        url = f"{self.base_url}wall.post"
        
        params = {
            'owner_id': f'-{self.group_id}',
            'message': message,
            'from_group': 1,
            'access_token': self.access_token,
            'v': self.api_version
        }
        
        if attachments:
            params['attachments'] = attachments
        
        try:
            response = requests.post(url, params=params)
            result = response.json()
            
            if 'error' in result:
                logger.error(f"VK API Error: {result['error']}")
                return False
            
            logger.info(f"Пост успешно опубликован. ID: {result['response']['post_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка публикации поста: {e}")
            return False
    
    def get_wall_posts(self, count: int = 10) -> List[Dict]:
        """Получает последние посты со стены"""
        url = f"{self.base_url}wall.get"
        
        params = {
            'owner_id': f'-{self.group_id}',
            'count': count,
            'access_token': self.access_token,
            'v': self.api_version
        }
        
        try:
            response = requests.post(url, params=params)
            result = response.json()
            
            if 'error' in result:
                logger.error(f"VK API Error: {result['error']}")
                return []
            
            return result['response']['items']
            
        except Exception as e:
            logger.error(f"Ошибка получения постов: {e}")
            return []

class VillageBloggerAgent:
    """Главный класс агента-блоггера"""
    
    def __init__(self, vk_token: str, group_id: str, gemini_api_key: str):
        self.vk_poster = VKPoster(vk_token, group_id)
        self.content_generator = VillageContentGenerator(gemini_api_key)
        
        # Популярные темы с весами для случайного выбора
        self.topics = {
            'сезонные работы в огороде': 0.25,
            'домашние заготовки и консервация': 0.20,
            'народные рецепты и кулинария': 0.15,
            'деревенские истории и случаи': 0.15,
            'практические советы для дома': 0.10,
            'животноводство и птицеводство': 0.10,
            'местные традиции и обычаи': 0.05
        }
        
        # Временные интервалы для постинга (часы)
        self.posting_hours = [7, 12, 16, 19]  # Утро, обед, после обеда, вечер
        
        self.last_post_time = None
        self.min_interval_hours = 4  # Минимальный интервал между постами
        
    def should_post_now(self) -> bool:
        """Определяет, нужно ли публиковать пост сейчас"""
        current_time = datetime.datetime.now()
        current_hour = current_time.hour
        
        # Проверяем, что сейчас подходящее время для поста
        if current_hour not in self.posting_hours:
            return False
        
        # Проверяем минимальный интервал между постами
        if self.last_post_time:
            time_diff = current_time - self.last_post_time
            if time_diff.total_seconds() < self.min_interval_hours * 3600:
                return False
        
        # Случайный фактор (70% вероятность поста в подходящее время)
        return random.random() < 0.7
    
    def select_topic(self) -> str:
        """Выбирает тему для поста на основе весов"""
        topics = list(self.topics.keys())
        weights = list(self.topics.values())
        return random.choices(topics, weights=weights)[0]
    
    def analyze_recent_performance(self) -> Dict:
        """Анализирует производительность недавних постов"""
        posts = self.vk_poster.get_wall_posts(count=20)
        
        if not posts:
            return {}
        
        total_likes = sum(post.get('likes', {}).get('count', 0) for post in posts)
        total_comments = sum(post.get('comments', {}).get('count', 0) for post in posts)
        total_reposts = sum(post.get('reposts', {}).get('count', 0) for post in posts)
        total_views = sum(post.get('views', {}).get('count', 0) for post in posts)
        
        avg_engagement = {
            'likes': total_likes / len(posts),
            'comments': total_comments / len(posts),
            'reposts': total_reposts / len(posts),
            'views': total_views / len(posts)
        }
        
        logger.info(f"Средняя активность: {avg_engagement}")
        return avg_engagement
    
    def create_and_post(self) -> bool:
        """Создает и публикует новый пост"""
        try:
            topic = self.select_topic()
            logger.info(f"Выбрана тема: {topic}")
            
            post_content = self.content_generator.generate_post(topic)
            logger.info(f"Контент сгенерирован, длина: {len(post_content)} символов")
            
            success = self.vk_poster.post_to_wall(post_content)
            
            if success:
                self.last_post_time = datetime.datetime.now()
                logger.info("Пост успешно опубликован!")
                return True
            else:
                logger.error("Не удалось опубликовать пост")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при создании и публикации поста: {e}")
            return False
    
    def run_posting_cycle(self):
        """Один цикл проверки и возможной публикации"""
        logger.info("Проверка необходимости публикации поста...")
        
        if self.should_post_now():
            logger.info("Время для нового поста!")
            self.create_and_post()
        else:
            logger.info("Пока не время для поста")
    
    def start_continuous_mode(self):
        """Запускает агента в непрерывном режиме"""
        logger.info("🌾 Запуск Village Blogger Agent в непрерывном режиме...")
        
        # Планируем проверки каждый час
        schedule.every().hour.do(self.run_posting_cycle)
        
        # Первая проверка сразу при запуске
        self.run_posting_cycle()
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Проверяем каждую минуту
            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки. Завершаем работу...")
                break
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
                time.sleep(300)  # Ждем 5 минут перед продолжением

class AgentManager:
    """Управление агентом через простой интерфейс"""
    
    def __init__(self, agent: VillageBloggerAgent):
        self.agent = agent
    
    def post_now(self, topic: str = None):
        """Форсированная публикация поста прямо сейчас"""
        if topic:
            content = self.agent.content_generator.generate_post(topic)
        else:
            topic = self.agent.select_topic()
            content = self.agent.content_generator.generate_post(topic)
        
        return self.agent.vk_poster.post_to_wall(content)
    
    def get_status(self):
        """Получает статус агента"""
        status = {
            'last_post_time': self.agent.last_post_time,
            'next_possible_post': None,
            'performance': self.agent.analyze_recent_performance()
        }
        
        if self.agent.last_post_time:
            next_time = self.agent.last_post_time + datetime.timedelta(hours=self.agent.min_interval_hours)
            status['next_possible_post'] = next_time
        
        return status
    
    def change_posting_schedule(self, hours: List[int]):
        """Изменяет расписание постинга"""
        self.agent.posting_hours = hours
        logger.info(f"Расписание изменено на: {hours}")

def validate_environment():
    """Проверяет наличие всех необходимых переменных окружения"""
    required_vars = ['VK_ACCESS_TOKEN', 'GROUP_ID', 'GEMINI_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        logger.info("Создайте файл .env со следующими переменными:")
        logger.info("VK_ACCESS_TOKEN=your_vk_token")
        logger.info("GROUP_ID=-your_group_id")
        logger.info("GEMINI_API_KEY=your_gemini_key")
        return False
    
    return True

def start_village_blogger():
    """Запускает деревенского блоггера"""
    
    if not validate_environment():
        return
    
    # Получаем конфигурацию из переменных окружения
    VK_ACCESS_TOKEN = os.getenv('VK_ACCESS_TOKEN')
    GROUP_ID = os.getenv('GROUP_ID')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Создаем и запускаем агента
    try:
        agent = VillageBloggerAgent(VK_ACCESS_TOKEN, GROUP_ID, GEMINI_API_KEY)
        logger.info("Агент успешно создан")
        agent.start_continuous_mode()
    except Exception as e:
        logger.error(f"Критическая ошибка при создании агента: {e}")

def test_agent():
    """Функция для тестирования агента"""
    print("🧪 Тестирование агента...")
    
    if not validate_environment():
        return
    
    VK_ACCESS_TOKEN = os.getenv('VK_ACCESS_TOKEN')
    GROUP_ID = os.getenv('GROUP_ID')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    try:
        agent = VillageBloggerAgent(VK_ACCESS_TOKEN, GROUP_ID, GEMINI_API_KEY)
        manager = AgentManager(agent)
        
        # Тест генерации контента
        test_topic = "сезонные работы в огороде"
        content = agent.content_generator.generate_post(test_topic)
        print(f"✅ Тест генерации контента прошел успешно")
        print(f"Тема: {test_topic}")
        print(f"Контент: {content[:100]}...")
        
        # Тест получения статуса
        status = manager.get_status()
        print(f"✅ Тест получения статуса: {status}")
        
        print("🎉 Все тесты пройдены!")
        
    except Exception as e:
        print(f"❌ Ошибка в тестах: {e}")

if __name__ == "__main__":
    # Установка зависимостей:
    # pip install requests schedule google-generativeai python-dotenv
    
    print("🌾 ДЕРЕВЕНСКИЙ БЛОГГЕР АГЕНТ 🌾")
    print("=" * 50)
    print("Автоматическая публикация постов в VK")
    print("Интеграция с Gemini AI для генерации контента")
    print("=" * 50)
    
    # Выберите режим запуска
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_agent()
    else:
        start_village_blogger()