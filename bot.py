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


# ✅ BOT CLASS (fix loop error)
class MyBot(commands.Bot):
    async def setup_hook(self):
        self.loop.create_task(status_loop())


bot = MyBot(command_prefix="!", intents=intents)
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

disconnect_tasks = {}
last_status = ""


# 🎯 STATUS
async def update_status(guild_id):
    global last_status

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

    # 🚫 anti spam discord
    if status == last_status:
        return

    last_status = status

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=status[:100]
        )
    )


# 🔌 AUTO DISCONNECT
async def auto_disconnect(vc, guild_id):
    await asyncio.sleep(10)

    if vc.channel:
        humans = [m for m in vc.channel.members if not m.bot]

        if len(humans) == 0:
            await vc.disconnect()

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
            if guild_id in disconnect_tasks:
                disconnect_tasks[guild_id].cancel()
                disconnect_tasks.pop(guild_id, None)


# ▶️ PLAY NEXT
async def play_next(ctx):
    guild_id = ctx.guild.id

    if ctx.voice_client is None:
        return

    # 🔁 LOOP SONG
    if shared.loop["song"] and shared.current.get(guild_id):
        track = shared.current[guild_id]

    else:
        if shared.queues.get(guild_id) and len(shared.queues[guild_id]) > 0:
            track = shared.queues[guild_id].pop(0)
            shared.history.setdefault(guild_id, []).append(track)
        else:
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

        asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)

    ctx.voice_client.play(source, after=after)

    shared.current[guild_id] = track
    shared.timestamps[guild_id] = time.time()

    await update_status(guild_id)


# 🎛 LOOP
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
    shared.timestamps[ctx.guild.id] = time.time()
    await update_status(ctx.guild.id)


# 🔁 STATUS LOOP
async def status_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        for guild_id in list(shared.current.keys()):
            await update_status(guild_id)
        await asyncio.sleep(5)


def run_bot():
    bot.run(TOKEN)