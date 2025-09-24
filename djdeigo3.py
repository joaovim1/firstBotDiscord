import asyncio
import os

import discord
import spotipy
import yt_dlp
from discord.ext import commands
from openai import OpenAI
from spotipy.oauth2 import SpotifyClientCredentials

# ===== CONFIGURAÇÕES E TOKENS =====
DISCORD_TOKEN = "MTQyMDA1NzczNjk4NDY2MjIwOA.GAjar1.ITqezY3qhcbsgeij4491esrrh-BJsXfG9yJGI0"
SPOTIFY_CLIENT_ID = "90c132a779ce43ee981ad6eef6425dd5"
SPOTIFY_CLIENT_SECRET = "b1432c41ec8c4232a3ead35a93c58e3a"
OPENAI_API_KEY = "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"

# Inicializa clientes
client = OpenAI(api_key=OPENAI_API_KEY)

spotify_auth = SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
)
spotify = spotipy.Spotify(client_credentials_manager=spotify_auth)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== CACHE E FILA =====
cache_musicas = {}
filas = {}


# ===== CONTROLE DE MÚSICA =====
class ControleMusica(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="⏭️ Pular", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.ctx.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ DJ DEIGO DEIGO PULOU A MUSICA IGUAL PULA NA PIKA!️")
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
            filas[self.ctx.guild.id] = []
            await vc.disconnect()
            await interaction.response.send_message("🛑 DJ DEIGO DEIGO SAIU VAZADO.")
        else:
            await interaction.response.send_message("❌ DJ DEIGO DEIGO NAO TA NA SALA ANIMALLLL.", ephemeral=True)


# ===== FUNÇÕES AUXILIARES =====
async def gerar_pesquisa(mensagem):
    try:
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                 "content": "Você é um assistente musical. Dê apenas o nome da música e artista, sem explicações."},
                {"role": "user", "content": mensagem}
            ]
        )
        return resposta.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro OpenAI: {e}")
        return mensagem


async def tocar_proxima(guild_id):
    if guild_id not in filas or not filas[guild_id]:
        return

    musica = filas[guild_id][0]
    ctx = musica["ctx"]
    titulo = musica["titulo"]
    url = musica.get("url")
    caminho_local = musica.get("caminho_local")
    infinito = musica.get("infinito", False)

    if ctx.voice_client is None:
        await ctx.author.voice.channel.connect()
    elif ctx.voice_client.channel != ctx.author.voice.channel:
        await ctx.voice_client.move_to(ctx.author.voice.channel)

    vc = ctx.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        return

    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

    if infinito:
        ffmpeg_opts['before_options'] += ' -stream_loop -1'

    try:
        if url:
            ydl_opts = {"quiet": True, "format": "bestaudio/best", "extract_flat": True,
                        "force_generic_extractor": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_source = discord.FFmpegPCMAudio(info["url"], **ffmpeg_opts)
                thumbnail_url = info.get("thumbnail") if "thumbnail" in info else None
        else:  # É um arquivo local
            audio_source = discord.FFmpegPCMAudio(caminho_local, **ffmpeg_opts)
            thumbnail_url = None

        embed = discord.Embed(
            title="🎶 DJ DEIGO DEIGO TOCANDO UMA",
            description=f"**{titulo}**",
            color=discord.Color.from_rgb(30, 215, 96)
        )
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        embed.set_footer(text="DEIGO DEIGO DEIGO DEIGO DEIGO DEIGO DEIGO DEIGO DEIGO DEIGO")

    except Exception as e:
        await ctx.send(f"❌ DEU MERDA : {e}")
        return

    def depois(err):
        if err:
            print(f"DEU MERDA NA MUSICA: {err}")
        if filas[guild_id]:
            filas[guild_id].pop(0)
        asyncio.run_coroutine_threadsafe(tocar_proxima(guild_id), bot.loop)

    vc.play(audio_source, after=depois)
    await ctx.send(embed=embed, view=ControleMusica(ctx))


async def adicionar_fila(ctx, titulo, url=None, caminho_local=None, infinito=False):
    guild_id = ctx.guild.id
    if guild_id not in filas:
        filas[guild_id] = []

    item_fila = {"titulo": titulo, "ctx": ctx, "infinito": infinito}
    if url:
        item_fila["url"] = url
    if caminho_local:
        item_fila["caminho_local"] = caminho_local

    # Conectar o bot se ele não estiver em um canal
    if ctx.voice_client is None:
        await ctx.author.voice.channel.connect()

    filas[guild_id].append(item_fila)

    # Inicia a reprodução se a fila estava vazia
    if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
        await tocar_proxima(guild_id)
    else:
        await ctx.send(f"➕ DJ DEIGO DEIGO COLOCOU NA FILA: **{titulo}** (posição {len(filas[guild_id])})")


# ===== COMANDOS =====
@bot.command()
async def gpt(ctx, *, pedido):
    """Busca música com OpenAI e adiciona na fila"""
    if ctx.author.voice is None:
        await ctx.send("❌ ENTRA NA SALA, MLK BURRO!")
        return

    await ctx.send(f"🎧 DJ DEIGO DEIGO BUSCANDO: **{pedido}**...")

    pesquisa = await gerar_pesquisa(pedido)

    ydl_opts = {"quiet": True, "noplaylist": True, "format": "bestaudio/best"}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            resultado = ydl.extract_info(f"ytsearch:{pesquisa} official audio", download=False)["entries"][0]
            titulo_final, url_final = resultado["title"], resultado["webpage_url"]
            await adicionar_fila(ctx, titulo_final, url=url_final)
    except IndexError:
        await ctx.send("❌ Não encontrei nenhum resultado no YouTube para essa música.")
    except Exception as e:
        await ctx.send(f"❌ Erro ao buscar no YouTube: {e}")


@bot.command()
async def sp(ctx, *, pedido):
    """Busca música do Spotify e toca via YouTube"""
    if ctx.author.voice is None:
        await ctx.send("❌ ENTRA NA SALA, MLK BURRO!")
        return

    await ctx.send(f"🎧 DJ DEIGO DEIGO BUSCANDO no Spotify: **{pedido}**...")

    try:
        # Verifica se o pedido é um link
        if "googleusercontent.com/spotify.com" in pedido:
            # Extrai o ID da música do link para busca precisa
            track_id = pedido.split('/')[-1].split('?')[0]
            track = spotify.track(track_id)
        else:
            # Se for texto, faz a busca
            resultado_spotify = spotify.search(q=pedido, type="track", limit=1)
            tracks = resultado_spotify['tracks']['items']
            if not tracks:
                await ctx.send("❌ Não encontrei essa música no Spotify.")
                return
            track = tracks[0]

        # Extrai nome da música e artistas
        artistas = ", ".join([a['name'] for a in track['artists']])
        titulo_busca = f"{track['name']} - {artistas} official audio"

        # Busca no YouTube com o nome completo
        ydl_opts = {"quiet": True, "noplaylist": True, "format": "bestaudio/best"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            yt_result = ydl.extract_info(f"ytsearch:{titulo_busca}", download=False)["entries"][0]
            titulo_final, url_final = yt_result["title"], yt_result["webpage_url"]

        await adicionar_fila(ctx, titulo_final, url=url_final)

    except Exception as e:
        await ctx.send(f"❌ Ocorreu um erro ao buscar no Spotify: {e}")


@bot.command()
async def fila(ctx):
    """Mostra a fila de músicas"""
    guild_id = ctx.guild.id
    if guild_id not in filas or not filas[guild_id]:
        await ctx.send("🎵 Fila vazia.")
        return

    lista = "\n".join([f"{i + 1}. {m['titulo']}" for i, m in enumerate(filas[guild_id])])
    await ctx.send(f"📜 **Fila de músicas:**\n{lista}")


@bot.command()
async def deigo(ctx):
    if ctx.author.voice is None:
        await ctx.send("❌ ENTRA NA SALA, MLK BURRO!")
        return

    arquivo_mp3 = "deigo.mp3"
    if not os.path.exists(arquivo_mp3):
        await ctx.send("⚠️ Arquivo deigo.mp3 não encontrado!")
        return

    await adicionar_fila(ctx, "deigo.mp3", caminho_local=arquivo_mp3, infinito=True)
    await ctx.send("**Deigo** **Deigo** **Deigo**!")


@bot.command()
async def pinote(ctx):
    if ctx.author.voice is None:
        await ctx.send("❌ ENTRA NA SALA, MLK BURRO!")
        return

    arquivo_mp3 = "pinote.mp3"
    if not os.path.exists(arquivo_mp3):
        await ctx.send("⚠️ Arquivo pinote.mp3 não encontrado!")
        return

    await adicionar_fila(ctx, "pinote.mp3", caminho_local=arquivo_mp3, infinito=True)
    await ctx.send("😭😭😭😭😭😭😭😭😭😭")


@bot.command()
async def skip(ctx):
    """Pula a música atual"""
    vc = ctx.voice_client
    if vc is None or not vc.is_playing():
        await ctx.send("❌ NAO TEM MUSICA TOCANDO PRA SKIPAR SUA LOMBRIGA TE LIGA.")
        return
    vc.stop()
    await ctx.send("⏭️ DJ DEIGO DEIGO PULOU A MUSICA IGUAL PULA NA PIKA!")


@bot.command()
async def amizade(ctx):
    """Envia uma imagem de amizade"""
    arquivo = "amizade.png"
    if not os.path.exists(arquivo):
        await ctx.send("⚠️XI")
        return

    await ctx.send(content="VOCÊS ME FAZEM MUITO FELIZES❤️❤️❤️❤️", file=discord.File(arquivo))


bot.run(DISCORD_TOKEN)