import discord

class DuelView(discord.ui.View):
    def __init__(self, davetci_id: int, hedef_id: int, bahis: int):
        super().__init__(timeout=60)
        self.davetci_id = davetci_id
        self.hedef_id   = hedef_id
        self.bahis      = bahis
        self.islendi    = False

    async def _deaktive_et(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

    @discord.ui.button(label="✅ Kabul Et", style=discord.ButtonStyle.success)
    async def kabul(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.hedef_id:
            await interaction.response.send_message(
                "❌ Bu duel sana değil!", ephemeral=True
            )
            return
        if self.islendi:
            await interaction.response.send_message(
                "⚠️ Bu duel zaten işlendi.", ephemeral=True
            )
            return
        self.islendi = True
        await self._deaktive_et(interaction)

        from src.game.manager import game_manager
        from src.economy.db import ensure_oyuncu
        await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
        await game_manager.duel_baslat(
            interaction, self.davetci_id, self.hedef_id, self.bahis
        )

    @discord.ui.button(label="❌ Reddet", style=discord.ButtonStyle.danger)
    async def reddet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.hedef_id, self.davetci_id):
            await interaction.response.send_message(
                "❌ Sadece duel katılımcıları reddedebilir.", ephemeral=True
            )
            return
        if self.islendi:
            await interaction.response.send_message(
                "⚠️ Bu duel zaten işlendi.", ephemeral=True
            )
            return
        self.islendi = True
        await self._deaktive_et(interaction)
        await interaction.response.send_message(
            f"❌ **{interaction.user.display_name}** dueli reddetti."
        )
