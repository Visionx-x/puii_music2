import os
import re
import asyncio
import aiofiles
import aiohttp
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from unidecode import unidecode
from ytSearch import VideosSearch

from AnonXMusic import app, LOGGER
from config import YOUTUBE_IMG_URL

# --- Helper Functions (Synchronous) ---

def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage

def circle(img):
    h, w = img.size
    a = Image.new('L', [h, w], 0)
    b = ImageDraw.Draw(a)
    b.pieslice([(0, 0), (h, w)], 0, 360, fill=255, outline="white")
    c = np.array(img)
    d = np.array(a)
    e = np.dstack((c, d))
    return Image.fromarray(e)

def clear(text):
    list = text.split(" ")
    title = ""
    for i in list:
        if len(title) + len(i) < 60:
            title += " " + i
    return title.strip()

def gen_thumb_sync(videoid, user_id, channel, views, duration, title, thumb_path, profile_path):
    try:
        youtube = Image.open(thumb_path)
        if os.path.exists(profile_path):
            xp = Image.open(profile_path)
        else:
            xp = youtube # Fallback

        image1 = changeImageSize(1280, 720, youtube)
        image2 = image1.convert("RGBA")
        background = image2.filter(filter=ImageFilter.BoxBlur(10))
        enhancer = ImageEnhance.Brightness(background)
        background = enhancer.enhance(0.5)

        y = changeImageSize(200, 200, circle(youtube))
        background.paste(y, (45, 225), mask=y)
        
        a = changeImageSize(200, 200, circle(xp))
        background.paste(a, (1045, 225), mask=a)

        draw = ImageDraw.Draw(background)
        
        # Font Fallback
        try:
            arial = ImageFont.truetype("AnonXMusic/assets/font2.ttf", 30)
            font = ImageFont.truetype("AnonXMusic/assets/font.ttf", 30)
        except:
            arial = ImageFont.load_default()
            font = ImageFont.load_default()

        draw.text((1110, 8), unidecode(app.name), fill="white", font=arial)
        draw.text(
            (55, 560),
            f"{channel} | {views[:23]}",
            (255, 255, 255),
            font=arial,
        )
        draw.text(
            (57, 600),
            clear(title),
            (255, 255, 255),
            font=font,
        )
        draw.line(
            [(55, 660), (1220, 660)],
            fill="white",
            width=5,
            joint="curve",
        )
        draw.ellipse(
            [(918, 648), (942, 672)],
            outline="white",
            fill="white",
            width=15,
        )
        draw.text(
            (36, 685),
            "00:00",
            (255, 255, 255),
            font=arial,
        )
        draw.text(
            (1185, 685),
            f"{duration[:23]}",
            (255, 255, 255),
            font=arial,
        )

        output_path = f"cache/{videoid}_{user_id}.png"
        background.save(output_path)
        return output_path
    except Exception as e:
        LOGGER(__name__).error(f"Error generating thumbnail image: {e}")
        return None

# --- Main Async Function ---

async def get_thumb(videoid, user_id):
    if os.path.isfile(f"cache/{videoid}_{user_id}.png"):
        return f"cache/{videoid}_{user_id}.png"

    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        # 1. Fetch Metadata (We use VideosSearch because your API doesn't return Channel/Views yet)
        results = VideosSearch(url, limit=1)
        for result in (await results.next())["result"]:
            try:
                title = result["title"]
                title = re.sub("\W+", " ", title)
                title = title.title()
            except:
                title = "Unsupported Title"
            try:
                duration = result["duration"]
            except:
                duration = "Unknown"
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            try:
                views = result["viewCount"]["short"]
            except:
                views = "Unknown Views"
            try:
                channel = result["channel"]["name"]
            except:
                channel = "Unknown Channel"

        # 2. Download Images Async
        thumb_path = f"cache/thumb{videoid}.png"
        profile_path = f"cache/profile{user_id}.jpg"

        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                if resp.status == 200:
                    f = await aiofiles.open(thumb_path, mode="wb")
                    await f.write(await resp.read())
                    await f.close()

        try:
            photo_found = False
            async for photo in app.get_chat_photos(user_id, 1):
                await app.download_media(photo.file_id, file_name=f'cache/profile{user_id}.jpg')
                photo_found = True
            
            if not photo_found:
                 # Try downloading bot's photo if user has none
                async for photo in app.get_chat_photos(app.id, 1):
                    await app.download_media(photo.file_id, file_name=f'cache/profile{user_id}.jpg')
        except:
            pass
        
        # 3. Process Image in Thread (Non-Blocking)
        loop = asyncio.get_running_loop()
        final_path = await loop.run_in_executor(
            None, 
            gen_thumb_sync, 
            videoid, user_id, channel, views, duration, title, thumb_path, profile_path
        )

        # 4. Cleanup temp files
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        if os.path.exists(profile_path):
            os.remove(profile_path)

        if final_path:
            return final_path
        else:
            return YOUTUBE_IMG_URL

    except Exception as e:
        LOGGER(__name__).error(f"Thumbnail Error: {e}")
        return YOUTUBE_IMG_URL
