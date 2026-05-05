import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv
import shared
import time

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

shared.bot = bot

# 🔥 YTDLP STABLE
YDL_OPTIONS = {
    "format": "bestaudio[ext=opus]/bestaudio/best",
    "quiet": True,
    "noplaylist": True,
    "retries": 10,
    "extractor_retries": 5,
    "extractor_args": {
        "youtube": {
            "player_client": ["android"]
        }
    }
}

# 🔥 FFmpeg FIX PRO
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
    "options": "-vn"
}

# 🔒 anti double trigger
_playing_lock = {}
disconnect_tasks = {}

async def update_status(guild_id):
    if guild_id not in shared.current:
        return

    track = shared.current[guild_id]
    title = track["title"]
    duration = track.get("duration", 0)

    start = shared.timestamps.get(guild_id, time.time())
    elapsed = int(time.time() - start)
    remaining = max(duration - elapsed, 0)

    vc = discord.utils.get(bot.voice_clients, guild__id=guild_id)

    if vc and vc.is_paused():
        status = f"⏸️ Pause • {title}"
    else:
        m, s = divmod(remaining, 60)
        status = f"🎵 {title} ({m}:{s:02d})"

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=status
        )
    )


async def auto_disconnect(vc, guild_id):
    await asyncio.sleep(10)

    if vc.channel:
        humans = [m for m in vc.channel.members if not m.bot]

        if len(humans) == 0:
            await vc.disconnect()

    # nettoyage
    disconnect_tasks.pop(guild_id, None)


@bot.event
async def on_voice_state_update(member, before, after):
    for vc in bot.voice_clients:
        if not vc.channel:
            continue

        guild_id = vc.guild.id
        humans = [m for m in vc.channel.members if not m.bot]

        if len(humans) == 0:
            if guild_id not in disconnect_tasks:
                task = bot.loop.create_task(auto_disconnect(vc, guild_id))
                disconnect_tasks[guild_id] = task
        else:
            # quelqu’un revient → annule le disconnect
            if guild_id in disconnect_tasks:
                disconnect_tasks[guild_id].cancel()
                disconnect_tasks.pop(guild_id, None)

async def play_next(ctx):
    guild_id = ctx.guild.id

    if ctx.voice_client is None:
        return

    # 🔁 LOOP SONG
    if shared.loop["song"] and shared.current.get(guild_id):
        track = shared.current[guild_id]

    else:
        # queue normale
        if shared.queues.get(guild_id):
            if len(shared.queues[guild_id]) > 0:
                track = shared.queues[guild_id].pop(0)

                # save history
                shared.history.setdefault(guild_id, []).append(track)

            else:
                track = None
        else:
            track = None

        # 🔁 LOOP QUEUE
        if not track:
            if shared.loop["queue"] and shared.history.get(guild_id):
                shared.queues[guild_id] = shared.history[guild_id].copy()
                track = shared.queues[guild_id].pop(0)
            else:
                return

    # 🎧 STREAM
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(track["url"], download=False)

        if "entries" in info:
            info = info["entries"][0]

        stream = info["url"]

    source = discord.FFmpegPCMAudio(stream, **FFMPEG_OPTIONS)

    def after(error):
        if error:
            print("FFMPEG ERROR:", error)

        asyncio.run_coroutine_threadsafe(
            play_next(ctx),
            bot.loop
        )

    ctx.voice_client.play(source, after=after)

    # ✅ update current propre
    shared.current[guild_id] = track
    shared.timestamps[guild_id] = time.time()
    await update_status(guild_id)


# 🎛 LOOP COMMAND
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


# ▶ PLAY
@bot.command()
async def play(ctx, *, search):
    if not ctx.author.voice:
        return await ctx.send("Vocal requis")

    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()

    guild_id = ctx.guild.id
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(search, download=False)

        if "entries" in info:
            info = info["entries"][0]

        track = {
            "title": info["title"],
            "url": info.get("webpage_url") or search,
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration", 0)
        }

    shared.queues.setdefault(guild_id, []).append(track)

    if not ctx.voice_client.is_playing():
        await play_next(ctx)


# ⏭ skip
@bot.command()
async def skip(ctx):
    ctx.voice_client.stop()


# ⏸ pause
@bot.command()
async def pause(ctx):
    ctx.voice_client.pause()
    await update_status(ctx.guild.id)


# ▶ resume
@bot.command()
async def resume(ctx):
    ctx.voice_client.resume()

    paused_time = shared.timestamps.get(ctx.guild.id, time.time())
    elapsed = time.time() - paused_time

    shared.timestamps[ctx.guild.id] = time.time() - elapsed

    await update_status(ctx.guild.id)

async def status_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        for guild_id in shared.current.keys():
            await update_status(guild_id)
        await asyncio.sleep(5)


def run_bot():
    bot.loop.create_task(status_loop())
    bot.run(TOKEN)