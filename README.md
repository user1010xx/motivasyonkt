# Toniva Motivasyon Telegram Botu

Çağrı merkezi personellerinin **günlük çağrı adedi** ve **konuşma süresi** liderliğini Toniva CRM’den alıp Telegram’a motivasyon metni + liderlik kartı görseli gönderir.

> **Güvenlik:** Token, API key ve chat id **yalnızca ortam değişkenlerinde** tutulur. Repoya secret commit edilmez.

## Yetki modeli

| Yer | Davranış |
|-----|----------|
| **Özel sohbet** | Sadece `TELEGRAM_ADMIN_IDS` içindeki kullanıcıya yanıt verir; diğerleri sessizce yok sayılır |
| **Gruplar** | Bot eklendiğin herhangi bir grupta **admin** `/sabah` vb. çalıştırabilir; mesaj o gruba gider |
| **Zamanlayıcı** | `TELEGRAM_CHAT_ID` / `TELEGRAM_CHAT_IDS` listesindeki grup(lar)a otomatik gönderir |

## Komutlar (yalnızca admin)

| Komut | Açıklama |
|--------|----------|
| `/sabah` | Sabah motivasyon + kart |
| `/oglen` | Öğlen motivasyon + kart |
| `/aksam` | Akşam motivasyon + kart |
| `/test` | Hızlı deneme (öğlen) |
| `/durum` | Ayar özeti (secret değerleri göstermez) |
| `/start` | Yardım |

Varsayılan otomatik saatler (`Europe/Istanbul`): 09:00 / 13:00 / 18:00

## Railway env değişkenleri

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | evet | BotFather token |
| `TELEGRAM_ADMIN_IDS` | evet | Senin Telegram user id (örn. `123456789`) |
| `TELEGRAM_CHAT_ID` veya `TELEGRAM_CHAT_IDS` | zamanlayıcı için | Grup id; çoklu: `-100a,-100b` |
| `TONIVA_API_KEY` | canlıda evet | `tva_...` scope: `reports:read` |
| `TONIVA_BASE_URL` | hayır | varsayılan public API |
| `TIMEZONE` | hayır | `Europe/Istanbul` |
| `SCHEDULE_SABAH` / `OGLEN` / `AKSAM` | hayır | `HH:MM` |
| `ENABLE_SCHEDULE` | hayır | `true` / `false` |
| `MOCK_MODE` | hayır | `true` = örnek veri |

## Yerel geliştirme

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# .env doldur — ASLA commit etme
python run.py
```

Smoke test (Telegram/Toniva yok):

```bash
python scripts/smoke_test.py
```

## Mimari

```
bot/
  config.py         # env (secret yok)
  toniva_client.py  # performance + conversations yedek
  ranking.py
  messages.py
  card_image.py
  service.py
  main.py           # admin gate + komutlar + schedule
run.py
Procfile            # Railway worker
railway.toml
```

## Notlar

- Caption HTML; Telegram ~1024 karakter limiti.
- Performance alan adları tenant’a göre değişebilir; client esnek map kullanır.
- Grup chat id genelde `-100...` formatındadır (`getUpdates` ile bulunur).
