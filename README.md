# Kararsızım

Kararsız kaldığın konularda başkalarına anket açıp oy toplayabildiğin basit bir web uygulaması.
Django 5.2 + Supabase (PostgreSQL) + saf HTML/CSS/JS, Vercel'de çalışır.

- Misafirler anketleri görür ve oy verir. Üyeler ayrıca anket oluşturur ve kendi anketlerini siler.
- Anketlerde oluşturanın kullanıcı adı görünür, e-postası asla görünmez.
- Ayrıntılı tasarım: [docs/KARARSIZIM_PLAN.md](docs/KARARSIZIM_PLAN.md)

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

## Supabase

1. Supabase'de bir proje oluştur. Panelde **Connect** düğmesinden iki bağlantı dizesi al:
   - **Session pooler** (port 5432): migration'ları yerel makineden çalıştırmak için.
   - **Transaction pooler** (port 6543): Vercel'deki uygulama için.
2. Kullanıcı adı `postgres.<proje-ref>` biçimindedir. Parolada `@ # / :` gibi özel karakter kullanma.
3. Yerelden migration'ları çalıştır (`.env` içine Session pooler adresini yaz):

   ```bash
   .venv/bin/python manage.py migrate
   ```

   Bu, `polls.0003_enable_rls` ile tüm tablolarda Row Level Security'yi de açar. Politika eklenmediği için Supabase'in otomatik REST API'si bu tablolara erişemez; Django `postgres` rolüyle bağlandığı için etkilenmez.
4. **Yeni bir model/tablo eklediğinde** o tabloda da RLS'i açan bir migration yaz. Eski migration yeni tabloları kapsamaz.

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
