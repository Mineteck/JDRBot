import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv
import shared

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

shared.bot = bot

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "noplaylist": True
}

FFMPEG_OPTIONS = {
    "options": "-vn -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}


async def play_next(ctx):
    guild_id = ctx.guild.id

    if ctx.voice_client is None:
        return

    # 🔁 LOOP SONG
    if shared.loop["song"] and shared.current.get(guild_id):
        search = shared.current[guild_id]["source"]

    else:
        if shared.queues.get(guild_id):
            search = shared.queues[guild_id].pop(0)
        else:
            # 🔁 LOOP QUEUE
            if shared.loop["queue"]:
                shared.queues[guild_id] = shared.current.get("history", []).copy()
                if not shared.queues[guild_id]:
                    return
                search = shared.queues[guild_id].pop(0)
            else:
                return

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(search, download=False)

        if "entries" in info:
            info = info["entries"][0]

        stream = info["url"]
        title = info["title"]

    source = discord.FFmpegPCMAudio(stream, **FFMPEG_OPTIONS)

    def after(e):
        asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)

    ctx.voice_client.play(source, after=after)

    shared.current[guild_id] = {
        "title": title,
        "source": search
    }

@bot.command()
async def loop(ctx, mode=None):
    if mode == "song":
        shared.loop["song"] = not shared.loop["song"]
        await ctx.send(f"🔁 loop song = {shared.loop['song']}")

    elif mode == "queue":
        shared.loop["queue"] = not shared.loop["queue"]
        await ctx.send(f"🔁 loop queue = {shared.loop['queue']}")

    else:
        await ctx.send("Utilise: !loop song | !loop queue")

@bot.command()
async def play(ctx, *, search):
    if not ctx.author.voice:
        return await ctx.send("Vocal requis")

    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()

    guild_id = ctx.guild.id

    shared.queues.setdefault(guild_id, []).append(search)

    if not ctx.voice_client.is_playing():
        await play_next(ctx)


@bot.command()
async def skip(ctx):
    ctx.voice_client.stop()


@bot.command()
async def pause(ctx):
    ctx.voice_client.pause()


@bot.command()
async def resume(ctx):
    ctx.voice_client.resume()


def run_bot():
    bot.run(TOKEN)