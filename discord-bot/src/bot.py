import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from src.economy.db import (
    init_db, ensure_oyuncu, get_oyuncu, gunluk_al,
    transfer_cip, get_liderlik, update_cip, vip_mac_oyna,
    get_izin_roller
)
from src.ui.views import LobiView, build_masa_view
from src.ui.render import render_profil
from src.game.manager import game_manager

ADMIN_ROLE_ID = 1513128919182606378
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class OkeyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.lobi_view_registered = False

    async def setup_hook(self):
        await init_db()
        self.add_view(LobiView())

    async def on_ready(self):
        print(f"✅ {self.user} olarak giriş yapıldı!")
        for guild in self.guilds:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"  ✔ {guild.name}: {len(synced)} komut sync edildi.")
        print("✅ Slash komutları senkronize edildi.")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="🎲 Kahvehane Okey | /yardım"
            )
        )

bot = OkeyBot()

def is_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.id == ADMIN_ROLE_ID:
        return True
    if hasattr(interaction.user, "roles"):
        return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)
    return False

# ─── PANEL KOMUTU ────────────────────────────────────────────────────────────

@bot.tree.command(name="okey-paneli-gonder", description="Kahvehane Okey ana panelini gönderir. (Sadece yöneticiler)")
async def okey_panel(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "❌ Bu paneli sadece yöneticiler gönderebilir!", ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📯 Kahvehane Okey Salonu",
        description=(
            "Aşağıdaki butonları kullanarak hemen bir masa kurabilir, "
            "botlara karşı antrenman yapabilir veya istatistiklerini inceleyebilirsin. "
            "**İyi şanslar!**"
        ),
        color=0x2ECC71
    )
    embed.set_footer(text="Kahvehane Okey Salonu • Her zaman açık, her zaman eğlenceli!")
    embed.add_field(
        name="🎮 Nasıl Oynanır?",
        value=(
            "1. Bir masa türü seç ve masaya katıl\n"
            "2. Oyun başlayınca **El Gör** ile taşlarını gör\n"
            "3. Sıra sende: **Talon'dan Çek** → Taş al → **Taş At**\n"
            "4. Elini tamamlayınca **OKEY AÇ!** butonuna bas!"
        ),
        inline=False
    )
    embed.add_field(
        name="💰 Ekonomi",
        value="Başlangıç: **1,000** 🪙 | Günlük: **+500** 🪙 | Kazanma: **+200** 🪙",
        inline=False
    )

    view = LobiView()
    await interaction.response.send_message(embed=embed, view=view)

# ─── OYUN KOMUTLARI ──────────────────────────────────────────────────────────

okey_group = app_commands.Group(name="okey", description="Okey oyun komutları")

@okey_group.command(name="kur", description="Yeni bir özel okey masası kur")
@app_commands.describe(bahis="Bahis miktarı (varsayılan: 0)", sifre="Oda şifresi (isteğe bağlı)")
async def okey_kur(interaction: discord.Interaction, bahis: int = 0, sifre: str = ""):
    await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
    if bahis > 0:
        oyuncu = await get_oyuncu(interaction.user.id)
        if oyuncu.get("cip", 0) < bahis:
            await interaction.response.send_message(
                f"❌ Yeterli çipiniz yok. Mevcut: **{oyuncu.get('cip',0):,}** 🪙", ephemeral=True
            )
            return
    await game_manager.masa_kur(interaction, max_oyuncu=4, bot_modu=False, bahis=bahis)

@okey_group.command(name="katil", description="Belirli bir masaya katıl")
@app_commands.describe(oda_id="Masa ID'si", sifre="Masa şifresi (varsa)")
async def okey_katil(interaction: discord.Interaction, oda_id: str, sifre: str = ""):
    masa_id = oda_id.upper()
    masa = game_manager.masalar.get(masa_id)
    if not masa:
        await interaction.response.send_message(f"❌ `{masa_id}` ID'li masa bulunamadı.", ephemeral=True)
        return
    if masa.sifreli and masa.sifre != sifre:
        await interaction.response.send_message("❌ Yanlış şifre!", ephemeral=True)
        return
    await game_manager.masaya_katil(interaction, masa_id)

@okey_group.command(name="hizli-mac", description="Bekleyen bir masaya otomatik katıl")
async def okey_hizli(interaction: discord.Interaction):
    await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
    from src.game.okey_engine import GameState
    uygun = [
        mid for mid, masa in game_manager.masalar.items()
        if masa.durum == GameState.WAITING
        and interaction.user.id not in masa.oyuncular
        and masa.bahis == 0
    ]
    if not uygun:
        await interaction.response.send_message(
            "❌ Şu an bekleyen uygun masa yok. `/okey kur` ile yeni masa açabilirsiniz!", ephemeral=True
        )
        return
    await game_manager.masaya_katil(interaction, uygun[0])

@okey_group.command(name="izle", description="Devam eden bir masayı izle")
@app_commands.describe(oda_id="Masa ID'si")
async def okey_izle(interaction: discord.Interaction, oda_id: str):
    masa_id = oda_id.upper()
    masa = game_manager.masalar.get(masa_id)
    if not masa:
        await interaction.response.send_message(f"❌ `{masa_id}` ID'li masa bulunamadı.", ephemeral=True)
        return
    from src.game.okey_engine import GameState
    if masa.durum != GameState.PLAYING:
        await interaction.response.send_message("❌ Bu masa henüz başlamadı.", ephemeral=True)
        return
    if interaction.user.id in masa.oyuncular:
        await interaction.response.send_message("❌ Bu masanın oyuncususunuz, izleyici olamazsınız!", ephemeral=True)
        return
    if interaction.user.id not in masa.izleyiciler:
        masa.izleyiciler.append(interaction.user.id)
    oyuncu_listesi = "\n".join(
        f"{'🤖' if uid < 0 else '👤'} {ad}"
        + (" ⏳" if uid == masa.siradaki_oyuncu_id() else "")
        for uid, ad in masa.oyuncu_adlari.items()
    )
    embed = discord.Embed(
        title=f"👁️ Masa `{masa_id}` — İzleyici Modu",
        description=(
            f"**Oyuncular:**\n{oyuncu_listesi}\n\n"
            f"**Okey Taşı:** {game_manager._okey_str(masa)}\n"
            f"**Talon:** {len(masa.talon)} taş kaldı"
        ),
        color=0x9b59b6
    )
    if masa.cop_yigi:
        embed.add_field(name="♻️ Son Atılan", value=str(masa.cop_yigi[-1]), inline=True)
    embed.set_footer(text="İzleyici modundasınız — oyunculara oyun bilgisi görünmez.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@okey_group.command(name="ayril", description="Masadan veya lobiden ayrıl")
async def okey_ayril(interaction: discord.Interaction):
    mid = game_manager._masa_bul_oyuncu(interaction.user.id)
    if not mid:
        await interaction.response.send_message("❌ Herhangi bir masada değilsiniz.", ephemeral=True)
        return
    await game_manager.masadan_ayril(interaction, mid)

bot.tree.add_command(okey_group)

# ─── OKEY ROL KOMUTU (sadece yönetici) ───────────────────────────────────────

@bot.tree.command(
    name="okey-rol",
    description="Okey butonlarını kullanabilecek rolleri belirler."
)
@app_commands.describe(
    roller="İzin verilecek rol ID'leri — boşlukla ayır. Boş bırakılırsa herkes erişebilir."
)
async def okey_rol(interaction: discord.Interaction, roller: str = ""):
    if interaction.user.id != 1513128919182606378:
        await interaction.response.send_message(
            "❌ Bu komutu sadece bot yöneticisi kullanabilir.", ephemeral=True
        )
        return

    guild_id = interaction.guild_id
    if not guild_id:
        await interaction.response.send_message("❌ Bu komut sunucuda kullanılmalı.", ephemeral=True)
        return

    if not roller.strip():
        await game_manager.izin_rol_guncelle(guild_id, [])
        await interaction.response.send_message(
            "✅ **Rol kısıtlaması kaldırıldı.**\n"
            "Artık sunucudaki **herkes** Okey butonlarını kullanabilir.",
            ephemeral=True
        )
        return

    # ID'leri parse et
    gecerli_ids = []
    hatali = []
    for parca in roller.split():
        parca = parca.strip().lstrip("<@&>")
        try:
            rid = int(parca)
            rol = interaction.guild.get_role(rid)
            if rol:
                gecerli_ids.append(rid)
            else:
                hatali.append(parca)
        except ValueError:
            hatali.append(parca)

    if not gecerli_ids:
        await interaction.response.send_message(
            f"❌ Geçerli rol ID'si bulunamadı. Girilen: `{roller}`\n"
            "Sunucudaki rol ID'lerini kullandığınızdan emin olun.",
            ephemeral=True
        )
        return

    await game_manager.izin_rol_guncelle(guild_id, gecerli_ids)

    mevcut_roller = interaction.guild
    rol_isimleri = []
    for rid in gecerli_ids:
        rol = interaction.guild.get_role(rid)
        if rol:
            rol_isimleri.append(f"• {rol.mention} (`{rid}`)")

    hata_str = f"\n⚠️ Bulunamayan ID'ler: `{'`, `'.join(hatali)}`" if hatali else ""
    await interaction.response.send_message(
        f"✅ **Okey izin rolleri güncellendi!**\n\n"
        f"**Bu rollere sahip üyeler Okey oynayabilir:**\n"
        + "\n".join(rol_isimleri)
        + hata_str
        + "\n\n💡 *Sıfırlamak için `/okey-rol` komutunu boş bırakarak çalıştırın.*",
        ephemeral=True
    )

# ─── EKONOMİ KOMUTLARI ───────────────────────────────────────────────────────

@bot.tree.command(name="cuzdan", description="Mevcut çip ve seviye bilgini gör")
async def cuzdan(interaction: discord.Interaction):
    oyuncu = await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
    embed = discord.Embed(title="💼 Cüzdanım", color=0xf1c40f)
    embed.add_field(name="🪙 Çip", value=f"{oyuncu.get('cip', 0):,}", inline=True)
    embed.add_field(name="⭐ Seviye", value=str(oyuncu.get("seviye", 1)), inline=True)
    embed.add_field(name="🏆 Galibiyet", value=str(oyuncu.get("galibiyet", 0)), inline=True)
    embed.set_footer(text="Günlük 500 çip için /gunluk komutunu kullanın!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="gunluk", description="24 saatte bir ücretsiz çip ödülü al")
async def gunluk(interaction: discord.Interaction):
    await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
    basarili, miktar, kalan = await gunluk_al(interaction.user.id)
    if basarili:
        embed = discord.Embed(
            title="🎁 Günlük Ödül!",
            description=f"**+{miktar:,} 🪙** hesabınıza yatırıldı!",
            color=0x2ecc71
        )
        embed.set_footer(text="Yarın tekrar gelin!")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="⏰ Henüz Erken!",
            description=f"Günlük ödülünüzü almak için **{kalan}** beklemeniz gerekiyor.",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="gonder", description="Başka bir kullanıcıya çip gönder")
@app_commands.describe(kullanici="Çip gönderilecek kişi", miktar="Gönderilecek çip miktarı")
async def gonder(interaction: discord.Interaction, kullanici: discord.Member, miktar: int):
    if kullanici.id == interaction.user.id:
        await interaction.response.send_message("❌ Kendinize çip gönderemezsiniz!", ephemeral=True)
        return
    if kullanici.bot:
        await interaction.response.send_message("❌ Botlara çip gönderemezsiniz!", ephemeral=True)
        return
    await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
    await ensure_oyuncu(kullanici.id, kullanici.display_name)
    basarili, hata = await transfer_cip(interaction.user.id, kullanici.id, miktar)
    if basarili:
        embed = discord.Embed(
            title="💸 Transfer Başarılı!",
            description=f"**{miktar:,} 🪙** → {kullanici.mention}",
            color=0x2ecc71
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"❌ {hata}", ephemeral=True)

@bot.tree.command(name="market", description="Kozmetik ürünler marketi")
async def market(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛍️ Kahvehane Okey Marketi",
        description="Çiplerini harca, masanı özelleştir!",
        color=0xe67e22
    )
    urunler = [
        ("🟩 Yeşil Masa Örtüsü", "Varsayılan", "Ücretsiz"),
        ("⬛ VIP Siyah Masa", "Prestige", "2,000 🪙"),
        ("🟥 Kırmızı Masa", "Ateşli", "1,500 🪙"),
        ("🎴 Altın Taş Seti", "Parlak taşlar", "5,000 🪙"),
        ("🌟 Altın Çerçeve", "Profil süsü", "3,000 🪙"),
    ]
    for ad, aciklama, fiyat in urunler:
        embed.add_field(name=f"{ad} — {fiyat}", value=aciklama, inline=False)
    embed.set_footer(text="Market yakında tam işlevli olacak! 🚀")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ─── SOSYAL KOMUTLAR ─────────────────────────────────────────────────────────

@bot.tree.command(name="profil", description="Okey istatistik kartını gör")
@app_commands.describe(kullanici="Profili görülecek kişi (boş bırakırsan kendi profilin)")
async def profil(interaction: discord.Interaction, kullanici: discord.Member = None):
    from src.ui.views import _seviye_adi
    from src.economy.db import get_liderlik
    hedef   = kullanici or interaction.user
    oyuncu  = await ensure_oyuncu(hedef.id, hedef.display_name)
    img_buf = render_profil(oyuncu)
    file    = discord.File(img_buf, filename="profil.png")

    lider_tam = await get_liderlik("cip", 10)
    siralam   = next((i + 1 for i, o in enumerate(lider_tam) if o["user_id"] == hedef.id), "10+")
    lider_top3 = lider_tam[:3]

    toplam    = oyuncu.get("toplam_mac", 0)
    galibiyet = oyuncu.get("galibiyet", 0)
    yenilgi   = oyuncu.get("yenilgi", 0)
    bera      = oyuncu.get("beraberlik", 0)
    oran      = f"%{(galibiyet / toplam * 100):.1f}" if toplam > 0 else "%0"
    cip       = oyuncu.get("cip", 0)
    seviye    = oyuncu.get("seviye", 1)

    embed = discord.Embed(title="📇 KAHVEHANE OKEY — OYUNCU PROFİLİ", color=0xf1c40f)
    embed.set_thumbnail(url=hedef.display_avatar.url)
    embed.description = (
        f"👤 **Oyuncu:** {hedef.mention}\n\n"
        f"🪙 **Mevcut Çip:** `{cip:,} 🪙`\n"
        f"🏆 **Lig / Seviye:** `{_seviye_adi(seviye)} ✨`\n\n"
        f"📊 **İstatistikler:**\n"
        f"├ 🟢 **Galibiyet:** `{galibiyet} Oyun`\n"
        f"├ 🟡 **Beraberlik:** `{bera} Oyun`\n"
        f"└ 🔴 **Mağlubiyet:** `{yenilgi} Oyun`\n"
        f"📈 **Kazanma Oranı:** `{oran}`\n\n"
        f"🥇 **Sunucu Sıralaması:** `#{siralam}. Sırada`"
    )
    if lider_top3:
        mdl = ["1️⃣", "2️⃣", "3️⃣"]
        ls  = "\n".join(
            f"{mdl[i]} `{o.get('ad','?')}` — {o.get('cip', 0):,} Çip"
            for i, o in enumerate(lider_top3)
        )
        embed.add_field(name="👑 TOP 3 LİDERLİK TABLOSU", value=ls, inline=False)
    embed.set_image(url="attachment://profil.png")
    embed.set_footer(text="Bu profil kartı size özeldir." if not kullanici else f"{hedef.display_name} profilini görüyorsunuz.")
    await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

@bot.tree.command(name="liderlik", description="Sunucu liderlik tablosu")
@app_commands.describe(kategori="Sıralama kategorisi")
@app_commands.choices(kategori=[
    app_commands.Choice(name="En Zengin (Çip)", value="cip"),
    app_commands.Choice(name="En Çok Kazanan", value="galibiyet"),
    app_commands.Choice(name="En Çok Oynayan", value="mac"),
])
async def liderlik(interaction: discord.Interaction, kategori: str = "cip"):
    liste = await get_liderlik(kategori, 10)
    basliklar = {"cip": "🪙 En Zengin", "galibiyet": "🏆 En Çok Kazanan", "mac": "🎮 En Çok Oynayan"}
    degerler = {"cip": lambda o: f"{o.get('cip',0):,} 🪙", "galibiyet": lambda o: f"{o.get('galibiyet',0)} galibiyet", "mac": lambda o: f"{o.get('toplam_mac',0)} maç"}

    embed = discord.Embed(title=f"🏅 Liderlik Tablosu — {basliklar.get(kategori, '')}", color=0xf1c40f)
    medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    satirlar = []
    for i, o in enumerate(liste):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        satirlar.append(f"{medal} **{o.get('ad', 'Bilinmiyor')}** — {degerler[kategori](o)}")
    embed.description = "\n".join(satirlar) if satirlar else "Henüz kayıt yok."
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="yardim", description="Okey botu komutları ve oyun kuralları rehberi")
async def yardim(interaction: discord.Interaction):
    embeds = []

    # ── 1. Komutlar ──────────────────────────────────────────────────────────
    e1 = discord.Embed(
        title="📖 Kahvehane Okey — Yardım Rehberi",
        description="Tüm komutlar ve tam oyun kuralları aşağıda:",
        color=0x3498db
    )
    e1.add_field(
        name="🎮 Oyun Komutları",
        value=(
            "`/okey kur` — Özel masa aç\n"
            "`/okey katil` — Masaya katıl\n"
            "`/okey hizli-mac` — Hızlı maça atıl (bot dolu)\n"
            "`/okey izle` — Maç izle\n"
            "`/okey ayril` — Masadan ayrıl"
        ),
        inline=True
    )
    e1.add_field(
        name="💰 Ekonomi & Sosyal",
        value=(
            "`/cuzdan` — Çip & seviye\n"
            "`/gunluk` — Günlük 500 🪙 ödül\n"
            "`/gonder @kişi miktar` — Çip gönder\n"
            "`/profil` — İstatistik kartı\n"
            "`/liderlik` — Sıralama tablosu"
        ),
        inline=True
    )

    # ── 2. Temel Kurallar ────────────────────────────────────────────────────
    e1.add_field(
        name="━━━━━━━━━━━━━━━━━━━━━━━━",
        value="** **",
        inline=False
    )
    e1.add_field(
        name="🎲 Temel Oyun Kuralları",
        value=(
            "**Taş seti:** 106 taş — 4 renk × 13 sayı × 2 adet + 2 sahte okey\n"
            "**Başlangıç:** İlk oyuncu **15 taş**, diğerleri **14 taş** alır\n"
            "**Her tur:** Talon'dan veya son atılan taştan **1 çek**, ardından **1 at**\n"
            "**İlk oyuncu:** Taş çekmeden doğrudan atar (15 taşı var)\n"
            "**Amaç:** 14 taşı geçerli perlere dizerek **OKEY AÇ!** butonuna bas\n"
            "**Süre:** Her tur için **5 dakika** — aşılırsa diskalifiye"
        ),
        inline=False
    )

    # ── 3. Okey Taşı Belirleme ───────────────────────────────────────────────
    e1.add_field(
        name="🃏 Okey Taşı Nasıl Belirlenir?",
        value=(
            "Oyun başında bir **gösterge taşı** açılır.\n"
            "Gösterge taşının **bir üstü** (aynı renk) o elin **okey taşıdır**.\n\n"
            "**Örnek:** Gösterge = 🔴4 → Okey taşı = 🔴5\n"
            "**Sarma:** Gösterge = 🔵13 → Okey taşı = 🔵1"
        ),
        inline=False
    )
    embeds.append(e1)

    # ── 4. Joker Sistemi ─────────────────────────────────────────────────────
    e2 = discord.Embed(
        title="🃏 Joker Sistemi — Sahte Okey vs Gerçek Okey",
        color=0xe67e22
    )
    e2.add_field(
        name="⭐ Gerçek Okey Taşı (Fiziksel kart)",
        value=(
            "O elin okey taşı (ör: 🔴5) **gerçek wildcard'dır.**\n"
            "• Her taşın yerine her perde kullanılabilir\n"
            "• Atarken **⭐ Okey** butonunu kullan\n"
            "• Opsiyonel olarak hangi taşın yerine kullandığını belirtebilirsin"
        ),
        inline=False
    )
    e2.add_field(
        name="🃏 Sahte Okey (Üzerinde sayı/renk olmayan özel taş)",
        value=(
            "Sahte okey **wildcard DEĞİLDİR.**\n"
            "Sahte okey, **her zaman o elin okey taşının kimliğini** taşır.\n\n"
            "**Örnek:** Okey taşı 🔴5 ise →\n"
            "• Sahte okey = 🔴5 olarak sayılır\n"
            "• Sadece 🔴5'e ihtiyaç duyulan perlerde kullanılabilir\n"
            "  *(🔴3 - 🔴4 - SahteOkey = 🔴3-🔴4-🔴5 ✅)*\n"
            "• 🔴1 yerine kullanamazsın ❌\n\n"
            "Atarken **🃏 Joker Ata** butonunu kullan — renk/sayı sorulmaz, otomatik atılır."
        ),
        inline=False
    )
    embeds.append(e2)

    # ── 5. Geçerli Perler ────────────────────────────────────────────────────
    e3 = discord.Embed(
        title="📐 Geçerli Perler (Setler)",
        color=0x2ecc71
    )
    e3.add_field(
        name="🔗 Seri (Aynı Renk, Ardışık Sayı) — min 3 taş",
        value=(
            "🔴3 🔴4 🔴5 ✅\n"
            "🟡7 🟡8 🟡9 🟡10 ✅\n"
            "🔴3 🔴4 ⭐*(okey=🔴5)* ✅\n"
            "🔴12 🔴13 🔴1 ✅  *(13→1 sarma)*"
        ),
        inline=True
    )
    e3.add_field(
        name="🔀 Grup (Aynı Sayı, Farklı Renk) — min 3 taş",
        value=(
            "🔴7 🟡7 🔵7 ✅\n"
            "🔴13 🟡13 🔵13 ⚫13 ✅\n"
            "🔴5 🟡5 ⭐*(okey=🔵5)* ✅\n"
            "🔴3 🔴3 ❌  *(aynı renk olamaz)*"
        ),
        inline=True
    )
    e3.add_field(
        name="🎊 7 Çift (Özel Kazanma)",
        value=(
            "14 taşını **7 eşleşik çift** oluşturacak şekilde dizersen kazanırsın.\n"
            "Gerçek okey taşı (wildcard) eksik çiftleri tamamlayabilir.\n"
            "**Bonus: +350 🪙**"
        ),
        inline=False
    )
    embeds.append(e3)

    # ── 6. Kazanma & Bonuslar ────────────────────────────────────────────────
    e4 = discord.Embed(
        title="🏆 Kazanma Yolları & Bonuslar",
        color=0xf1c40f
    )
    e4.add_field(
        name="Kazanma Koşulu",
        value=(
            "Sıra sende olduğunda **OKEY AÇ!** butonuna bas.\n"
            "15 taşın varsa (çektikten sonra) sistem otomatik en iyi atılacak taşı bulur.\n"
            "14 taşın geçerli perlere bölünebiliyorsa → **KAZANDIN!**"
        ),
        inline=False
    )
    e4.add_field(
        name="🏆 Normal Kazanma",
        value="+200 🪙",
        inline=True
    )
    e4.add_field(
        name="🌟 Çifte Okey",
        value="Sahte okeyı **son taş** olarak atarak kazanma → +500 🪙",
        inline=True
    )
    e4.add_field(
        name="🎊 Yedi Çift",
        value="7 eşleşik çiftle bitirme → +350 🪙",
        inline=True
    )
    e4.add_field(
        name="📱 Butonlar",
        value=(
            "**✅ Masaya Katıl** — Masaya gir\n"
            "**🀄 Perleri Diz** — Eli per düzenine göre sırala (iki mod var)\n"
            "**👁️ El Gör** — Taşlarını görsel olarak gör\n"
            "**🎴 Talon'dan Çek** — Talon'dan taş çek\n"
            "**♻️ Son Taşı Al** — Önceki oyuncunun attığı taşı al\n"
            "**🗑️ Taş At** — Elinizden taş at (renk + sayı gir)\n"
            "**🃏 Joker Ata** — Sahte okey veya gerçek okey taşını at\n"
            "**🎉 OKEY AÇ!** — Okey aç ve kazandığını kontrol et\n"
            "**🚪 Masadan Ayrıl** — Masadan çık"
        ),
        inline=False
    )
    e4.set_footer(text="İyi eğlenceler! | Sorun için sunucu yönetimine ulaşın.")
    embeds.append(e4)

    await interaction.response.send_message(embeds=embeds, ephemeral=True)

# ─── HATA YÖNETİMİ ───────────────────────────────────────────────────────────

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = f"❌ Bir hata oluştu: {str(error)}"
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception:
        pass

def main():
    if not TOKEN:
        print("❌ DISCORD_BOT_TOKEN secret'ı ayarlanmamış! Replit Secrets'a ekleyin.")
        raise SystemExit(1)
    bot.run(TOKEN, log_handler=None)

if __name__ == "__main__":
    main()
