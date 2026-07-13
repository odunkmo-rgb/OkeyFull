import discord

class RovansView(discord.ui.View):
    def __init__(self, oyuncu_ids: list[int], bahis: int):
        super().__init__(timeout=180)
        self.oyuncu_ids = list(oyuncu_ids)
        self.bahis      = bahis
        self.kullanildi = False

    @discord.ui.button(label="🔄 Rövanş!", style=discord.ButtonStyle.primary)
    async def rovans(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.oyuncu_ids:
            await interaction.response.send_message(
                "❌ Bu masanın oyuncusu değilsiniz!", ephemeral=True
            )
            return
        if self.kullanildi:
            await interaction.response.send_message(
                "⚠️ Rövanş masası zaten kuruldu!", ephemeral=True
            )
            return
        self.kullanildi = True
        from src.game.manager import game_manager
        from src.economy.db import ensure_oyuncu
        await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
        await game_manager.masa_kur(
            interaction, max_oyuncu=4, bot_modu=False, bahis=self.bahis
        )
