"""Görev Sistemi — Günlük ve haftalık görevler."""
import aiosqlite
from datetime import datetime, timedelta
from src.economy.db import DB_PATH, update_cip

GUNLUK_GOREVLER = [
    {
        "id":       "gun_kazan3",
        "ad":       "🏆 Gün Şampiyonu",
        "aciklama": "Bugün 3 oyun kazan",
        "tip":      "galibiyet",
        "hedef":    3,
        "odul":     300,
        "periyot":  "gunluk",
    },
    {
        "id":       "gun_oyna5",
        "ad":       "🎮 Günlük Antrenman",
        "aciklama": "Bugün 5 oyun oyna",
        "tip":      "oyun",
        "hedef":    5,
        "odul":     200,
        "periyot":  "gunluk",
    },
    {
        "id":       "gun_market",
        "ad":       "🛍️ Alışveriş Günü",
        "aciklama": "Marketten 1 ürün satın al",
        "tip":      "alisveris",
        "hedef":    1,
        "odul":     100,
        "periyot":  "gunluk",
    },
]

HAFTALIK_GOREVLER = [
    {
        "id":       "haf_kazan10",
        "ad":       "🌟 Haftanın Efsanesi",
        "aciklama": "Bu hafta 10 oyun kazan",
        "tip":      "galibiyet",
        "hedef":    10,
        "odul":     1500,
        "periyot":  "haftalik",
    },
    {
        "id":       "haf_oyna25",
        "ad":       "⚡ Hafta Sporcusu",
        "aciklama": "Bu hafta 25 oyun oyna",
        "tip":      "oyun",
        "hedef":    25,
        "odul":     1000,
        "periyot":  "haftalik",
    },
    {
        "id":       "haf_gonder",
        "ad":       "🤝 Cömert Oyuncu",
        "aciklama": "Bu hafta birine çip gönder",
        "tip":      "gonder",
        "hedef":    1,
        "odul":     150,
        "periyot":  "haftalik",
    },
]

TUM_GOREVLER: dict[str, dict] = {
    g["id"]: g for g in GUNLUK_GOREVLER + HAFTALIK_GOREVLER
}


async def init_gorevler_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS kullanici_gorevler (
                user_id    INTEGER NOT NULL,
                gorev_id   TEXT NOT NULL,
                ilerleme   INTEGER DEFAULT 0,
                tamamlandi INTEGER DEFAULT 0,
                baslangic  TEXT,
                PRIMARY KEY (user_id, gorev_id)
            )
        """)
        await db.commit()


def _baslangic_zamani(gorev_id: str) -> str:
    now = datetime.now()
    if TUM_GOREVLER[gorev_id]["periyot"] == "gunluk":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    return start.isoformat()


def _periyot_bitti_mi(baslangic_str: str, gorev_id: str) -> bool:
    try:
        baslangic = datetime.fromisoformat(baslangic_str)
    except Exception:
        return True
    now = datetime.now()
    periyot = TUM_GOREVLER.get(gorev_id, {}).get("periyot", "gunluk")
    if periyot == "gunluk":
        return now.date() > baslangic.date()
    else:
        bugun_pzt   = (now - timedelta(days=now.weekday())).date()
        basl_pzt    = (baslangic - timedelta(days=baslangic.weekday())).date()
        return bugun_pzt > basl_pzt


async def get_gorevler_durumu(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM kullanici_gorevler WHERE user_id = ?", (user_id,)
        ) as cur:
            kayitlar = {r["gorev_id"]: dict(r) for r in await cur.fetchall()}

    sonuc = []
    for gorev_id, gorev in TUM_GOREVLER.items():
        kayit = kayitlar.get(gorev_id)
        if kayit and _periyot_bitti_mi(kayit["baslangic"], gorev_id):
            kayit = None

        ilerleme   = kayit["ilerleme"]   if kayit else 0
        tamamlandi = (kayit["tamamlandi"] == 1) if kayit else False

        sonuc.append({
            **gorev,
            "ilerleme":   ilerleme,
            "tamamlandi": tamamlandi,
        })
    return sonuc


async def gorev_ilerlet(user_id: int, tip: str, miktar: int = 1) -> list[str]:
    """
    Belirtilen tipteki görevleri ilerlet.
    Tamamlanan görevlerin ID listesini döndür (ödül zaten eklenir).
    """
    tamamlananlar: list[str] = []

    for gorev_id, gorev in TUM_GOREVLER.items():
        if gorev["tip"] != tip:
            continue

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM kullanici_gorevler WHERE user_id = ? AND gorev_id = ?",
                (user_id, gorev_id)
            ) as cur:
                kayit = await cur.fetchone()
                kayit = dict(kayit) if kayit else None

        if kayit and _periyot_bitti_mi(kayit["baslangic"], gorev_id):
            kayit = None

        if kayit and kayit["tamamlandi"]:
            continue

        yeni_ilerleme   = (kayit["ilerleme"] if kayit else 0) + miktar
        yeni_tamamlandi = 1 if yeni_ilerleme >= gorev["hedef"] else 0
        baslangic       = kayit["baslangic"] if kayit else _baslangic_zamani(gorev_id)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO kullanici_gorevler
                    (user_id, gorev_id, ilerleme, tamamlandi, baslangic)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, gorev_id) DO UPDATE SET
                    ilerleme   = excluded.ilerleme,
                    tamamlandi = excluded.tamamlandi,
                    baslangic  = excluded.baslangic
            """, (user_id, gorev_id, yeni_ilerleme, yeni_tamamlandi, baslangic))
            await db.commit()

        if yeni_tamamlandi:
            tamamlananlar.append(gorev_id)
            await update_cip(user_id, gorev["odul"])

    return tamamlananlar
