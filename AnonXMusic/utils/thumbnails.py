import os
import re

import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageOps, ImageFilter
from unidecode import unidecode
from ytSearch import VideosSearch

from AnonXMusic import app
from config import YOUTUBE_IMG_URL

# Ensure cache directory exists
os.makedirs("cache", exist_ok=True)

def changeImageSize(maxWidth, maxHeight, image):
    widthRatio = maxWidth / image.size[0]
    heightRatio = maxHeight / image.size[1]
    newWidth = int(widthRatio * image.size[0])
    newHeight = int(heightRatio * image.size[1])
    newImage = image.resize((newWidth, newHeight))
    return newImage


def clear(text):
    if not text:
        return ""
    list = text.split(" ")
    title = ""
    for i in list:
        if len(title) + len(i) < 60:
            title += " " + i
    return title.strip()


async def get_thumb(videoid, user_id=None, force_update=False):
    """
    Generate a thumbnail for a YouTube video using a template image
    
    Args:
        videoid (str): YouTube video ID
        user_id (int, optional): User ID (kept for compatibility)
        force_update (bool, optional): Force regeneration of thumbnail

    Returns:
        str: Path to thumbnail image or fallback URL
    """
    # Make sure cache directory exists
    os.makedirs("cache", exist_ok=True)
    
    # Return cached version if it exists and not forcing update
    if os.path.isfile(f"cache/{videoid}.png") and not force_update:
        return f"cache/{videoid}.png"

    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        results = VideosSearch(url, limit=1)
        results_data = await results.next()
        
        if not results_data or not results_data.get("result"):
            print(f"No results found for {videoid}")
            return YOUTUBE_IMG_URL
        
        result = results_data["result"][0]
            
        # Extract video details with error handling
        thumbnail = YOUTUBE_IMG_URL
        channel = "Unknown Artist"
        
        try:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        except Exception as e:
            print(f"Error processing thumbnail URL: {e}")
            
        try:
            channel = result.get("channel", {}).get("name", "Unknown Artist")
        except Exception as e:
            print(f"Error processing channel name: {e}")

        # Download thumbnail
        temp_thumb = f"cache/thumb{videoid}.png"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(thumbnail) as resp:
                    if resp.status == 200:
                        f = await aiofiles.open(temp_thumb, mode="wb")
                        await f.write(await resp.read())
                        await f.close()
                    else:
                        print(f"Failed to download thumbnail: HTTP {resp.status}")
                        return YOUTUBE_IMG_URL
        except Exception as e:
            print(f"Error downloading thumbnail: {e}")
            return YOUTUBE_IMG_URL

        try:
            # Load template image and print dimensions for debugging
            template_path = "AnonXMusic/assets/new_template.jpg"
            if not os.path.exists(template_path):
                print(f"New template image not found at {template_path}")
                # Fall back to original template if new one is not found
                template_path = "AnonXMusic/assets/template.jpg"
                if not os.path.exists(template_path):
                    print(f"Template image not found at {template_path}")
                    return YOUTUBE_IMG_URL
                
            template = Image.open(template_path).convert("RGBA")
            template_width, template_height = template.size
            print(f"Template dimensions: {template_width}x{template_height}")
            
            # Load the song artwork
            song_art = Image.open(temp_thumb).convert("RGBA")
            
            # Precisely sized to cover only the girl surrounded by flowers
            artwork_width = int(template_width * 0.44)    # Width to cover just the floral area
            artwork_height = int(template_width * 0.22)   # Shorter height to match the flower-surrounded area
            
            # Positioned to exactly overlay the girl with flowers
            artwork_x = int(template_width * 0.28)        # Repositioned to center on the girl image
            artwork_y = int(template_height * 0.15)       # Fine-tuned vertical position for perfect centering
            
            # Create a mask for rounded corners - matching the flower area's shape
            corner_radius = int(artwork_width * 0.10)     # Corner radius to match the flower area's contour
            
            # Resize the song artwork to fit in the template
            # Use LANCZOS for high-quality resizing
            song_art = song_art.resize((artwork_width, artwork_height), Image.LANCZOS)
            
            # Create a mask for rounded corners - softer corners for natural framing
            corner_radius = int(artwork_width * 0.09)     # Increased radius for softer framing effect
            
            # Create a larger canvas for the artwork to add effects
            effects_padding = 15  # Padding for shadow and border
            art_with_effects = Image.new(
                "RGBA", 
                (artwork_width + effects_padding*2, artwork_height + effects_padding*2),
                (0, 0, 0, 0)
            )
            
            # Create shadow first (larger rounded rectangle behind artwork)
            shadow = Image.new("RGBA", art_with_effects.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                [(effects_padding-5, effects_padding-5), 
                 (effects_padding + artwork_width+5, effects_padding + artwork_height+5)],
                corner_radius+5,
                fill=(0, 0, 0, 100)  # Semi-transparent black for shadow
            )
            # Blur the shadow for softer effect
            shadow = shadow.filter(ImageFilter.GaussianBlur(10))
            
            # Add shadow to the canvas
            art_with_effects.paste(shadow, (0, 0), shadow)
            
            # Create mask for artwork with rounded corners
            mask = Image.new("L", (artwork_width, artwork_height), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([(0, 0), (artwork_width, artwork_height)], corner_radius, fill=255)
            
            # Apply mask to song artwork
            song_art.putalpha(mask)
            
            # Create border (slightly larger rounded rectangle around artwork)
            border_img = Image.new("RGBA", (artwork_width+6, artwork_height+6), (0, 0, 0, 0))
            border_draw = ImageDraw.Draw(border_img)
            border_draw.rounded_rectangle(
                [(0, 0), (artwork_width+6, artwork_height+6)],
                corner_radius+3,
                fill=(255, 255, 255, 0),  # Transparent fill
                outline=(255, 255, 255, 180),  # White border
                width=3  # Border width
            )
            
            # Add border to effects canvas
            art_with_effects.paste(border_img, (effects_padding-3, effects_padding-3), border_img)
            
            # Add artwork on top of effects
            art_with_effects.paste(song_art, (effects_padding, effects_padding), song_art)
            
            # Optional: Add subtle glow effect by overlaying a colored layer
            glow = Image.new("RGBA", art_with_effects.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow)
            glow_draw.rounded_rectangle(
                [(effects_padding, effects_padding), 
                 (effects_padding + artwork_width, effects_padding + artwork_height)],
                corner_radius,
                fill=(255, 255, 255, 0),  # Transparent fill
                outline=(180, 180, 255, 60),  # Subtle blue glow
                width=5  # Glow width
            )
            glow = glow.filter(ImageFilter.GaussianBlur(5))
            
            # Blend glow with artwork
            art_with_effects = Image.alpha_composite(art_with_effects, glow)
            
            # Paste the artwork with effects onto the template
            # Adjust position to account for the effects padding
            template.paste(
                art_with_effects, 
                (artwork_x - effects_padding, artwork_y - effects_padding), 
                art_with_effects
            )
            
            # Save the final image
            final_image_path = f"cache/{videoid}.png"
            template.convert("RGB").save(final_image_path)
            
            # Clean up temp file
            try:
                if os.path.exists(temp_thumb):
                    os.remove(temp_thumb)
            except Exception as e:
                print(f"Error removing temporary thumbnail: {e}")
                
            return final_image_path
            
        except Exception as e:
            print(f"Error processing image: {e}")
            # Try to clean up temp file in case of failure
            try:
                if os.path.exists(temp_thumb):
                    os.remove(temp_thumb)
            except:
                pass
            return YOUTUBE_IMG_URL

    except Exception as e:
        print(f"Error in get_thumb: {e}")
        return YOUTUBE_IMG_URL