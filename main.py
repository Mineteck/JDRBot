import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queues = {}  # file d’attente par serveur

YDL_OPTIONS = {
    'format': 'bestaudio',
    'quiet': True,
    'default_search': 'ytsearch'
}

FFMPEG_OPTIONS = {
    'options': '-vn'
}


async def play_next(ctx):
    if queues.get(ctx.guild.id):
        url = queues[ctx.guild.id].pop(0)

        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            url2 = info['url']
            title = info.get('title', 'Titre inconnu')

        source = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)

        ctx.voice_client.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        )

        await ctx.send(f"🎶 Lecture : {title}")
    else:
        await ctx.voice_client.disconnect()


@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")


@bot.command()
async def play(ctx, *, search):
    if not ctx.author.voice:
        await ctx.send("Tu dois être dans un salon vocal.")
        return

    channel = ctx.author.voice.channel

    if not ctx.voice_client:
        await channel.connect()

    if ctx.guild.id not in queues:
        queues[ctx.guild.id] = []

    queues[ctx.guild.id].append(search)

    if not ctx.voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"Ajouté à la queue : {search}")


@bot.command()
async def skip(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skip !")


@bot.command()
async def pause(ctx):
    if ctx.voice_client:
        ctx.voice_client.pause()
        await ctx.send("⏸️ Pause")


@bot.command()
async def resume(ctx):
    if ctx.voice_client:
        ctx.voice_client.resume()
        await ctx.send("▶️ Reprise")


@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        queues[ctx.guild.id] = []
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Stop et déconnexion")


@bot.command()
async def queue(ctx):
    q = queues.get(ctx.guild.id)

    if not q:
        await ctx.send("Queue vide.")
    else:
        msg = "\n".join([f"{i+1}. {song}" for i, song in enumerate(q)])
        await ctx.send(f"📜 Queue:\n{msg}")


bot.run(TOKEN)