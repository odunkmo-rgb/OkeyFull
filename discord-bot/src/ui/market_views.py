import discord
import os
import random
from src.economy.db import (
    MARKET_URUNLER, market_satin_al, envanter_getir, urun_kontrol
)

VIDEO_DOSYALARI = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../attached_assets/Çaycı_Hüseyin_çaylarrrr(360P)_1782411092153.mp4")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../attached_assets/Çocuklar_Duymasın_(Çaylarrr)_Kral_Geri_Döndü(720P_HD)_1782411092227.mp4")),
]

# Başlangıçta path'leri doğrula
for _v in VIDEO_DOSYALARI:
    if not os.path.exists(_v):
        print(f"[UYARI] Video dosyası bulunamadı: {_v}")


def market_ana_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🛍️ Kahvehane Okey Marketi",
        description="Çiplerini harca, masana renk kat!\nBir ürün seçmek için aşağıdaki menüyü kullan.",
        color=0xe67e22
    )
    for anahtar, urun in MARKET_URUNLER.items():
        embed.add_field(
            name=f"{urun['emoji']} {urun['ad']} — {urun['fiyat']:,} 🪙",
            value=urun["aciklama"],
            inline=False
        )
    embed.set_footer(text="Satın almak için menüden ürün seç → Onayla")
    return embed


class MarketSelectMenu(discord.ui.Select):
    def __init__(self):
        secenekler = [
            discord.SelectOption(
                label=urun["ad"],
                value=anahtar,
                description=f"{urun['fiyat']:,} 🪙 — {urun['aciklama'][:80]}",
                emoji=urun["emoji"]
            )
            for anahtar, urun in MARKET_URUNLER.items()
        ]
        super().__init__(
            placeholder="Satın almak istediğin ürünü seç...",
            options=secenekler,
            min_values=1, max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        urun_adi = self.values[0]
        urun = MARKET_URUNLER[urun_adi]
        embed = discord.Embed(
            title=f"{urun['emoji']} {urun['ad']}",
            description=urun["aciklama"],
            color=0x2ecc71
        )
        embed.add_field(name="💰 Fiyat", value=f"{urun['fiyat']:,} 🪙", inline=True)
        embed.add_field(name="🔖 Tür", value="Sürekli" if urun["tur"] == "sürekli" else "Tek Kullanımlık", inline=True)
        embed.set_footer(text="Satın almak için aşağıdaki butona bas.")
        await interaction.response.edit_message(
            embed=embed,
            view=SatinAlOnayla(urun_adi)
        )


class MarketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(MarketSelectMenu())


class SatinAlOnayla(discord.ui.View):
    def __init__(self, urun_adi: str):
        super().__init__(timeout=60)
        self.urun_adi = urun_adi

    @discord.ui.button(label="✅ Satın Al", style=discord.ButtonStyle.success, emoji="🛒")
    async def satin_al(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        await interaction.response.defer(ephemeral=True)

        urun = MARKET_URUNLER.get(self.urun_adi)
        if not urun:
            await interaction.followup.send("❌ Geçersiz ürün.", ephemeral=True)
            return

        basarili, hata = await market_satin_al(uid, self.urun_adi)
        if not basarili:
            await interaction.followup.send(f"❌ {hata}", ephemeral=True)
            return

        embed = discord.Embed(
            title="✅ Satın Alma Başarılı!",
            description=f"{urun['emoji']} **{urun['ad']}** envanterine eklendi!",
            color=0x2ecc71
        )
        embed.set_footer(text="Ürünün efekti oyun içinde otomatik aktif olur.")
        for item in self.children:
            item.disabled = True
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="⬅️ Geri", style=discord.ButtonStyle.secondary)
    async def geri(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=market_ana_embed(), view=MarketView())


class CayIstiyorumView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="☕ Ben de Çay İstiyorum! (Satın Al — 200 🪙)",
        style=discord.ButtonStyle.primary,
        custom_id="cayci_satin_al_btn"
    )
    async def cay_satin_al(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        await interaction.response.defer(ephemeral=True)

        mevcut = await urun_kontrol(uid, "cayci_huseyin")
        if mevcut:
            await interaction.followup.send("☕ Zaten envanterinde **Çaycı Hüseyin Efekti** var!", ephemeral=True)
            return

        basarili, hata = await market_satin_al(uid, "cayci_huseyin")
        if not basarili:
            await interaction.followup.send(f"❌ {hata}", ephemeral=True)
            return

        await interaction.followup.send(
            "☕ **Çaycı Hüseyin Efekti** satın alındı! Her 3 elde bir çay videosu gelecek.",
            ephemeral=True
        )


async def cayci_video_gonder(channel, oyuncu_adlari: dict):
    """
    Çaycı Hüseyin videosu gönder + "Ben de Çay İstiyorum!" butonu ekle.
    oyuncu_adlari: {user_id: ad} sözlüğü
    """
    video_yolu = random.choice(VIDEO_DOSYALARI)
    try:
        file = discord.File(video_yolu)
        adlar = ", ".join(oyuncu_adlari.values()) if oyuncu_adlari else "Oyuncu"
        await channel.send(
            content=f"☕ **Çay Vakti!** {adlar} çay söyledi! 🍵",
            file=file,
            view=CayIstiyorumView()
        )
    except Exception as e:
        await channel.send(f"☕ Çay vakti! (Video yüklenemedi: {e})")
