# Kahvehane Okey Botu

Discord için Türkçe Okey oyunu botu. Slash komutlarıyla masa kurma, düello, ekonomi sistemi ve rozet özelliklerine sahiptir.

## Çalıştırma

Workflow: **Discord Okey Botu** (`cd discord-bot && python main.py`)

### Gerekli Secret

| Secret | Nereden Alınır |
|--------|----------------|
| `DISCORD_BOT_TOKEN` | Discord Developer Portal → Uygulamanız → Bot → Token |

## Stack

- Python 3.11
- discord.py 2.x (slash commands / app_commands)
- aiosqlite (SQLite veritabanı)
- Pillow (profil kartı görseli)
- Dahili keep-alive HTTP sunucusu

## Proje Yapısı

```
discord-bot/
  main.py              # Giriş noktası
  src/
    bot.py             # Komutlar ve bot tanımı
    game/
      manager.py       # Oyun akışı ve masa yönetimi
      okey_engine.py   # Okey oyun motoru
    economy/
      db.py            # Veritabanı işlemleri
      gorevler.py      # Görev sistemi
      rozetler.py      # Rozet sistemi
    ui/
      views.py         # Lobi ve masa butonları
      duel_view.py     # Düello kabul/ret butonları
      render.py        # Profil kartı render
      market_views.py  # Market UI
  okey.db              # SQLite veritabanı (otomatik oluşur)
```

## Önemli Notlar

- Komut sync işlemi `on_ready` olayında yalnızca **bir kez** yapılır (`lobi_view_registered` bayrağı ile); yeniden bağlanmalarda duplicate oluşmaz.
- `on_guild_join`'da guild-özel sync **yapılmaz** — global komutlar tüm sunucularda otomatik görünür. Önceden yapılan guild sync'ler duplicate komutlara yol açıyordu.
- Düello `kabul` butonu `interaction.response.defer()` ile başlar; sonraki DB + kanal oluşturma işlemleri 3 saniyelik limiti aşsa bile panel doğru gönderilir.

## User Preferences

- Türkçe açıklama ve mesajlar tercih edilir.
