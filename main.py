import os
import discord
from discord.ext import commands
import yt_dlp
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queues = {}
current = {}

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "retries": 3
}

FFMPEG_OPTIONS = {
    "options": "-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}


async def play_next(ctx):
    guild_id = ctx.guild.id

    if queues.get(guild_id):
        url = queues[guild_id].pop(0)

        try:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(url, download=False)
                stream = info["url"]
                title = info.get("title")

            source = discord.FFmpegPCMAudio(stream, **FFMPEG_OPTIONS)

            def after(e):
                asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)

            ctx.voice_client.play(source, after=after)
            current[guild_id] = title

            await ctx.send(f"🎶 {title}")

        except Exception as e:
            print("Erreur:", e)
            await play_next(ctx)

    await asyncio.sleep(60)
    if not ctx.voice_client.is_playing():
        await ctx.voice_client.disconnect()


@bot.command()
async def play(ctx, *, search):
    if not ctx.author.voice:
        return await ctx.send("Tu dois être en vocal")

    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()

    guild_id = ctx.guild.id

    queues.setdefault(guild_id, [])
    queues[guild_id].append(search)

    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send("Ajouté à la queue")


@bot.command()
async def skip(ctx):
    ctx.voice_client.stop()


@bot.command()
async def pause(ctx):
    ctx.voice_client.pause()


@bot.command()
async def resume(ctx):
    ctx.voice_client.resume()


bot.run(TOKEN)