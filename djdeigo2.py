import asyncio

import discord
import spotipy
import yt_dlp
from discord.ext import commands
from openai import OpenAI
from spotipy.oauth2 import SpotifyClientCredentials

# ===== CONFIGURAÇÕES =====
DISCORD_TOKEN = "MTQyMDA1NzczNjk4NDY2MjIwOA.GAjar1.ITqezY3qhcbsgeij4491esrrh-BJsXfG9yJGI0"
SPOTIFY_CLIENT_ID = "90c132a779ce43ee981ad6eef6425dd5"
SPOTIFY_CLIENT_SECRET = "b1432c41ec8c4232a3ead35a93c58e3a"
SPOTIFY_REDIRECT_URI = "http://localhost:8888/callback"

# Inicializa clientes
client = OpenAI()

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
cache_musicas = {}  # {"chave": {"url": str, "titulo": str}}
filas = {}  # {"guild_id": [{"url": str, "titulo": str, "ctx": ctx}]}

# ===== CONTROLE DE MÚSICA =====
class ControleMusica(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.button(label="⏭️ Pular", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction, button):
        vc = self.ctx.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏭️ DJ DEIGO DEIGO PULOU A MUSICA IGUAL PULA NA PIKA.")
        else:
            await interaction.response.send_message("❌ Nenhuma música tocando.", ephemeral=True)

    @discord.ui.button(label="⏯️ Pausar/Continuar", style=discord.ButtonStyle.primary)
    async def pausar(self, interaction, button):
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
    async def parar(self, interaction, button):
        vc = self.ctx.voice_client
        if vc:
            filas[self.ctx.guild.id] = []
            await vc.disconnect()
            await interaction.response.send_message("🛑 DJ DEIGO DEIGO SAIU VAZADO.")
        else:
            await interaction.response.send_message("❌ DJ DEIGO DEIGO NAO TA NA SALA.", ephemeral=True)

# ===== FUNÇÕES AUXILIARES =====
async def gerar_pesquisa(mensagem):
    try:
        resposta = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {"role": "system", "content": "Você é um assistente musical. Dê apenas o nome da música e artista, sem explicações."},
                {"role": "user", "content": mensagem}
            ]
        )
        return resposta.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro OpenAI: {e}")
        return mensagem  # fallback: usar texto do usuário

async def tocar_proxima(guild_id):
    if guild_id not in filas or not filas[guild_id]:
        return

    musica = filas[guild_id][0]
    ctx = musica["ctx"]
    url = musica["url"]
    titulo = musica["titulo"]

    if ctx.voice_client is None:
        await ctx.author.voice.channel.connect()
    vc = ctx.voice_client

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
        if filas[guild_id]:
            filas[guild_id].pop(0)
        asyncio.run_coroutine_threadsafe(tocar_proxima(guild_id), bot.loop)

    vc.play(discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts), after=depois)
    await ctx.send(f"🎶 DJ DEIGO DEIGO Tocando: **{titulo}**", view=ControleMusica(ctx))

# ===== COMANDOS =====
async def adicionar_fila(ctx, titulo, url):
    guild_id = ctx.guild.id
    if guild_id not in filas:
        filas[guild_id] = []

    filas[guild_id].append({"url": url, "titulo": titulo, "ctx": ctx})
    if len(filas[guild_id]) == 1:
        await tocar_proxima(guild_id)
    else:
        await ctx.send(f"➕ DJ DEIGO DEIGO COLOCOU NA FILA: **{titulo}** (posição {len(filas[guild_id])})")

# !musica usando OpenAI
@bot.command()
async def musica(ctx, *, pedido):
    await ctx.send(f"🎧 DJ DEIGO DEIGO BUSCANDO...")
    pesquisa = await gerar_pesquisa(pedido)

    ydl_opts = {"quiet": True, "noplaylist": True, "format": "bestaudio"}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        resultado = ydl.extract_info(f"ytsearch:{pesquisa}", download=False)["entries"][0]
        titulo, url = resultado["title"], resultado["webpage_url"]

    await adicionar_fila(ctx, titulo, url)

# !yt busca direto no YouTube
@bot.command()
async def yt(ctx, *, pesquisa):
    await ctx.send("🎧 DJ DEIGO DEIGO BUSCANDO no YouTube...")
    ydl_opts = {"quiet": True, "noplaylist": True, "format": "bestaudio"}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        resultado = ydl.extract_info(f"ytsearch:{pesquisa}", download=False)["entries"][0]
        titulo, url = resultado["title"], resultado["webpage_url"]

    await adicionar_fila(ctx, titulo, url)


# !sp busca no Spotify e toca via YouTube
@bot.command()
async def sp(ctx, *, pesquisa):
    await ctx.send("🎧 DJ DEIGO DEIGO BUSCANDO no Spotify...")

    try:
        # Buscar no Spotify
        resultado = spotify.search(q=pesquisa, type="track", limit=1)
        tracks = resultado['tracks']['items']
        if not tracks:
            await ctx.send("❌ TEM NADA DISSO.")
            return

        track = tracks[0]

        # Construir título completo com todos os artistas
        artistas = ", ".join([a['name'] for a in track['artists']])
        titulo_busca = f"{track['name']} - {artistas} audio"

        # Procurar no YouTube
        ydl_opts = {"quiet": True, "noplaylist": True, "format": "bestaudio"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            yt_result = ydl.extract_info(f"ytsearch:{titulo_busca}", download=False)["entries"][0]
            titulo_final, url_final = yt_result["title"], yt_result["webpage_url"]

        # Adicionar na fila
        await adicionar_fila(ctx, titulo_final, url_final)

    except Exception as e:
        await ctx.send(f"❌ DEU RUIM: {e}")


# !fila mostra a fila
@bot.command()
async def fila(ctx):
    guild_id = ctx.guild.id
    if guild_id not in filas or not filas[guild_id]:
        await ctx.send("🎵 Fila vazia.")
        return

    lista = "\n".join([f"{i+1}. {m['titulo']}" for i, m in enumerate(filas[guild_id])])
    await ctx.send(f"📜 **Fila de músicas:**\n{lista}")

# !skip pular música
@bot.command()
async def skip(ctx):
    vc = ctx.voice_client
    if vc is None or not vc.is_playing():
        await ctx.send("❌ Nenhuma música tocando.")
        return
    vc.stop()
    await ctx.send("⏭️ DJ DEIGO DEIGO PULOU A MUSICA IGUAL PULA NA PIKA.")

bot.run(DISCORD_TOKEN)
