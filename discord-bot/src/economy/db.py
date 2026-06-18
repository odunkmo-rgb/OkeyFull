import aiosqlite
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "../../okey.db")

BASLANGIC_CIP  = 1000
GUNLUK_ODUL    = 500
KAZANMA_ODUL   = 200
KAYBETME_CEZA  = 50

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS oyuncular (
                user_id       INTEGER PRIMARY KEY,
                ad            TEXT,
                cip           INTEGER DEFAULT 1000,
                galibiyet     INTEGER DEFAULT 0,
                yenilgi       INTEGER DEFAULT 0,
                beraberlik    INTEGER DEFAULT 0,
                toplam_mac    INTEGER DEFAULT 0,
                son_gunluk    TEXT,
                seviye        INTEGER DEFAULT 1,
                kozmetik      TEXT DEFAULT '{}',
                kayit_tarihi  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Eski veritabanlarına beraberlik kolonu ekle (varsa ignore)
        try:
            await db.execute("ALTER TABLE oyuncular ADD COLUMN beraberlik INTEGER DEFAULT 0")
        except Exception:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mac_gecmisi (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                masa_id     TEXT,
                kazanan_id  INTEGER,
                oyuncular   TEXT,
                bahis       INTEGER DEFAULT 0,
                tarih       TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS okey_ayarlar (
                guild_id    INTEGER PRIMARY KEY,
                rol_idleri  TEXT DEFAULT '[]'
            )
        """)
        await db.commit()

async def get_oyuncu(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM oyuncular WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else {}

async def ensure_oyuncu(user_id: int, ad: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO oyuncular (user_id, ad, cip) VALUES (?, ?, ?)",
            (user_id, ad, BASLANGIC_CIP)
        )
        await db.execute("UPDATE oyuncular SET ad = ? WHERE user_id = ?", (ad, user_id))
        await db.commit()
    return await get_oyuncu(user_id)

async def update_cip(user_id: int, miktar: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE oyuncular SET cip = MAX(0, cip + ?) WHERE user_id = ?",
            (miktar, user_id)
        )
        await db.commit()
    return (await get_oyuncu(user_id)).get("cip", 0)

async def gunluk_al(user_id: int) -> tuple[bool, int, str]:
    oyuncu = await get_oyuncu(user_id)
    if not oyuncu:
        return False, 0, "Kayıt bulunamadı"
    son = oyuncu.get("son_gunluk")
    if son:
        son_dt = datetime.fromisoformat(son)
        if datetime.now() - son_dt < timedelta(hours=24):
            kalan = timedelta(hours=24) - (datetime.now() - son_dt)
            saat  = int(kalan.total_seconds() // 3600)
            dak   = int((kalan.total_seconds() % 3600) // 60)
            return False, 0, f"{saat}s {dak}dk"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE oyuncular SET cip = cip + ?, son_gunluk = ? WHERE user_id = ?",
            (GUNLUK_ODUL, datetime.now().isoformat(), user_id)
        )
        await db.commit()
    return True, GUNLUK_ODUL, ""

async def mac_bitti(kazanan_id: int, oyuncu_ids: list[int], bahis: int, masa_id: str):
    gercek = [uid for uid in oyuncu_ids if uid > 0]
    async with aiosqlite.connect(DB_PATH) as db:
        for uid in gercek:
            if uid == kazanan_id:
                kazanim = KAZANMA_ODUL + bahis * (len(gercek) - 1)
                await db.execute("""
                    UPDATE oyuncular
                    SET cip = cip + ?, galibiyet = galibiyet + 1, toplam_mac = toplam_mac + 1
                    WHERE user_id = ?
                """, (kazanim, uid))
            else:
                await db.execute("""
                    UPDATE oyuncular
                    SET cip = MAX(0, cip - ?), yenilgi = yenilgi + 1, toplam_mac = toplam_mac + 1
                    WHERE user_id = ?
                """, (KAYBETME_CEZA + bahis, uid))
        await db.execute(
            "INSERT INTO mac_gecmisi (masa_id, kazanan_id, oyuncular, bahis) VALUES (?, ?, ?, ?)",
            (masa_id, kazanan_id, ",".join(str(x) for x in oyuncu_ids), bahis)
        )
        await db.commit()
    await _seviye_guncelle(gercek)

async def _seviye_guncelle(uid_list: list[int]):
    async with aiosqlite.connect(DB_PATH) as db:
        for uid in uid_list:
            o = await get_oyuncu(uid)
            sv = 1 + o.get("toplam_mac", 0) // 10
            await db.execute("UPDATE oyuncular SET seviye = ? WHERE user_id = ?", (sv, uid))
        await db.commit()

async def transfer_cip(gonderen: int, alan: int, miktar: int) -> tuple[bool, str]:
    g = await get_oyuncu(gonderen)
    if not g:
        return False, "Hesabınız bulunamadı."
    if miktar <= 0:
        return False, "Geçersiz miktar."
    if g.get("cip", 0) < miktar:
        return False, f"Yeterli çipiniz yok. Mevcut: **{g.get('cip', 0):,}** 🪙"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE oyuncular SET cip = cip - ? WHERE user_id = ?", (miktar, gonderen))
        await db.execute("UPDATE oyuncular SET cip = cip + ? WHERE user_id = ?", (miktar, alan))
        await db.commit()
    return True, ""

async def get_liderlik(kategori: str = "cip", limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sorgu = {
            "galibiyet": "SELECT * FROM oyuncular ORDER BY galibiyet DESC, cip DESC LIMIT ?",
            "mac":        "SELECT * FROM oyuncular ORDER BY toplam_mac DESC LIMIT ?",
        }.get(kategori, "SELECT * FROM oyuncular ORDER BY cip DESC LIMIT ?")
        async with db.execute(sorgu, (limit,)) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def vip_mac_oyna(user_id: int, bahis: int) -> tuple[str, int, int]:
    """VIP masa RNG: kazan/bera/kaybet döner. (sonuc, odül_delta, yeni_cip)"""
    import random
    oyuncu = await get_oyuncu(user_id)
    cip = oyuncu.get("cip", 0)

    kazanma_hedef   = random.choice([10, 45, 50])
    beraberlik_hedef = random.choice([60, 70, 80])
    sans = random.randint(1, 100)

    async with aiosqlite.connect(DB_PATH) as db:
        if sans <= kazanma_hedef:
            odul = bahis * 2
            await db.execute("""
                UPDATE oyuncular SET cip = cip + ?, galibiyet = galibiyet + 1,
                toplam_mac = toplam_mac + 1 WHERE user_id = ?
            """, (odul, user_id))
            await db.commit()
            return "kazan", odul, cip + odul
        elif sans <= beraberlik_hedef:
            await db.execute("""
                UPDATE oyuncular SET beraberlik = beraberlik + 1,
                toplam_mac = toplam_mac + 1 WHERE user_id = ?
            """, (user_id,))
            await db.commit()
            return "bera", 0, cip
        else:
            await db.execute("""
                UPDATE oyuncular SET cip = MAX(0, cip - ?), yenilgi = yenilgi + 1,
                toplam_mac = toplam_mac + 1 WHERE user_id = ?
            """, (bahis, user_id))
            await db.commit()
            return "kaybet", -bahis, max(0, cip - bahis)


# ── Okey ayarları (izin rolleri) ─────────────────────────────────────────────

async def get_izin_roller(guild_id: int) -> list:
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT rol_idleri FROM okey_ayarlar WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return json.loads(row["rol_idleri"])
            return []


async def set_izin_roller(guild_id: int, rol_idleri: list) -> None:
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO okey_ayarlar (guild_id, rol_idleri) VALUES (?, ?)",
            (guild_id, json.dumps(rol_idleri))
        )
        await db.commit()
