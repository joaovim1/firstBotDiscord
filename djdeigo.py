import asyncio
import os

import discord
import yt_dlp
from discord.ext import commands
from openai import OpenAI
#TOKENS
DISCORD_TOKEN = "MTQyMDA1NzczNjk4NDY2MjIwOA.GAjar1.ITqezY3qhcbsgeij4491esrrh-BJsXfG9yJGI0"
SPOTIFY_CLIENT_ID = "90c132a779ce43ee981ad6eef6425dd5"
SPOTIFY_CLIENT_SECRET = "b1432c41ec8c4232a3ead35a93c58e3a"

# Inicializa o client da OpenAI
client = OpenAI()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

cache_musicas = {}
filas = {}  # {"guild_id": [{"url": str, "titulo": str, "ctx": ctx}, ...]}


class ControleMusica(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="⏭️ Pular", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.ctx.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ DJ DEIGO DEIGO PULOU A MÚSICA.")
        else:
            await interaction.response.send_message("❌ Nenhuma música tocando.", ephemeral=True)

    @discord.ui.button(label="⏯️ Pausar/Continuar", style=discord.ButtonStyle.primary)
    async def pausar(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.ctx.voice_client
        if vc is None:
            await interaction.response.send_message("❌ DJ DEIGO DEIGO NAO TA AFIM DE TOCAR.", ephemeral=True)
            return
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ DJ DEIGO DEIGO PAUSOU.")
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ DJ DEIGO DEIGO TA ONLAINE.")
        else:
            await interaction.response.send_message("❌ Nada para pausar.", ephemeral=True)

    @discord.ui.button(label="⏹️ Parar", style=discord.ButtonStyle.danger)
    async def parar(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.ctx.voice_client
        if vc:
            filas[self.ctx.guild.id] = []  # limpa a fila
            await vc.disconnect()
            await interaction.response.send_message("🛑 DJ DEIGO DEIGO SAIU VAZADO.")
        else:
            await interaction.response.send_message("❌ DJ DEIGO DEIGO NAO TA NA SALA ANIMALLLL.", ephemeral=True)


async def gerar_pesquisa(mensagem):
    try:
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {"role": "system", "content": "Você é um assistente musical. Dê apenas o nome da música e artista, sem explicações."},
                {"role": "user", "content": mensagem}  # <-- usar a mensagem real do usuário
            ]
        )
        return resposta.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro OpenAI: {e}")
        return "Desculpe, estou sem acesso à API no momento."

#TOCAR PROXIMA MUSICA FILA
async def tocar_proxima(guild_id):
    if guild_id not in filas or not filas[guild_id]:
        return  # fila vazia

    musica = filas[guild_id][0]  # pegar a primeira música da fila
    ctx = musica["ctx"]
    url = musica["url"]
    titulo = musica["titulo"]

    if ctx.voice_client is None:
        await ctx.author.voice.channel.connect()

    vc = ctx.voice_client

    # se já estiver tocando, não tenta tocar de novo
    if vc.is_playing() or vc.is_paused():
        return

    ydl_opts = {"quiet": True, "format": "bestaudio"}
    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        audio_url = info["url"]

    def depois(err):
        if err:
            print(f"Erro ao tocar música: {err}")
        # remove a música que acabou de tocar da fila
        if filas[guild_id]:
            filas[guild_id].pop(0)
        # chama a próxima música da fila
        asyncio.run_coroutine_threadsafe(tocar_proxima(guild_id), bot.loop)

    vc.play(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts), after=depois)
    await ctx.send(f"🎶 DJ DEIGO DEIGO Tocando: **{titulo}**", view=ControleMusica(ctx))


@bot.command()
async def musica(ctx, *, pedido):
    """Busca música com OpenAI e adiciona na fila"""
    await ctx.send(f"🎧 DJ DEIGO DEIGO BUSCANDO: **{pedido}**...")

    if pedido in cache_musicas:
        musica_cache = cache_musicas[pedido]
    else:
        pesquisa = await gerar_pesquisa(pedido)
        ydl_opts = {"quiet": True, "noplaylist": True, "format": "bestaudio"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            resultado = ydl.extract_info(f"ytsearch:{pesquisa}", download=False)["entries"][0]
            musica_cache = {"url": resultado["webpage_url"], "titulo": resultado["title"]}
            cache_musicas[pedido] = musica_cache

    guild_id = ctx.guild.id
    if guild_id not in filas:
        filas[guild_id] = []

    filas[guild_id].append({"url": musica_cache["url"], "titulo": musica_cache["titulo"], "ctx": ctx})

    if len(filas[guild_id]) == 1:
        await tocar_proxima(guild_id)
    else:
        await ctx.send(f"➕ DJ DEIGO DEIGO COLOCO NA FILA: **{musica_cache['titulo']}** (posição {len(filas[guild_id])})")


@bot.command()
async def fila(ctx):
    guild_id = ctx.guild.id
    if guild_id not in filas or not filas[guild_id]:
        await ctx.send("🎵 Fila vazia.")
        return

    lista = "\n".join([f"{i+1}. {musica['titulo']}" for i, musica in enumerate(filas[guild_id])])
    await ctx.send(f"📜 **Fila de músicas:**\n{lista}")


@bot.command()
async def pinote(ctx):
    if ctx.author.voice is None:
        await ctx.send("❌ ENTRA NA SALA, MLK BURRO!")
        return

    canal = ctx.author.voice.channel
    if ctx.voice_client is None:
        await canal.connect()
    elif ctx.voice_client.channel != canal:
        await ctx.voice_client.move_to(canal)

    vc = ctx.voice_client
    arquivo_mp3 = "pinote.mp3"

    if not os.path.exists(arquivo_mp3):
        await ctx.send("⚠️ Arquivo pinote.mp3 não encontrado!")
        return

    vc.stop()
    vc.play(discord.FFmpegPCMAudio(arquivo_mp3))
    await ctx.send("😭😭😭😭😭😭😭😭😭😭", view=ControleMusica(ctx))
#OUTRO
@bot.command()
async def deigo(ctx):
    if ctx.author.voice is None:
        await ctx.send("❌ ENTRA NA SALA, MLK BURRO!")
        return

    canal = ctx.author.voice.channel
    if ctx.voice_client is None:
        await canal.connect()
    elif ctx.voice_client.channel != canal:
        await ctx.voice_client.move_to(canal)

    vc = ctx.voice_client
    arquivo_mp3 = "deigo.mp3"

    if not os.path.exists(arquivo_mp3):
        await ctx.send("⚠️ Arquivo deigo.mp3 não encontrado!")
        return

    vc.stop()
    vc.play(discord.FFmpegPCMAudio(arquivo_mp3))
    await ctx.send("**Deigo** **Deigo** **Deigo**!", view=ControleMusica(ctx))

@bot.command()
async def skip(ctx):
    vc = ctx.voice_client
    guild_id = ctx.guild.id

    if vc is None or not vc.is_playing():
        await ctx.send("❌ NAO TEM MUSICA TOCANDO PRA SKIPAR SUA LOMBRIGA TE LIGA.")
        return

    await ctx.send("⏭️ DJ DEIGO DEIGO PULOU A MUSICA IGUAL PULA NA PICA!")
    vc.stop()

#YT MUSICA
@bot.command()
async def yt(ctx, *, pesquisa):
    await ctx.send(f"🎧 DJ DEIGO DEIGO BUSCANDO no YouTube: **{pesquisa}**...")

    ydl_opts = {"quiet": True, "noplaylist": True, "format": "bestaudio"}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            resultado = ydl.extract_info(f"ytsearch:{pesquisa}", download=False)["entries"][0]
            musica_cache = {"url": resultado["webpage_url"], "titulo": resultado["title"]}
    except Exception as e:
        await ctx.send(f"❌ Erro ao buscar música: {e}")
        return

    guild_id = ctx.guild.id
    # garante que a fila do servidor existe
    if guild_id not in filas:
        filas[guild_id] = []

    # adiciona a música na fila
    filas[guild_id].append({"url": musica_cache["url"], "titulo": musica_cache["titulo"], "ctx": ctx})

    # se for a primeira música, toca imediatamente
    if len(filas[guild_id]) == 1:
        await tocar_proxima(guild_id)
    else:
        await ctx.send(f"➕ DJ DEIGO DEIGO COLOCOU NA FILA: **{musica_cache['titulo']}** (posição {len(filas[guild_id])})")

#amizade

@bot.command()
async def amizade(ctx):
    arquivo = "amizade.png"
    if not os.path.exists(arquivo):
        await ctx.send("⚠️ Arquivo de amizade não encontrado!")
        return

    await ctx.send(content="VOCÊS ME FAZEM MUITO FELIZES❤️❤️❤️❤️", file=discord.File(arquivo))

bot.run(DISCORD_TOKEN)
