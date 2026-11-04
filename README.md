# Tahmince

**Tahminini yap, sonucu gör!** Gelecekte sonucu belli olacak konularda tahmin soruları açılır, üyeler
seçeneklerden birini seçerek tahmin yapar. Süre bitince soru kapanır; sonucu soruyu açan kişi bildirir ve
doğru bilenler 10 puan kazanır. Puanlar yalnızca eğlence içindir (para, bahis, ödeme, ödül yok).

Django 5.2 + Supabase (PostgreSQL) + saf HTML/CSS/JS, Vercel'de çalışır.

## Nasıl çalışır

- **Misafirler** soruları, tahmin dağılımını, sonuçları ve puan tablosunu görür. Tahmin yapmak, soru açmak ve puan kazanmak için giriş gerekir.
- **Üyeler** 2-4 seçenekli, kategorili ve kapanış zamanlı soru açar. Her soruya tek tahmin yapar, kapanışa kadar değiştirebilir. Kendi sorusuna tahmin yapamaz ve kendi sorusundan puan kazanamaz.
- **Sonuç:** Yalnızca soruyu açan kişi, yalnızca kapanıştan sonra, onay adımıyla ve bir kez doğru seçeneği bildirir. Belirlenemiyorsa gerekçeyle iptal eder (kimseye puan verilmez).
- **Durumlar:** Tahmine açık → Sonuç bekliyor (süre doldu) → Sonuçlandı ya da İptal edildi. "Sonuç bekliyor" ayrı saklanmaz, kapanış zamanından türetilir.
- **Eski anketler:** Tahmince'den önceki "Kararsızım" anketleri, seçenekleri ve oyları kaldırıldı (üretimden kalıcı silindi). `polls` uygulaması yalnızca geçmiş migration zinciri için boş tablolarla duruyor.
- Kullanıcı adı görünür, e-posta hiçbir sayfada görünmez. Giriş e-posta **veya** kullanıcı adıyla yapılır.

## Güvenlik ve kurallar nerede uygulanır

1. **Sunucu kodu** (`predictions/services.py`): tüm yazma işlemleri tek veritabanı işleminde, soru satırı kilitlenerek yapılır. Sonuçlandırma `UPDATE ... WHERE status='open'` ile tek seferliktir; puanlar yalnızca bu geçişi kazanan işlemde yazılır.
2. **Veritabanı kısıtları ve tetikleyicileri** (`predictions/migrations/`): benzersiz tahmin, tutarlı durum, geçerli puan ve (PostgreSQL) kapanış sonrası tahmin, kendi soruna tahmin, kilitli alanlar, değişmez sonuç ve tek seferlik puan tetikleyicileri.
3. **RLS:** Tüm tablolarda Row Level Security açıktır ve politika yoktur; Supabase'in otomatik REST API'si hiçbir tabloya erişemez. Django `postgres` rolüyle bağlanır, etkilenmez. Gizli anahtarlar yalnızca sunucu ortam değişkenlerindedir.

Ayrıntılı tasarım için eski plan: [docs/KARARSIZIM_PLAN.md](docs/KARARSIZIM_PLAN.md) (Tahmince dönüşümü için `docs/TAHMINCE.md`).

## Yerel kurulum

Python 3.12 gerekir.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # SECRET_KEY değerini değiştir
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser   # isteğe bağlı, /admin/ için
.venv/bin/python manage.py runserver
```

`.env` içinde `DATABASE_URL` boşsa yerel `db.sqlite3` kullanılır. Doluysa **gerçek Supabase veritabanına** bağlanır.

Testler (SQLite ile çalışsın diye `DATABASE_URL` boş verilir; yoksa Django Supabase'de test veritabanı açmaya çalışır):

```bash
DATABASE_URL= .venv/bin/python manage.py test
```

PostgreSQL tetikleyici testleri (`predictions/tests_postgres.py`) SQLite'ta atlanır. Onları çalıştırmak için yerel/geçici bir PostgreSQL gerekir (üretim veritabanına bağlama):

```bash
DATABASE_URL=postgresql://kullanici@localhost:5432/postgres .venv/bin/python manage.py test
```

Yerel görsel deneme için örnek veri (yalnızca DEBUG + SQLite'ta çalışır):

```bash
DATABASE_URL= .venv/bin/python manage.py migrate && DATABASE_URL= .venv/bin/python manage.py seed_demo
```

## Supabase

1. Supabase'de bir proje oluştur. Panelde **Connect** düğmesinden iki bağlantı dizesi al:
   - **Session pooler** (port 5432): migration'ları yerel makineden çalıştırmak için.
   - **Transaction pooler** (port 6543): Vercel'deki uygulama için.
2. Kullanıcı adı `postgres.<proje-ref>` biçimindedir. Parolada `@ # / :` gibi özel karakter kullanma.
3. Yerelden migration'ları çalıştır (`.env` içine Session pooler adresini yaz):

   ```bash
   .venv/bin/python manage.py migrate
   ```

   Bu, `polls.0003_enable_rls` ve `predictions.0002_db_guards` ile tüm tablolarda Row Level Security'yi açar ve tetikleyicileri kurar. Politika eklenmediği için Supabase'in otomatik REST API'si bu tablolara erişemez; Django `postgres` rolüyle bağlandığı için etkilenmez.
4. **Yeni bir model/tablo eklediğinde** o tabloda da RLS'i açan bir migration yaz. Eski migration yeni tabloları kapsamaz.
5. **Mevcut veriler:** `predictions` migration'ları yeni tablolar ekler; `accounts` (kullanıcılar) tablosuna dokunmaz.

## Vercel'e yayın

Vercel `manage.py` dosyasını bulup Django'yu otomatik tanır; `vercel.json` gerekmez. Build sırasında `collectstatic` kendiliğinden çalışır ve statik dosyalar CDN'den sunulur.

1. [vercel.com/new](https://vercel.com/new) adresinden GitHub'daki `kararsizim` reposunu içe aktar. Framework otomatik olarak Django seçilir; build ayarlarına dokunma.
2. **Settings → Environment Variables** bölümüne ekle (Production için):

   | Ad | Değer |
   |---|---|
   | `SECRET_KEY` | Uzun rastgele bir değer. Üretmek için: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"` |
   | `DATABASE_URL` | Supabase **Transaction pooler** (6543) bağlantı dizesi |
   | `DEBUG` | `False` (verilmezse zaten kapalıdır) |

   `ALLOWED_HOSTS` ve `CSRF_TRUSTED_ORIGINS` için `*.vercel.app` adresleri Vercel'in sistem değişkenlerinden otomatik eklenir (**Settings → Environment Variables → Automatically expose System Environment Variables** açık olmalı). Kendi alan adını bağlarsan şunları da ekle: `ALLOWED_HOSTS=alanadin.com` ve `CSRF_TRUSTED_ORIGINS=https://alanadin.com` (virgülle birden fazla yazılabilir).
3. **Deploy** et. Sonraki her `git push` yeni bir yayın başlatır.
4. Yayından sonra kontrol et: ana sayfa, kayıt, anket oluşturma, oy verme, çıkış.

Notlar:
- Migration'lar Vercel build'inde çalışmaz; yukarıdaki gibi yerelden çalıştırılır.
- Bağımlılıklar hem `requirements.txt` hem `pyproject.toml` içinde tutulur; ikisini birlikte güncelle.
- Anonim oylar `voter_id` çerezine bağlıdır; çerezleri silen kişi tekrar oy verebilir (bilinen prototip sınırlaması).
