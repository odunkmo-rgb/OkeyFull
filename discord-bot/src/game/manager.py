import discord
import asyncio
import uuid
from typing import Optional
from src.game.okey_engine import OkeyGame, GameState, COLOR_EMOJI, COLOR_NAMES
from src.economy.db import ensure_oyuncu, update_cip, mac_bitti
from src.ui.render import render_el, render_son_tas

IZLEYICI_ROL_ID  = 1513129008554971256
KARISIK_BEKLEME  = 30
BOT_SAYAC        = 10

class GameManager:
    def __init__(self):
        self.masalar: dict[str, OkeyGame] = {}

    def yeni_masa_id(self) -> str:
        return uuid.uuid4().hex[:8].upper()

    def _masa_bul_oyuncu(self, user_id: int) -> Optional[str]:
        for mid, masa in self.masalar.items():
            if user_id in masa.oyuncular:
                return mid
        return None

    # ── Özel kanal oluştur/sil ───────────────────────────────────────────────
    async def _oyun_kanali_olustur(self, guild: discord.Guild, masa: OkeyGame) -> Optional[discord.TextChannel]:
        try:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
            }
            izleyici = guild.get_role(IZLEYICI_ROL_ID)
            if izleyici:
                overwrites[izleyici] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=False, read_message_history=True
                )
            for uid in masa.oyuncular:
                if uid > 0:
                    member = guild.get_member(uid)
                    if member:
                        overwrites[member] = discord.PermissionOverwrite(
                            view_channel=True, send_messages=True, read_message_history=True
                        )
            kategori = discord.utils.get(guild.categories, name="🎲 Okey Masaları")
            if not kategori:
                kategori = await guild.create_category("🎲 Okey Masaları")
            kanal = await guild.create_text_channel(
                name=f"okey-masa-{masa.masa_id.lower()}",
                category=kategori,
                overwrites=overwrites,
                topic=f"🎲 Masa #{masa.masa_id} | Bahis: {'Yok' if masa.bahis == 0 else f'{masa.bahis:,} çip'}"
            )
            masa.oyun_kanal_id = kanal.id
            return kanal
        except discord.Forbidden:
            return None
        except Exception as e:
            print(f"[Kanal Hatası] {e}")
            return None

    async def _kanal_sil_bekle(self, kanal: discord.TextChannel, gecikme: int = 10):
        await asyncio.sleep(gecikme)
        try:
            await kanal.delete(reason="Okey oyunu bitti")
        except Exception:
            pass

    # ── Panel gönder / sayaç ─────────────────────────────────────────────────
    async def _panel_gonder(self, channel, masa_id: str):
        masa = self.masalar.get(masa_id)
        if not masa:
            return
        from src.ui.views import build_masa_view
        embed = self._oyun_embed(masa)
        view  = build_masa_view(masa_id)
        try:
            msg = await channel.send(embed=embed, view=view)
            masa.panel_mesaj_id = msg.id
        except Exception:
            pass

    async def _mesaj_sayaci_artir(self, channel, masa_id: str):
        masa = self.masalar.get(masa_id)
        if not masa or masa.durum != GameState.PLAYING:
            return
        masa.mesaj_sayaci += 1
        if masa.mesaj_sayaci >= 2:
            masa.mesaj_sayaci = 0
            await self._panel_gonder(channel, masa_id)

    # ── Masa kur ─────────────────────────────────────────────────────────────
    async def masa_kur(self, interaction: discord.Interaction, max_oyuncu: int = 4,
                       bot_modu=False, bahis: int = 0):
        await ensure_oyuncu(interaction.user.id, interaction.user.display_name)

        mevcut = self._masa_bul_oyuncu(interaction.user.id)
        if mevcut:
            await interaction.response.send_message(
                f"❌ Zaten **`{mevcut}`** masadasınız! Önce `/okey ayrıl` yazın.", ephemeral=True)
            return

        masa_id = self.yeni_masa_id()
        masa = OkeyGame(masa_id=masa_id, max_oyuncu=max_oyuncu, bahis=bahis, bot_modu=bot_modu)
        masa.kanal_id = interaction.channel_id

        if bot_modu is True:
            masa.oyuncu_ekle(interaction.user.id, interaction.user.display_name)
            masa.doldur_botlarla()
        else:
            masa.oyuncu_ekle(interaction.user.id, interaction.user.display_name)

        self.masalar[masa_id] = masa
        embed = self._masa_embed(masa)
        from src.ui.views import build_masa_view
        view = build_masa_view(masa_id)

        if bot_modu is True:
            await interaction.response.send_message(
                f"⏳ **Oyun kuruluyor...** 3 Bot ekleniyor!\n"
                f"🤖 **{BOT_SAYAC} saniye** içinde başlıyor...",
                embed=embed, view=view
            )
            try:
                msg = await interaction.original_response()
                masa.mesaj_id = msg.id
            except Exception:
                pass
            asyncio.create_task(self._bot_sayac_baslat(interaction, masa_id))

        elif bot_modu == "karisik":
            gercek = len([u for u in masa.oyuncular if u > 0])
            await interaction.response.send_message(
                f"🎲 **Karışık Masa kuruldu!** `({gercek}/{max_oyuncu})`\n"
                f"⏳ **{KARISIK_BEKLEME} saniye** bekleniyor — eksik yerler botla doldurulacak...",
                embed=embed, view=view
            )
            try:
                msg = await interaction.original_response()
                masa.mesaj_id = msg.id
            except Exception:
                pass
            asyncio.create_task(self._karisik_sayac_baslat(interaction, masa_id))

        else:
            gercek = len([u for u in masa.oyuncular if u > 0])
            await interaction.response.send_message(
                f"🎮 **Masa kuruldu!** `({gercek}/{max_oyuncu})`\n"
                f"Katılmak için **Masaya Katıl** butonuna basın!",
                embed=embed, view=view
            )
            try:
                msg = await interaction.original_response()
                masa.mesaj_id = msg.id
            except Exception:
                pass

    # ── Sayaçlar ─────────────────────────────────────────────────────────────
    async def _bot_sayac_baslat(self, interaction: discord.Interaction, masa_id: str):
        await asyncio.sleep(BOT_SAYAC)
        masa = self.masalar.get(masa_id)
        if not masa or masa.durum != GameState.WAITING:
            return
        await self.masayi_baslat_otomatik(interaction.guild, interaction.channel, masa_id)

    async def _karisik_sayac_baslat(self, interaction: discord.Interaction, masa_id: str):
        await asyncio.sleep(KARISIK_BEKLEME)
        masa = self.masalar.get(masa_id)
        if not masa or masa.durum != GameState.WAITING:
            return
        gercek = [u for u in masa.oyuncular if u > 0]
        if len(gercek) < 1:
            del self.masalar[masa_id]
            try:
                await interaction.channel.send("⚠️ Yeterli oyuncu gelmedi, masa kapatıldı.")
            except Exception:
                pass
            return
        eksik = masa.max_oyuncu - len(masa.oyuncular)
        if eksik > 0:
            masa.doldur_botlarla()
            try:
                await interaction.channel.send(
                    f"⏰ **Süre doldu!** {eksik} bot eklendi. Oyun başlıyor!"
                )
            except Exception:
                pass
        await self.masayi_baslat_otomatik(interaction.guild, interaction.channel, masa_id)

    # ── Masaya katıl ─────────────────────────────────────────────────────────
    async def masaya_katil(self, interaction: discord.Interaction, masa_id: str):
        await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
        masa = self.masalar.get(masa_id)
        if not masa:
            await interaction.response.send_message("❌ Masa bulunamadı.", ephemeral=True); return
        if masa.durum != GameState.WAITING:
            await interaction.response.send_message("❌ Masa zaten başlamış.", ephemeral=True); return
        if interaction.user.id in masa.oyuncular:
            await interaction.response.send_message("❌ Zaten bu masadasınız!", ephemeral=True); return
        mevcut = self._masa_bul_oyuncu(interaction.user.id)
        if mevcut:
            await interaction.response.send_message(f"❌ Zaten `{mevcut}` masadasınız.", ephemeral=True); return
        if masa.bahis > 0:
            o = await ensure_oyuncu(interaction.user.id, interaction.user.display_name)
            if o.get("cip", 0) < masa.bahis:
                await interaction.response.send_message(
                    f"❌ VIP masa için **{masa.bahis:,}** 🪙 gerekmektedir. Mevcut: **{o.get('cip',0):,}** 🪙",
                    ephemeral=True); return

        ok = masa.oyuncu_ekle(interaction.user.id, interaction.user.display_name)
        if not ok:
            await interaction.response.send_message("❌ Masa dolu.", ephemeral=True); return

        gercek = len([u for u in masa.oyuncular if u > 0])
        embed = self._masa_embed(masa)

        if len(masa.oyuncular) >= masa.max_oyuncu:
            oyuncular_str = self._oyuncu_mention_str(masa, interaction.guild)
            await interaction.response.edit_message(
                content=f"🎉 **Masa doldu!** Oyun başlıyor...\n**Oyuncular:** {oyuncular_str}",
                embed=embed
            )
            await asyncio.sleep(0.5)
            await self.masayi_baslat_otomatik(interaction.guild, interaction.channel, masa_id)
        else:
            await interaction.response.edit_message(
                content=f"✅ **{interaction.user.display_name}** masaya katıldı! `({gercek}/{masa.max_oyuncu})`\nKatılmak için butona basın!",
                embed=embed
            )

    def _oyuncu_mention_str(self, masa: OkeyGame, guild: Optional[discord.Guild]) -> str:
        parts = []
        for uid in masa.oyuncular:
            if uid > 0 and guild:
                m = guild.get_member(uid)
                parts.append(m.mention if m else masa.oyuncu_adlari.get(uid, "?"))
            else:
                parts.append(masa.oyuncu_adlari.get(uid, "Bot"))
        return ", ".join(parts)

    # ── Oyunu başlat ─────────────────────────────────────────────────────────
    async def masayi_baslat(self, interaction: discord.Interaction, masa_id: str):
        masa = self.masalar.get(masa_id)
        if not masa:
            await interaction.response.send_message("❌ Masa bulunamadı.", ephemeral=True); return
        if masa.oyuncular and interaction.user.id != masa.oyuncular[0]:
            await interaction.response.send_message("❌ Sadece masa kurucusu başlatabilir.", ephemeral=True); return
        if masa.durum != GameState.WAITING:
            await interaction.response.send_message("❌ Masa zaten başlamış.", ephemeral=True); return

        eksik = masa.max_oyuncu - len(masa.oyuncular)
        if eksik > 0:
            masa.doldur_botlarla()

        await interaction.response.defer()
        await self.masayi_baslat_otomatik(interaction.guild, interaction.channel, masa_id)

    async def masayi_baslat_otomatik(self, guild: Optional[discord.Guild], kanal, masa_id: str):
        masa = self.masalar.get(masa_id)
        if not masa or masa.durum != GameState.WAITING:
            return
        masa.oyunu_baslat()

        oyun_kanali = None
        if guild:
            oyun_kanali = await self._oyun_kanali_olustur(guild, masa)

        hedef = oyun_kanali or kanal

        oyuncu_list = self._oyuncu_mention_str(masa, guild)
        if kanal and oyun_kanali and oyun_kanali.id != kanal.id:
            try:
                await kanal.send(
                    f"🎲 **Oyun başladı!** Oyuncular: {oyuncu_list}\n"
                    f"📍 Oyun kanalı: {oyun_kanali.mention}"
                )
            except Exception:
                pass

        if hedef:
            await hedef.send(
                f"🎲 **Kahvehane Okey Başladı!**\n"
                f"👥 **Oyuncular:** {oyuncu_list}\n"
                f"🎴 **Okey Taşı:** {self._okey_str(masa)}\n"
                f"⏳ **İlk Sıra:** {masa.oyuncu_adlari.get(masa.siradaki_oyuncu_id(), '?')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            await self._panel_gonder(hedef, masa_id)

        await self._bot_tur_kontrol(hedef, masa_id)

    # ── Bot turları ──────────────────────────────────────────────────────────
    async def _bot_tur_kontrol(self, channel, masa_id: str):
        """Bot sıralarını zincirleme oynatır; gerçek oyuncuya geçince panel gönderir."""
        while True:
            masa = self.masalar.get(masa_id)
            if not masa or masa.durum != GameState.PLAYING:
                return
            siradaki = masa.siradaki_oyuncu_id()
            if siradaki not in masa.bot_oyuncular:
                # Gerçek oyuncunun sırası — panel gönder
                if channel:
                    await channel.send(
                        f"🎴 Sıra: **{masa.oyuncu_adlari.get(siradaki, '?')}** — Taş çekin!"
                    )
                    await self._panel_gonder(channel, masa_id)
                return
            await asyncio.sleep(1.5)
            masa = self.masalar.get(masa_id)
            if not masa or masa.durum != GameState.PLAYING:
                return
            atilan = masa.bot_hamle_yap(siradaki)
            bot_ad = masa.oyuncu_adlari.get(siradaki, "Bot")
            if masa.durum == GameState.FINISHED:
                if channel:
                    await channel.send(f"🤖 **{bot_ad}** OKEY AÇTI! 🎉")
                await self._oyun_bitti(channel, masa_id, siradaki, None)
                return
            if channel and atilan:
                await channel.send(f"🤖 **{bot_ad}** `{str(atilan)}` attı.")

    # ── El gör ──────────────────────────────────────────────────────────────
    async def el_goster(self, interaction: discord.Interaction, masa_id: str):
        masa = self.masalar.get(masa_id)
        if not masa:
            await interaction.response.send_message("❌ Masa bulunamadı.", ephemeral=True); return
        if interaction.user.id not in masa.oyuncu_elleri:
            await interaction.response.send_message("❌ Oyun başlamadı veya masada değilsiniz.", ephemeral=True); return

        el = masa.oyuncu_elleri[interaction.user.id]
        img_buf = render_el(el, masa.okey_tas, title=f"🀄 {interaction.user.display_name} — Elinizdeki Taşlar")
        file = discord.File(img_buf, filename="el.png")

        # Her taşı numaralı text listesi
        el_satirlar = []
        for i, t in enumerate(el):
            renk_ad = COLOR_NAMES.get(t.renk, t.renk) if not t.okey else "JOKER"
            sayi_str = str(t.sayi) if not t.okey else "★"
            emoji = COLOR_EMOJI.get(t.renk, "🃏") if not t.okey else "🃏"
            el_satirlar.append(f"`{i+1:>2}.` {emoji} **{renk_ad} {sayi_str}**")

        el_text = "\n".join(el_satirlar)
        embed = discord.Embed(
            title="🀄 Elinizdeki Taşlar",
            description=(
                f"**Okey taşı:** {self._okey_str(masa)}\n"
                f"**Taş sayısı:** {len(el)}\n\n"
                f"{el_text}\n\n"
                f"💡 *Taş At butonuna basıp **renk** ve **sayı** yazın.*"
            ),
            color=0x2ecc71
        )
        embed.set_image(url="attachment://el.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    # ── Per diz (mod seçimli) ────────────────────────────────────────────────
    async def per_diz_mod(self, interaction: discord.Interaction, masa_id: str, mod: str):
        masa = self.masalar.get(masa_id)
        if not masa:
            await interaction.response.send_message("❌ Masa bulunamadı.", ephemeral=True); return
        if interaction.user.id not in masa.oyuncu_elleri:
            await interaction.response.send_message("❌ Masada değilsiniz.", ephemeral=True); return

        masa.peri_diz(interaction.user.id, mod)
        el = masa.oyuncu_elleri[interaction.user.id]
        img_buf = render_el(
            el, masa.okey_tas,
            title="🀄 Aynı Renk+Ardışık" if mod == "renk_sayi" else "🀄 Aynı Sayı+Farklı Renk"
        )
        file = discord.File(img_buf, filename="per.png")

        mod_aciklama = (
            "🎯 **Aynı Renk + Ardışık** (🔴1-🔴2-🔴3 gibi)"
            if mod == "renk_sayi"
            else "🀄 **Aynı Sayı + Farklı Renk** (🔴13-🟡13-🔵13 gibi)"
        )
        # Her taşı numaralı listele
        el_satirlar = []
        for i, t in enumerate(el):
            renk_ad = COLOR_NAMES.get(t.renk, t.renk) if not t.okey else "JOKER"
            sayi_str = str(t.sayi) if not t.okey else "★"
            emoji = COLOR_EMOJI.get(t.renk, "🃏") if not t.okey else "🃏"
            el_satirlar.append(f"`{i+1:>2}.` {emoji} **{renk_ad} {sayi_str}**")
        el_text = "\n".join(el_satirlar)

        embed = discord.Embed(
            title="🀄 Perlendi!",
            description=f"{mod_aciklama}\n\n{el_text}",
            color=0x3498db
        )
        embed.set_image(url="attachment://per.png")
        # edit_message ile dosya eklenemez, yeni ephemeral mesaj gönder
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    # ── Talon çek ───────────────────────────────────────────────────────────
    async def talon_cek(self, interaction: discord.Interaction, masa_id: str):
        masa = self.masalar.get(masa_id)
        if not masa:
            await interaction.response.send_message("❌ Masa bulunamadı.", ephemeral=True); return
        if masa.durum != GameState.PLAYING:
            await interaction.response.send_message("❌ Oyun başlamadı.", ephemeral=True); return
        if masa.siradaki_oyuncu_id() != interaction.user.id:
            await interaction.response.send_message("❌ Sıra sizde değil!", ephemeral=True); return
        if masa.el_cekti.get(interaction.user.id):
            await interaction.response.send_message("❌ Bu turda zaten taş çektiniz — şimdi taş atın!", ephemeral=True); return

        tas = masa.talon_cek(interaction.user.id)
        if not tas:
            await interaction.response.send_message("❌ Talon boş!", ephemeral=True); return

        el = masa.oyuncu_elleri[interaction.user.id]
        img_buf = render_el(el, masa.okey_tas, title=f"🎴 Çekilen: {str(tas)}")
        file = discord.File(img_buf, filename="cek.png")
        embed = discord.Embed(
            title="🎴 Talon'dan Taş Çekildi!",
            description=(
                f"**Çekilen taş:** {str(tas)}\n"
                f"**Taş sayınız:** {len(el)}\n\n"
                f"💡 Şimdi **Taş At** butonuna basıp atmak istediğiniz taşın **rengini** ve **sayısını** girin."
            ),
            color=0xf39c12
        )
        embed.set_image(url="attachment://cek.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    # ── Son taşı al (tablodaki/atılan) ───────────────────────────────────────
    async def son_tasi_al(self, interaction: discord.Interaction, masa_id: str):
        masa = self.masalar.get(masa_id)
        if not masa:
            await interaction.response.send_message("❌ Masa bulunamadı.", ephemeral=True); return
        if masa.durum != GameState.PLAYING:
            await interaction.response.send_message("❌ Oyun başlamadı.", ephemeral=True); return
        if masa.siradaki_oyuncu_id() != interaction.user.id:
            await interaction.response.send_message("❌ Sıra sizde değil!", ephemeral=True); return
        if masa.el_cekti.get(interaction.user.id):
            await interaction.response.send_message("❌ Bu turda zaten taş çektiniz — şimdi taş atın!", ephemeral=True); return
        if not masa.cop_yigi:
            await interaction.response.send_message("❌ Tabloda henüz taş yok!", ephemeral=True); return

        # Almadan önce göster
        son_tas = masa.cop_yigi[-1]
        tas = masa.son_tasi_al(interaction.user.id)
        if not tas:
            await interaction.response.send_message("❌ Taş alınamadı.", ephemeral=True); return

        el = masa.oyuncu_elleri[interaction.user.id]
        img_buf = render_el(el, masa.okey_tas, title=f"♻️ Tablodan alındı: {str(tas)}")
        file = discord.File(img_buf, filename="son_tas.png")
        embed = discord.Embed(
            title="♻️ Tablodaki Son Taş Alındı!",
            description=(
                f"**Aldığınız taş:** {str(tas)}\n"
                f"**Taş sayınız:** {len(el)}\n\n"
                f"💡 Şimdi **Taş At** butonuna basıp atmak istediğiniz taşın **rengini** ve **sayısını** girin."
            ),
            color=0x27ae60
        )
        embed.set_image(url="attachment://son_tas.png")
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    # ── Taş at (renk+sayı) ───────────────────────────────────────────────────
    async def tas_at_renk_sayi(self, interaction: discord.Interaction, masa_id: str, renk: str, sayi: int):
        masa = self.masalar.get(masa_id)
        if not masa:
            await interaction.response.send_message("❌ Masa bulunamadı.", ephemeral=True); return
        if masa.durum != GameState.PLAYING:
            await interaction.response.send_message("❌ Oyun başlamadı.", ephemeral=True); return
        if masa.siradaki_oyuncu_id() != interaction.user.id:
            await interaction.response.send_message("❌ Sıra sizde değil!", ephemeral=True); return
        if not masa.el_cekti.get(interaction.user.id):
            await interaction.response.send_message("❌ Önce taş çekin!", ephemeral=True); return

        el = masa.oyuncu_elleri.get(interaction.user.id, [])
        eslesme = [(i, t) for i, t in enumerate(el) if not t.okey and t.renk == renk and t.sayi == sayi]
        if not eslesme:
            re = COLOR_EMOJI.get(renk, "")
            ra = COLOR_NAMES.get(renk, renk)
            mevcut = "  ".join(str(t) for t in el)
            await interaction.response.send_message(
                f"❌ Elinizde **{re}{ra} {sayi}** taşı yok!\n\n**Eliniz:** {mevcut}",
                ephemeral=True
            )
            return

        atilan = masa.tas_at_by_renk_sayi(interaction.user.id, renk, sayi)
        if not atilan:
            await interaction.response.send_message("❌ Taş atılamadı.", ephemeral=True); return

        sonraki_id = masa.siradaki_oyuncu_id()
        sonraki_ad = masa.oyuncu_adlari.get(sonraki_id, "?")

        channel = interaction.channel
        if masa.oyun_kanal_id and interaction.guild:
            oyun_kanali = interaction.guild.get_channel(masa.oyun_kanal_id)
            if oyun_kanali:
                channel = oyun_kanali

        await interaction.response.send_message(
            f"🗑️ **{interaction.user.display_name}** `{str(atilan)}` taşını attı.\n"
            f"🎴 Sıra: **{sonraki_ad}**"
        )
        await self._mesaj_sayaci_artir(channel, masa_id)
        await self._bot_tur_kontrol(channel, masa_id)

    # ── Okey aç ─────────────────────────────────────────────────────────────
    async def okey_ac(self, interaction: discord.Interaction, masa_id: str):
        masa = self.masalar.get(masa_id)
        if not masa:
            await interaction.response.send_message("❌ Masa bulunamadı.", ephemeral=True); return
        if masa.durum != GameState.PLAYING:
            await interaction.response.send_message("❌ Oyun başlamadı.", ephemeral=True); return
        if masa.siradaki_oyuncu_id() != interaction.user.id:
            await interaction.response.send_message("❌ Sıra sizde değil!", ephemeral=True); return

        kazandi = masa.okey_ac(interaction.user.id)
        if kazandi:
            await interaction.response.send_message(
                f"🎉🏆 **{interaction.user.display_name} OKEY AÇTI! TEBRİKLER!** 🏆🎉"
            )
            channel = interaction.channel
            if masa.oyun_kanal_id and interaction.guild:
                oy = interaction.guild.get_channel(masa.oyun_kanal_id)
                if oy:
                    channel = oy
            await self._oyun_bitti(channel, masa_id, interaction.user.id, interaction.guild)
        else:
            await interaction.response.send_message(
                "❌ Eliniz henüz geçerli değil. Devam edin!", ephemeral=True
            )

    # ── Oyun bitti ──────────────────────────────────────────────────────────
    async def _oyun_bitti(self, channel, masa_id: str, kazanan_id: int, guild: Optional[discord.Guild]):
        masa = self.masalar.get(masa_id)
        if not masa:
            return
        masa.durum = GameState.FINISHED
        kazanan_ad = masa.oyuncu_adlari.get(kazanan_id, "Bot")
        gercek     = [uid for uid in masa.oyuncular if uid > 0]

        await mac_bitti(kazanan_id, masa.oyuncular, masa.bahis, masa_id)

        embed = discord.Embed(
            title="🏆 Oyun Bitti!",
            description=f"🎊 **{kazanan_ad}** oyunu kazandı!",
            color=0xf1c40f
        )
        if masa.bahis > 0:
            kazanim = 200 + masa.bahis * (len(gercek) - 1)
            embed.add_field(name="💰 Bahis",    value=f"{masa.bahis:,} 🪙", inline=True)
            embed.add_field(name="🎁 Kazanılan", value=f"{kazanim:,} 🪙",  inline=True)
        else:
            embed.add_field(name="🎁 Kazanılan", value="200 🪙 + Puan", inline=True)
        embed.set_footer(text="Kanal 10 saniye içinde silinecek.")

        if channel:
            await channel.send(embed=embed)

        kanal_id = masa.oyun_kanal_id
        del self.masalar[masa_id]

        if guild and kanal_id:
            oy = guild.get_channel(kanal_id)
            if oy:
                asyncio.create_task(self._kanal_sil_bekle(oy, 10))

    # ── Masadan ayrıl ────────────────────────────────────────────────────────
    async def masadan_ayril(self, interaction: discord.Interaction, masa_id: str):
        masa = self.masalar.get(masa_id)
        if not masa:
            await interaction.response.send_message("❌ Masa bulunamadı.", ephemeral=True); return
        if interaction.user.id not in masa.oyuncular:
            await interaction.response.send_message("❌ Bu masada değilsiniz.", ephemeral=True); return

        channel = interaction.channel
        if masa.oyun_kanal_id and interaction.guild:
            oy = interaction.guild.get_channel(masa.oyun_kanal_id)
            if oy:
                channel = oy

        if masa.durum == GameState.PLAYING:
            await update_cip(interaction.user.id, -100)
            await interaction.response.send_message(
                "⚠️ Aktif maçtan ayrıldığınız için **100 🪙** ceza uygulandı.", ephemeral=True
            )
            masa.oyuncu_cikar(interaction.user.id)
            if not [u for u in masa.oyuncular if u > 0]:
                await self._oyun_bitti(channel, masa_id, -1, interaction.guild)
                return
            if channel:
                await channel.send(
                    f"🚪 **{interaction.user.display_name}** ayrıldı.\n"
                    f"🎴 Sıra: **{masa.oyuncu_adlari.get(masa.siradaki_oyuncu_id(), '?')}**"
                )
                await self._mesaj_sayaci_artir(channel, masa_id)
            await self._bot_tur_kontrol(channel, masa_id)
        else:
            masa.oyuncu_cikar(interaction.user.id)
            if not [u for u in masa.oyuncular if u > 0]:
                if masa_id in self.masalar:
                    del self.masalar[masa_id]
                await interaction.response.send_message("✅ Masadan ayrıldınız. Masa kapatıldı.", ephemeral=True)
                return
            embed = self._masa_embed(masa)
            await interaction.response.edit_message(
                content=f"🚪 **{interaction.user.display_name}** masadan ayrıldı.",
                embed=embed
            )

    # ── Embed yardımcıları ───────────────────────────────────────────────────
    def _masa_embed(self, masa: OkeyGame) -> discord.Embed:
        gercek = len([u for u in masa.oyuncular if u > 0])
        oyuncu_satirlar = "\n".join(
            f"{'🤖' if uid < 0 else '👤'} **{ad}**"
            for uid, ad in masa.oyuncu_adlari.items()
            if uid in masa.oyuncular
        )
        bos = masa.max_oyuncu - len(masa.oyuncular)
        bos_str = "\n".join(f"⬜ _{i+1}. yer boş..._" for i in range(bos)) if bos else ""
        embed = discord.Embed(
            title=f"🎮 Okey Masası — `{masa.masa_id}`",
            description=(
                f"**Doluluk:** {gercek}/{masa.max_oyuncu}\n"
                f"**Bahis:** {'Yok' if masa.bahis == 0 else f'{masa.bahis:,} 🪙'}\n\n"
                f"**Oyuncular:**\n{oyuncu_satirlar}\n{bos_str}"
            ),
            color=0x2ecc71
        )
        embed.set_footer(text="Katılmak için 'Masaya Katıl' butonuna basın!")
        return embed

    def _oyun_embed(self, masa: OkeyGame) -> discord.Embed:
        sid = masa.siradaki_oyuncu_id()
        oyuncu_satirlar = "\n".join(
            f"{'🤖' if uid < 0 else '👤'} **{ad}**" + (" ⏳ **(SIRAN!)**" if uid == sid else "")
            for uid, ad in masa.oyuncu_adlari.items()
            if uid in masa.oyuncular
        )
        embed = discord.Embed(
            title=f"🎲 Okey Devam Ediyor — `{masa.masa_id}`",
            description=(
                f"**Okey Taşı:** {self._okey_str(masa)}\n"
                f"**Talon:** {len(masa.talon)} taş\n\n"
                f"**Oyuncular:**\n{oyuncu_satirlar}"
            ),
            color=0xf1c40f
        )
        if masa.cop_yigi:
            embed.add_field(name="♻️ Tablodaki Son Taş", value=f"`{str(masa.cop_yigi[-1])}`", inline=True)
        embed.add_field(name="🎴 Sıra", value=f"**{masa.oyuncu_adlari.get(sid, '?')}**", inline=True)
        embed.set_footer(text="El Gör → Talon'dan Çek VEYA Son Taşı Al → Taş At | Her 2 mesajda panel yenilenir.")
        return embed

    def _okey_str(self, masa: OkeyGame) -> str:
        if not masa.okey_tas:
            return "?"
        re = COLOR_EMOJI.get(masa.okey_tas.renk, "⬜")
        ra = COLOR_NAMES.get(masa.okey_tas.renk, masa.okey_tas.renk)
        return f"{re} **{ra} {masa.okey_tas.sayi}**"

game_manager = GameManager()
