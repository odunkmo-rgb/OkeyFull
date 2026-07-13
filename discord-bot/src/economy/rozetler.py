"""Rozet & Başarım Sistemi."""
import aiosqlite
from src.economy.db import DB_PATH, get_oyuncu

ROZETLER: dict[str, dict] = {
    "ilk_oyun":       {"emoji": "🎮", "ad": "İlk Adım",          "aciklama": "İlk oyununu oynadın!"},
    "ilk_galibiyet":  {"emoji": "🌟", "ad": "İlk Galibiyet",     "aciklama": "İlk oyununu kazandın!"},
    "10_galibiyet":   {"emoji": "🥈", "ad": "Usta",              "aciklama": "10 oyun kazandın."},
    "50_galibiyet":   {"emoji": "🥇", "ad": "Şampiyon",          "aciklama": "50 oyun kazandın!"},
    "100_galibiyet":  {"emoji": "👑", "ad": "Efsane",            "aciklama": "100 oyun kazandın. Sen bir efsanesin!"},
    "10_oyun":        {"emoji": "🎯", "ad": "Düzenli",           "aciklama": "10 oyun oynadın."},
    "100_oyun":       {"emoji": "🎪", "ad": "Kahvehane Müdavimi","aciklama": "100 oyun oynadın!"},
    "zengin":         {"emoji": "💰", "ad": "Zengin",             "aciklama": "10.000 🪙 biriktirdin!"},
    "super_zengin":   {"emoji": "💎", "ad": "Milyoner",           "aciklama": "50.000 🪙 biriktirdin!"},
    "cifte_okey_r":   {"emoji": "🌠", "ad": "Çifte Usta",        "aciklama": "Çifte okey ile kazandın!"},
    "yedi_cift_r":    {"emoji": "🎊", "ad": "Çift Ustası",       "aciklama": "Yedi çift ile kazandın!"},
    "market_5":       {"emoji": "🛍️", "ad": "Market Müdavimi",   "aciklama": "Marketten 5 ürün satın aldın."},
    "hatrick":        {"emoji": "🔥", "ad": "Hatrick",            "aciklama": "Üst üste 3 oyun kazandın!"},
}


async def init_rozetler_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kullanici_rozetler (
                user_id   INTEGER NOT NULL,
                rozet_id  TEXT    NOT NULL,
                kazanildi TEXT    DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, rozet_id)
            )
        """)
        try:
            await db.execute(
                "ALTER TABLE oyuncular ADD COLUMN galibiyet_serisi INTEGER DEFAULT 0"
            )
        except Exception:
            pass
        await db.commit()


async def get_rozetler(user_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT rozet_id FROM kullanici_rozetler WHERE user_id = ?", (user_id,)
        ) as cur:
            return [r["rozet_id"] for r in await cur.fetchall()]


async def _ver_rozet(user_id: int, rozet_id: str, mevcut: set) -> bool:
    if rozet_id in mevcut:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO kullanici_rozetler (user_id, rozet_id) VALUES (?, ?)",
            (user_id, rozet_id)
        )
        await db.commit()
    return True


async def _guncelle_seri(user_id: int, kazandi: bool) -> int:
    """Galibiyet serisini güncelle, yeni seriyi döndür."""
    async with aiosqlite.connect(DB_PATH) as db:
        if kazandi:
            await db.execute(
                "UPDATE oyuncular SET galibiyet_serisi = galibiyet_serisi + 1 WHERE user_id = ?",
                (user_id,)
            )
        else:
            await db.execute(
                "UPDATE oyuncular SET galibiyet_serisi = 0 WHERE user_id = ?",
                (user_id,)
            )
        await db.commit()
    oyuncu = await get_oyuncu(user_id)
    return oyuncu.get("galibiyet_serisi", 0)


async def rozet_kontrol(user_id: int, kazandi: bool, kazanma_turu: str = "normal") -> list[str]:
    """
    Oyun sonrası rozet kontrolü. Yeni kazanılan rozet ID listesini döndür.
    """
    oyuncu = await get_oyuncu(user_id)
    if not oyuncu:
        return []

    mevcut = set(await get_rozetler(user_id))
    yeni: list[str] = []

    seri       = await _guncelle_seri(user_id, kazandi)
    galibiyet  = oyuncu.get("galibiyet", 0)
    toplam_mac = oyuncu.get("toplam_mac", 0)
    cip        = oyuncu.get("cip", 0)

    kontroller = [
        (toplam_mac >= 1,              "ilk_oyun"),
        (galibiyet >= 1,               "ilk_galibiyet"),
        (galibiyet >= 10,              "10_galibiyet"),
        (galibiyet >= 50,              "50_galibiyet"),
        (galibiyet >= 100,             "100_galibiyet"),
        (toplam_mac >= 10,             "10_oyun"),
        (toplam_mac >= 100,            "100_oyun"),
        (cip >= 10_000,                "zengin"),
        (cip >= 50_000,                "super_zengin"),
        (kazanma_turu == "cifte_okey", "cifte_okey_r"),
        (kazanma_turu == "yedi_cift",  "yedi_cift_r"),
        (seri >= 3,                    "hatrick"),
    ]

    for kosul, rid in kontroller:
        if kosul and await _ver_rozet(user_id, rid, mevcut):
            mevcut.add(rid)
            yeni.append(rid)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) as sayi FROM market_envanter WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if row and row[0] >= 5:
                if await _ver_rozet(user_id, "market_5", mevcut):
                    yeni.append("market_5")

    return yeni
