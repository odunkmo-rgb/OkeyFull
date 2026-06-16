import discord
from discord.ui import View, Button, Modal, TextInput
from typing import Optional

ADMIN_ID       = 1513128919182606378
IZLEYICI_ROL   = 1513129008554971256

# ─── Lobi paneli ─────────────────────────────────────────────────────────────

class LobiView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="4 Kişilik Masa Kur", style=discord.ButtonStyle.primary,
                       emoji="👥", custom_id="lobi_4kisi", row=0)
    async def dort_kisi(self, interaction: discord.Interaction, button: Button):
        from src.game.manager import game_manager
        await game_manager.masa_kur(interaction, max_oyuncu=4, bot_modu=False)

    @discord.ui.button(label="Botlara Karşı Oyna", style=discord.ButtonStyle.success,
                       emoji="🤖", custom_id="lobi_botlar", row=0)
    async def bot_modu(self, interaction: discord.Interaction, button: Button):
        from src.game.manager import game_manager
        await game_manager.masa_kur(interaction, max_oyuncu=4, bot_modu=True)

    @discord.ui.button(label="Karışık Masa", style=discord.ButtonStyle.secondary,
                       emoji="🎲", custom_id="lobi_karisik", row=0)
    async def karisik(self, interaction: discord.Interaction, button: Button):
        from src.game.manager import game_manager
        await game_manager.masa_kur(interaction, max_oyuncu=4, bot_modu="karisik")

    @discord.ui.button(label="Bahisli VIP Masa", style=discord.ButtonStyle.danger,
                       emoji="💰", custom_id="lobi_vip", row=1)
    async def vip_masa(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(VIPMasaModal())

    @discord.ui.button(label="Profilim & Sıralama", style=discord.ButtonStyle.secondary,
                       emoji="📊", custom_id="lobi_profil", row=1)
    async def profil_bak(self, interaction: discord.Interaction, button: Button):
        from src.economy.db import ensure_oyuncu, get_liderlik
        from src.ui.render import render_profil
        oyuncu = await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
        img_buf = render_profil(oyuncu)

        lider_tam = await get_liderlik("cip", 10)
        siralam   = next((i + 1 for i, o in enumerate(lider_tam)
                          if o["user_id"] == interaction.user.id), "10+")
        lider_top3 = lider_tam[:3]

        toplam    = oyuncu.get("toplam_mac", 0)
        galibiyet = oyuncu.get("galibiyet", 0)
        yenilgi   = oyuncu.get("yenilgi", 0)
        bera      = oyuncu.get("beraberlik", 0)
        oran      = f"%{(galibiyet / toplam * 100):.1f}" if toplam > 0 else "%0"
        cip       = oyuncu.get("cip", 0)
        seviye    = oyuncu.get("seviye", 1)

        embed = discord.Embed(title="📇 KAHVEHANE OKEY — OYUNCU PROFİLİ", color=0xf1c40f)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.description = (
            f"👤 **Oyuncu:** {interaction.user.mention}\n\n"
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
        embed.set_footer(text="Bu profil kartı sadece size özel gösterilmektedir.")
        file = discord.File(img_buf, filename="profil.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)


def _seviye_adi(seviye: int) -> str:
    if seviye < 5:  return "🪵 Çaylak Okeyci"
    if seviye < 10: return "☕ Kahve Müdavimi"
    if seviye < 20: return "⚡ Usta Okeyci"
    if seviye < 35: return "🔥 Uzman Okeyci"
    if seviye < 50: return "💎 Elit Okeyci"
    return "🎓 Okey Profesörü"


# ─── Modallar ────────────────────────────────────────────────────────────────

class VIPMasaModal(Modal, title="💰 VIP Masa — Bahis Belirle"):
    bahis = TextInput(label="Bahis Miktarı (Çip)", placeholder="Örn: 500",
                      min_length=1, max_length=10, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            miktar = int(self.bahis.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Geçersiz miktar.", ephemeral=True)
            return
        if miktar <= 0:
            await interaction.response.send_message("❌ Bahis 0'dan büyük olmalı.", ephemeral=True)
            return
        from src.economy.db import ensure_oyuncu
        from src.game.manager import game_manager
        oyuncu = await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
        if oyuncu.get("cip", 0) < miktar:
            await interaction.response.send_message(
                f"❌ Yeterli çipiniz yok! Mevcut: **{oyuncu.get('cip', 0):,}** 🪙", ephemeral=True)
            return
        await game_manager.masa_kur(interaction, max_oyuncu=4, bot_modu=False, bahis=miktar)


class TasAtModal(Modal, title="🗑️ Hangi Taşı Atacaksınız?"):
    def __init__(self, masa_id: str):
        super().__init__()
        self.masa_id = masa_id

    renk_input = TextInput(
        label="Taşın Rengi",
        placeholder="kirmizi / sari / mavi / siyah",
        min_length=1, max_length=10, required=True
    )
    sayi_input = TextInput(
        label="Taşın Sayısı (1-13)",
        placeholder="Örn: 11",
        min_length=1, max_length=2, required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        from src.game.okey_engine import COLOR_INPUT_MAP
        renk_raw = self.renk_input.value.strip().lower()
        renk = COLOR_INPUT_MAP.get(renk_raw)
        if not renk:
            await interaction.response.send_message(
                "❌ Geçersiz renk!\n"
                "`kirmizi` · `sari` · `mavi` · `siyah` yazın.", ephemeral=True)
            return
        try:
            sayi = int(self.sayi_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Geçersiz sayı.", ephemeral=True)
            return
        if not 1 <= sayi <= 13:
            await interaction.response.send_message("❌ Sayı 1-13 arasında olmalı.", ephemeral=True)
            return
        from src.game.manager import game_manager
        await game_manager.tas_at_renk_sayi(interaction, self.masa_id, renk, sayi)


# ─── Per seçim view'ı ────────────────────────────────────────────────────────

class PerSecimView(View):
    """Kullanıcıya per dizme modunu sorar."""
    def __init__(self, masa_id: str):
        super().__init__(timeout=60)
        self.masa_id = masa_id

    @discord.ui.button(
        label="Aynı Renk + Ardışık (🔴1-2-3)",
        style=discord.ButtonStyle.primary, emoji="🎯", row=0
    )
    async def renk_sayi(self, interaction: discord.Interaction, button: Button):
        from src.game.manager import game_manager
        await game_manager.per_diz_mod(interaction, self.masa_id, "renk_sayi")
        self.stop()

    @discord.ui.button(
        label="Aynı Sayı + Farklı Renk (🔴13 🟡13 🔵13)",
        style=discord.ButtonStyle.success, emoji="🀄", row=0
    )
    async def sayi_renk(self, interaction: discord.Interaction, button: Button):
        from src.game.manager import game_manager
        await game_manager.per_diz_mod(interaction, self.masa_id, "sayi_renk")
        self.stop()

    @discord.ui.button(label="İptal", style=discord.ButtonStyle.secondary, emoji="✖️", row=1)
    async def iptal(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="❌ Per dizme iptal edildi.", view=None)
        self.stop()


# ─── Masa aksiyon paneli ─────────────────────────────────────────────────────

def build_masa_view(masa_id: str) -> View:
    view = View(timeout=None)

    async def katil_cb(i):
        from src.game.manager import game_manager
        await game_manager.masaya_katil(i, masa_id)

    async def per_cb(i):
        """Per seçim menüsünü aç."""
        await i.response.send_message(
            "🀄 **Per dizme modu seçin:**\n"
            "• **Aynı Renk + Ardışık** → 🔴1 🔴2 🔴3 gibi sıralar\n"
            "• **Aynı Sayı + Farklı Renk** → 🔴13 🟡13 🔵13 gibi sıralar",
            view=PerSecimView(masa_id), ephemeral=True
        )

    async def el_cb(i):
        from src.game.manager import game_manager
        await game_manager.el_goster(i, masa_id)

    async def talon_cb(i):
        from src.game.manager import game_manager
        await game_manager.talon_cek(i, masa_id)

    async def son_tas_cb(i):
        from src.game.manager import game_manager
        await game_manager.son_tasi_al(i, masa_id)

    async def at_cb(i):
        await i.response.send_modal(TasAtModal(masa_id))

    async def okey_cb(i):
        from src.game.manager import game_manager
        await game_manager.okey_ac(i, masa_id)

    async def baslat_cb(i):
        from src.game.manager import game_manager
        await game_manager.masayi_baslat(i, masa_id)

    async def ayril_cb(i):
        from src.game.manager import game_manager
        await game_manager.masadan_ayril(i, masa_id)

    buttons = [
        # row 0
        Button(label="Masaya Katıl",    style=discord.ButtonStyle.success,   emoji="✅", custom_id=f"katil_{masa_id}",  row=0),
        Button(label="Perleri Diz",     style=discord.ButtonStyle.secondary, emoji="🀄", custom_id=f"per_{masa_id}",    row=0),
        Button(label="El Gör",          style=discord.ButtonStyle.primary,   emoji="👁️", custom_id=f"el_{masa_id}",     row=0),
        # row 1
        Button(label="Talon'dan Çek",   style=discord.ButtonStyle.primary,   emoji="🎴", custom_id=f"talon_{masa_id}",  row=1),
        Button(label="Son Taşı Al",     style=discord.ButtonStyle.secondary, emoji="♻️", custom_id=f"son_{masa_id}",    row=1),
        Button(label="Taş At",          style=discord.ButtonStyle.danger,    emoji="🗑️", custom_id=f"at_{masa_id}",     row=1),
        # row 2
        Button(label="OKEY AÇ! 🏆",    style=discord.ButtonStyle.success,   emoji="🎉", custom_id=f"okey_{masa_id}",   row=2),
        Button(label="Masayı Başlat",   style=discord.ButtonStyle.primary,   emoji="▶️", custom_id=f"baslat_{masa_id}", row=2),
        Button(label="Masadan Ayrıl",   style=discord.ButtonStyle.danger,    emoji="🚪", custom_id=f"ayril_{masa_id}",  row=2),
    ]
    cbs = [katil_cb, per_cb, el_cb, talon_cb, son_tas_cb, at_cb, okey_cb, baslat_cb, ayril_cb]

    for btn, cb in zip(buttons, cbs):
        btn.callback = cb
        view.add_item(btn)

    return view
