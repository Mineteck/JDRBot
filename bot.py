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

    vc = discord.utils.get(bot.voice_clients, guild__id=guild_id)

    # ❌ si pas connecté → reset status
    if not vc or not vc.is_connected():
        await bot.change_presence(activity=None)
        return

    if guild_id not in shared.current:
        return

    track = shared.current[guild_id]
    title = track["title"]
    duration = track.get("duration", 0)

    start = shared.timestamps.get(guild_id)
    pause_offset = shared.pause_offset.get(guild_id, 0)
    paused_at = shared.paused_at.get(guild_id)

    if not start:
        return

    # 🧠 CALCUL CLEAN
    if vc.is_paused() and paused_at:
        elapsed = int(paused_at - start - pause_offset)
        status = f"⏸️ Pause • {title}"
    else:
        elapsed = int(time.time() - start - pause_offset)

        #remaining = max(duration - elapsed, 0)
        #m, s = divmod(remaining, 60)

        status = f"🎵 {title}"

    # 🔒 anti spam discord API
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

    if not vc.channel:
        disconnect_tasks.pop(guild_id, None)
        return

    humans = [m for m in vc.channel.members if not m.bot]

    if len(humans) == 0:
        await vc.disconnect()

        # 🧹 CLEAN
        shared.current.pop(guild_id, None)
        shared.timestamps.pop(guild_id, None)
        shared.pause_offset.pop(guild_id, None)
        shared.paused_at.pop(guild_id, None)

        await bot.change_presence(activity=None)

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

    queue = shared.queues.get(guild_id, [])

    if len(queue) == 0:
        shared.current.pop(guild_id, None)
        return

    # init index
    if guild_id not in shared.current_index:
        shared.current_index[guild_id] = 0

    # 🔁 LOOP SONG
    if shared.loop["song"] and shared.current.get(guild_id):
        track = shared.current[guild_id]

    else:

        # musique suivante
        if shared.current.get(guild_id):
            shared.current_index[guild_id] += 1

        # fin queue
        if shared.current_index[guild_id] >= len(queue):

            if shared.loop["queue"]:
                shared.current_index[guild_id] = 0
            else:
                shared.current.pop(guild_id, None)
                return

        track = queue[shared.current_index[guild_id]]

    # 🎧 STREAM
    loop = asyncio.get_running_loop()

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = await loop.run_in_executor(
            None,
            lambda: ydl.extract_info(track["url"], download=False)
        )

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

    shared.current[guild_id] = track
    shared.timestamps[guild_id] = time.time()
    shared.pause_offset[guild_id] = 0
    shared.paused_at[guild_id] = None

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

    loop = asyncio.get_running_loop()

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = await loop.run_in_executor(
            None,
            lambda: ydl.extract_info(search, download=False)
        )

        if "entries" in info:
            info = info["entries"][0]

        track = {
            "title": info["title"],
            "url": info.get("webpage_url") or search,
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration", 0)
        }

    shared.queues.setdefault(guild_id, []).append(track)

    # init index
    if guild_id not in shared.current_index:
        shared.current_index[guild_id] = 0

    # ▶ démarre si rien joue
    if (
        not ctx.voice_client.is_playing()
        and not ctx.voice_client.is_paused()
        and not shared.current.get(guild_id)
    ):
        shared.current_index[guild_id] = -1
        await play_next(ctx)

    await ctx.send(f"🎶 Ajouté : {track['title']}")


# ⏭ skip
@bot.command()
async def skip(ctx):
    ctx.voice_client.stop()


# ⏸ pause
@bot.command()
async def pause(ctx):
    ctx.voice_client.pause()

    shared.paused_at[ctx.guild.id] = time.time()

    await update_status(ctx.guild.id)


# ▶ resume
@bot.command()
async def resume(ctx):
    ctx.voice_client.resume()

    paused = shared.paused_at.get(ctx.guild.id)
    if paused:
        delta = time.time() - paused
        shared.pause_offset[ctx.guild.id] = shared.pause_offset.get(ctx.guild.id, 0) + delta

    await update_status(ctx.guild.id)


# 🔁 STATUS LOOP
async def status_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():

        # 🧹 si le bot n'est connecté à aucun vocal → reset status
        if len(bot.voice_clients) == 0:
            await bot.change_presence(activity=None)

        else:
            for guild_id in list(shared.current.keys()):
                await update_status(guild_id)

        await asyncio.sleep(5)

@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id

    queue = shared.queues.get(guild_id, [])

    if len(queue) == 0:
        return await ctx.send("📭 Queue vide")

    msg = "🎶 Queue actuelle :\n\n"

    current = shared.current_index.get(guild_id, 0)

    for i, track in enumerate(queue):

        playing = ""

        if i == current:
            playing = "▶ "

        title = track["title"]

        duration = track.get("duration", 0)
        m, s = divmod(duration, 60)

        msg += f"{playing}`{i}` • {title} ({m}:{s:02d})\n"

    await ctx.send(msg[:2000])

@bot.command()
async def remove(ctx, index: int):
    guild_id = ctx.guild.id

    queue = shared.queues.get(guild_id, [])

    if len(queue) == 0:
        return await ctx.send("📭 Queue vide")

    if index < 0 or index >= len(queue):
        return await ctx.send("❌ Index invalide")

    removed = queue.pop(index)

    current = shared.current_index.get(guild_id, 0)

    # si on supprime avant la musique actuelle
    if index < current:
        shared.current_index[guild_id] -= 1

    # si on supprime la musique actuelle
    elif index == current:

        shared.current.pop(guild_id, None)

        shared.current_index[guild_id] -= 1

        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()

    await ctx.send(f"🗑️ Supprimé : {removed['title']}")

@bot.event
async def on_ready():
    await bot.change_presence(activity=None)


def run_bot():
    bot.run(TOKEN)