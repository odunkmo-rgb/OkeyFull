import discord
import os
import random
from src.economy.db import (
    MARKET_URUNLER, OKEY_FALLARI, SANS_KUTULARI, SANS_KUTUSU_AGIRLIKLARI,
    market_satin_al, envanter_getir, urun_kontrol, update_cip
)

_UI_DIR  = os.path.dirname(os.path.abspath(__file__))
_BOT_DIR = os.path.dirname(os.path.dirname(_UI_DIR))

VIDEO_DOSYALARI = [
    os.path.join(_BOT_DIR, "assets", "cayci_huseyin_1.mp4"),
    os.path.join(_BOT_DIR, "assets", "cayci_huseyin_2.mp4"),
]

for _v in VIDEO_DOSYALARI:
    if not os.path.exists(_v):
        print(f"[UYARI] Video dosyası bulunamadı: {_v}")
    else:
        print(f"[OK] Video bulundu: {_v}")


def market_ana_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🛍️ Kahvehane Okey Marketi",
        description="Çiplerini harca, masana renk kat!\nBir ürün seçmek için aşağıdaki menüyü kullan.",
        color=0xe67e22
    )
    for anahtar, urun in MARKET_URUNLER.items():
        tur_etiketi = {
            "sürekli":    "♾️ Kalıcı",
            "tek_kullanim": "1️⃣ Tek Kullanım",
            "anlik":      "⚡ Anında",
        }.get(urun["tur"], urun["tur"])
        embed.add_field(
            name=f"{urun['emoji']} {urun['ad']} — {urun['fiyat']:,} 🪙",
            value=f"{urun['aciklama']}\n*{tur_etiketi}*",
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
        tur_etiketi = {
            "sürekli":    "♾️ Kalıcı",
            "tek_kullanim": "1️⃣ Tek Kullanım",
            "anlik":      "⚡ Anında",
        }.get(urun["tur"], urun["tur"])
        embed = discord.Embed(
            title=f"{urun['emoji']} {urun['ad']}",
            description=urun["aciklama"],
            color=0x2ecc71
        )
        embed.add_field(name="💰 Fiyat", value=f"{urun['fiyat']:,} 🪙", inline=True)
        embed.add_field(name="🔖 Tür",   value=tur_etiketi,              inline=True)
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

        for item in self.children:
            item.disabled = True

        # Alışveriş görevi ilerlet
        try:
            from src.economy.gorevler import gorev_ilerlet
            await gorev_ilerlet(uid, "alisveris")
        except Exception:
            pass

        # ── Anında kullanılan ürünler ────────────────────────────────────────
        if urun["tur"] == "anlik":
            if self.urun_adi == "sans_kutusu":
                kazanim = random.choices(SANS_KUTULARI, weights=SANS_KUTUSU_AGIRLIKLARI, k=1)[0]
                await update_cip(uid, kazanim)
                yorumlar = {
                    50:   "😐 Küçük bir fırsat ama olsun!",
                    100:  "😊 Fena değil!",
                    250:  "😃 Güzel bir kazanç!",
                    500:  "🎉 Harika şans!",
                    1000: "🤩 İnanılmaz şans!",
                    2000: "💫 Efsanevi şans!!",
                }
                embed = discord.Embed(
                    title="🎁 Şans Kutusu Açıldı!",
                    description=f"Tebrikler! **{kazanim:,}** 🪙 kazandın!",
                    color=0xf1c40f if kazanim >= 500 else 0x2ecc71
                )
                embed.set_footer(text=yorumlar.get(kazanim, "İyi şanslar!"))

            elif self.urun_adi == "okey_fali":
                fal = random.choice(OKEY_FALLARI)
                embed = discord.Embed(
                    title="🔮 Okey Falın",
                    description=fal,
                    color=0x9b59b6
                )
                embed.set_footer(text="Bu fal eğlencelik amaçlıdır. İyi oyunlar! ✨")

            else:
                embed = discord.Embed(
                    title="✅ Kullanıldı!",
                    description=f"{urun['emoji']} **{urun['ad']}** anında kullanıldı.",
                    color=0x2ecc71
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # ── Normal ürünler (envantere eklendi) ──────────────────────────────
        embed = discord.Embed(
            title="✅ Satın Alma Başarılı!",
            description=f"{urun['emoji']} **{urun['ad']}** envanterine eklendi!",
            color=0x2ecc71
        )
        embed.set_footer(text="Ürünün efekti oyun içinde otomatik aktif olur.")
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
            await interaction.followup.send(
                "☕ Zaten envanterinde **Çaycı Hüseyin Efekti** var!", ephemeral=True
            )
            return
        basarili, hata = await market_satin_al(uid, "cayci_huseyin")
        if not basarili:
            await interaction.followup.send(f"❌ {hata}", ephemeral=True)
            return
        try:
            from src.economy.gorevler import gorev_ilerlet
            await gorev_ilerlet(uid, "alisveris")
        except Exception:
            pass
        await interaction.followup.send(
            "☕ **Çaycı Hüseyin Efekti** satın alındı! Her 3 elde bir çay videosu gelecek.",
            ephemeral=True
        )


async def cayci_video_gonder(channel, oyuncu_adlari: dict):
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
