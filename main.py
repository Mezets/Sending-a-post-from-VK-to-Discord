import os
import time
import requests
import discord
from discord.ext import tasks

# === НАСТРОЙКИ ===
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
VK_TOKEN = os.getenv('VK_TOKEN')
VK_GROUP_ID = int(os.getenv('VK_GROUP_ID'))
CHECK_INTERVAL = 30  # Интервал проверки новых постов (сек)

intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

last_post_id = None

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    print(f'Monitoring VK group: {VK_GROUP_ID}')
    print(f'Sending to Discord channel: {DISCORD_CHANNEL_ID}')
    check_vk_posts.start()

@tasks.loop(seconds=CHECK_INTERVAL)
async def check_vk_posts():
    global last_post_id
    url = f'https://api.vk.com/method/wall.get?owner_id={VK_GROUP_ID}&count=1&access_token={VK_TOKEN}&v=5.131'
    try:
        resp = requests.get(url)
        data = resp.json()
        if 'response' not in data:
            print('VK API error:', data)
            return
        post = data['response']['items'][0]
        post_id = post['id']
        if last_post_id is None:
            last_post_id = post_id
            print(f'Initial post ID: {post_id}')
            return
        if post_id != last_post_id:
            last_post_id = post_id
            print(f'New post found: {post_id}')
            await send_post_to_discord(post)
    except Exception as e:
        print('Error checking VK:', e)

async def send_post_to_discord(post):
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        print('Discord channel not found!')
        return
    
    text = post.get('text', '')
    attachments = post.get('attachments', [])
    embeds = []
    
    for att in attachments:
        if att['type'] == 'photo':
            photo_url = sorted(att['photo']['sizes'], key=lambda x: x['width']*x['height'], reverse=True)[0]['url']
            embeds.append(discord.Embed().set_image(url=photo_url))
        elif att['type'] == 'video':
            video = att['video']
            video_url = f"https://vk.com/video{video['owner_id']}_{video['id']}"
            text += f"\n[Видео]({video_url})"
        elif att['type'] == 'doc':
            doc = att['doc']
            doc_url = doc['url']
            text += f"\n[Документ: {doc['title']}]({doc_url})"
    
    if text:
        await channel.send(content=text)
    
    for embed in embeds:
        await channel.send(embed=embed)
    
    print(f'Post sent to Discord successfully!')

if __name__ == '__main__':
    print('Starting VK to Discord bot...')
    print(f'VK Group ID: {VK_GROUP_ID}')
    print(f'Discord Channel ID: {DISCORD_CHANNEL_ID}')
    client.run(DISCORD_TOKEN) 