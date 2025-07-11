import requests
import discord
from discord.ext import tasks, commands
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# === ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
load_dotenv()

# === НАСТРОЙКИ ===
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'ВАШ_НОВЫЙ_DISCORD_ТОКЕН_ЗДЕСЬ')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))  # ID вашего Discord канала
VK_TOKEN = os.getenv('VK_TOKEN', 'vk1.a.ВАШ_КЛЮЧ_СООБЩЕСТВА_ЗДЕСЬ')
VK_GROUP_ID = os.getenv('VK_GROUP_ID', 'your_vk_group')  # короткое имя сообщества (domain)
VK_GROUP_ID_2 = os.getenv('VK_GROUP_ID_2')  # короткое имя второго сообщества (domain)
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 30))  # Интервал проверки новых постов (сек)

logger.info("=== БОТ ЗАПУСКАЕТСЯ ===")
logger.info(f"Discord Channel ID: {DISCORD_CHANNEL_ID}")
logger.info(f"VK Group ID: {VK_GROUP_ID}")
logger.info(f"Check interval: {CHECK_INTERVAL} seconds")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

last_post_id = {}

@bot.slash_command(name="ping", description="Проверка работоспособности бота")
async def ping(ctx):
    await ctx.respond("🏓 Понг!", ephemeral=True)

@bot.event
async def on_ready():
    logger.info("🔄 Событие on_ready вызвано!")
    try:
        logger.info(f"=== БОТ УСПЕШНО ПОДКЛЮЧИЛСЯ К DISCORD ===")
        logger.info(f"Имя бота: {bot.user}")
        logger.info(f"ID бота: {bot.user.id}")
        logger.info(f"Имя пользователя: {bot.user.name}")
        logger.info(f"Дискриминатор: {bot.user.discriminator}")
        
        # Показываем информацию о серверах
        logger.info(f"Количество серверов: {len(bot.guilds)}")
        for guild in bot.guilds:
            logger.info(f"Сервер: {guild.name} (ID: {guild.id})")
        
        # Проверяем доступ к каналу
        logger.info(f"Ищу канал с ID: {DISCORD_CHANNEL_ID}")
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        
        if channel:
            logger.info(f"✅ Канал найден: #{channel.name} (ID: {channel.id})")
            logger.info(f"Тип канала: {channel.type}")
            
            # Проверяем права бота
            try:
                permissions = channel.permissions_for(channel.guild.me)
                logger.info(f"Права бота в канале: {permissions}")
                
                # Проверяем конкретные права
                if permissions.send_messages:
                    logger.info("✅ Право на отправку сообщений: ЕСТЬ")
                else:
                    logger.error("❌ НЕТ ПРАВА на отправку сообщений!")
                    
                if permissions.embed_links:
                    logger.info("✅ Право на встраивание ссылок: ЕСТЬ")
                else:
                    logger.warning("⚠️ НЕТ ПРАВА на встраивание ссылок (фото не будут отображаться)")
                    
            except Exception as perm_error:
                logger.error(f"❌ ОШИБКА при проверке прав: {perm_error}")
                logger.error(f"Тип ошибки прав: {type(perm_error).__name__}")
        else:
            logger.error(f"❌ КАНАЛ НЕ НАЙДЕН! ID: {DISCORD_CHANNEL_ID}")
            logger.error("Проверьте правильность ID канала и права бота")
            logger.error("Убедитесь, что бот добавлен на сервер и имеет доступ к каналу")
            
            # Показываем доступные каналы
            logger.info("Доступные каналы:")
            for guild in bot.guilds:
                logger.info(f"Сервер: {guild.name} (ID: {guild.id})")
                for ch in guild.channels:
                    if hasattr(ch, 'name'):
                        logger.info(f"  - #{ch.name} (ID: {ch.id}, тип: {ch.type})")
        
        logger.info("Запускаю задачу проверки VK постов...")
        if not check_vk_posts.is_running():
            check_vk_posts.start()
            logger.info("✅ Задача проверки VK постов запущена!")
        else:
            logger.info("Задача проверки VK постов уже запущена!")
        
        # Синхронизируем слэш-команды
        logger.info("Синхронизирую слэш-команды...")
        try:
            synced = await bot.tree.sync()
            logger.info(f"✅ Синхронизировано {len(synced)} команд")
        except Exception as sync_error:
            logger.error(f"❌ Ошибка синхронизации команд: {sync_error}")
        
    except Exception as e:
        logger.error(f"❌ ОШИБКА в on_ready: {e}")
        logger.error(f"Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    logger.info("🔄 Событие on_ready завершено!")

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_vk_posts():
    global last_post_id
    group_domains = [VK_GROUP_ID]
    if VK_GROUP_ID_2:
        group_domains.append(VK_GROUP_ID_2)

    for domain in group_domains:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            logger.info(f"[{current_time}] 🔍 Проверяю новые посты в VK для {domain}...")

            if not VK_TOKEN or VK_TOKEN.strip() == '':
                logger.error("❌ VK TOKEN НЕ УСТАНОВЛЕН!")
                continue

            # Получаем ID группы по domain
            group_url = f'https://api.vk.com/method/groups.getById?group_id={domain}&access_token={VK_TOKEN}&v=5.131'
            logger.info(f"Запрос к VK API: получение ID группы для {domain}")
            resp = requests.get(group_url, timeout=10)
            logger.info(f"Получен ответ от VK API. Статус: {resp.status_code}")

            if resp.status_code != 200:
                logger.error(f"❌ Ошибка HTTP: {resp.status_code}")
                logger.error(f"Текст ответа: {resp.text}")
                continue

            data = resp.json()
            logger.info(f"Ответ VK API получен. Структура: {list(data.keys())}")

            if 'response' not in data:
                logger.error(f"❌ ОШИБКА VK API: {data}")
                if 'error' in data:
                    error_code = data['error'].get('error_code')
                    error_msg = data['error'].get('error_msg')
                    logger.error(f"Код ошибки: {error_code}")
                    logger.error(f"Сообщение: {error_msg}")
                    if error_code == 5:
                        logger.error("❌ НЕВЕРНЫЙ ТОКЕН! Проверьте VK_TOKEN")
                    elif error_code == 15:
                        logger.error("❌ ДОСТУП ЗАПРЕЩЁН! Проверьте права приложения")
                    elif error_code == 100:
                        logger.error("❌ НЕВЕРНЫЙ ID СООБЩЕСТВА! Проверьте VK_GROUP_ID")
                continue

            group_info = data['response'][0]
            group_id = group_info['id']
            group_name = group_info.get('name', domain)
            group_screen_name = group_info.get('screen_name', domain)
            group_url = f"https://vk.com/{group_screen_name}"
            logger.info(f"ID группы: {group_id}")

            wall_url = f'https://api.vk.com/method/wall.get?owner_id=-{group_id}&count=1&access_token={VK_TOKEN}&v=5.131'
            logger.info(f"Запрос постов: owner_id=-{group_id}")

            wall_resp = requests.get(wall_url, timeout=10)
            if wall_resp.status_code != 200:
                logger.error(f"❌ Ошибка HTTP при получении постов: {wall_resp.status_code}")
                continue

            wall_data = wall_resp.json()
            if 'response' not in wall_data:
                logger.error(f"❌ ОШИБКА VK API при получении постов: {wall_data}")
                continue

            posts = wall_data['response']['items']
            logger.info(f"Найдено постов: {len(posts)}")

            if not posts:
                logger.warning("⚠️ Постов не найдено")
                continue

            post = posts[0]
            post_id = post['id']
            post_text = post.get('text', '')[:50] + '...' if len(post.get('text', '')) > 50 else post.get('text', '')
            # Формируем подпись о группе только с domain
            group_signature = f"**Источник:** {domain}"

            logger.info(f"Последний пост ID: {post_id}")
            logger.info(f"Текст поста: {post_text}")
            logger.info(f"Предыдущий ID: {last_post_id.get(domain)}")

            if last_post_id.get(domain) is None:
                logger.info("🔄 Первый запуск - сохраняю ID поста без отправки")
                last_post_id[domain] = post_id
                continue

            if post_id != last_post_id.get(domain):
                logger.info(f"🎉 НОВЫЙ ПОСТ НАЙДЕН! ID: {post_id}")
                logger.info(f"Отправляю в Discord...")
                last_post_id[domain] = post_id
                await send_post_to_discord(post, group_signature)
            else:
                logger.info("📭 Новых постов нет")

        except requests.exceptions.Timeout:
            logger.error("❌ ТАЙМАУТ при запросе к VK API")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ ОШИБКА СЕТИ при запросе к VK: {e}")
        except Exception as e:
            logger.error(f"❌ НЕОЖИДАННАЯ ОШИБКА при проверке VK: {e}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

async def send_post_to_discord(post, group_signature):
    logger.info("=== ОТПРАВКА ПОСТА В DISCORD ===")
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        logger.error(f"❌ КАНАЛ НЕ НАЙДЕН! ID: {DISCORD_CHANNEL_ID}")
        return

    logger.info(f"Канал найден: #{channel.name}")

    text = post.get('text', '')
    attachments = post.get('attachments', [])

    logger.info(f"Текст поста: {text[:100]}...")
    logger.info(f"Вложений: {len(attachments)}")

    # Добавляем подпись о группе
    if text:
        text = f"{group_signature}\n{text}"
    else:
        text = group_signature

    embeds = []

    for i, att in enumerate(attachments):
        att_type = att['type']
        logger.info(f"Вложение {i+1}: тип = {att_type}")

        if att_type == 'photo':
            # Берём самое большое фото
            photo_url = sorted(att['photo']['sizes'], key=lambda x: x['width']*x['height'], reverse=True)[0]['url']
            logger.info(f"Фото URL: {photo_url}")
            embeds.append(discord.Embed().set_image(url=photo_url))
        elif att_type == 'video':
            # Для видео вставляем ссылку на VK
            video = att['video']
            video_url = f"https://vk.com/video{video['owner_id']}_{video['id']}"
            logger.info(f"Видео URL: {video_url}")
            text += f"\n[Видео]({video_url})"

    try:
        logger.info("Отправляю текст поста...")
        if text:
            await channel.send(content=text)
            logger.info("✅ Текст отправлен")
        else:
            logger.info("Текст пустой, отправляю только вложения")

        logger.info(f"Отправляю {len(embeds)} вложений...")
        for i, embed in enumerate(embeds):
            await channel.send(embed=embed)
            logger.info(f"✅ Вложение {i+1} отправлено")

        logger.info("🎉 ПОСТ УСПЕШНО ОТПРАВЛЕН В DISCORD!")

    except discord.Forbidden:
        logger.error("❌ НЕТ ПРАВ для отправки в канал")
    except discord.HTTPException as e:
        logger.error(f"❌ ОШИБКА DISCORD API: {e}")
    except Exception as e:
        logger.error(f"❌ ОШИБКА при отправке: {e}")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"❌ ОШИБКА В СОБЫТИИ {event}: {args}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")

@bot.event
async def on_connect():
    logger.info("🔗 Бот подключился к Discord Gateway")

@bot.event
async def on_disconnect():
    logger.warning("🔌 Бот отключился от Discord Gateway")

@bot.event
async def on_guild_join(guild):
    logger.info(f"🎉 Бот добавлен на сервер: {guild.name} (ID: {guild.id})")

@bot.event
async def on_guild_remove(guild):
    logger.warning(f"👋 Бот удалён с сервера: {guild.name} (ID: {guild.id})")

if __name__ == '__main__':
    logger.info("=== ЗАПУСК БОТА ===")
    # Проверка наличия токенов
    if not DISCORD_TOKEN or DISCORD_TOKEN == 'ВАШ_НОВЫЙ_DISCORD_ТОКЕН_ЗДЕСЬ':
        logger.error("❌ DISCORD_TOKEN не установлен! Укажите токен в .env или переменных окружения.")
        exit(1)
    if not VK_TOKEN or VK_TOKEN == 'vk1.a.ВАШ_КЛЮЧ_СООБЩЕСТВА_ЗДЕСЬ':
        logger.error("❌ VK_TOKEN не установлен! Укажите токен в .env или переменных окружения.")
        exit(1)
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("❌ НЕВЕРНЫЙ DISCORD TOKEN!")
    except Exception as e:
        logger.error(f"❌ ОШИБКА ЗАПУСКА: {e}")