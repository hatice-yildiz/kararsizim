# Kararsızım — Proje Planı (Claude Code için)

> Bu dosya projenin tek doğruluk kaynağıdır. Claude Code ile çalışırken her fazın başında bu dosyayı referans ver (ör. `@KARARSIZIM_PLAN.md dosyasını oku ve Faz 1'i uygula`).
> Fazları **sırayla** ve **tek tek** uygula. Bir faz bitmeden ve test edilmeden sonrakine geçme.

---

## 1. Proje Özeti

**Kararsızım**, kullanıcıların kararsız kaldıkları konularda diğer kullanıcılara anket açarak danışabildiği basit bir web uygulamasıdır.

- Örnek: "Bugün sinemaya mı gitsem, yemeğe mi?" — 2 ile 5 arası seçenek.
- Takip / arkadaşlık mekanizması **yoktur**. Herkes platformdaki tüm anketleri görür.
- **Üye olmayanlar:** anketleri görüntüleyebilir ve oy kullanabilir.
- **Üyeler:** ek olarak anket oluşturabilir, kendi anketlerini görebilir/silebilir.
- Anketlerde oluşturanın **kullanıcı adı** görünür, **e-posta asla görünmez**.

**İlk hedef: çalışan bir prototip.** Karmaşık teknolojilerden kaçın; sonradan adım adım geliştirilecek.

---

## 2. Teknoloji Yığını

| Katman | Teknoloji | Not |
|---|---|---|
| Dil | Python 3.12 | |
| Backend | Django 5.2 (LTS) | Django'nun kendi auth, form ve template sistemi kullanılacak |
| Veritabanı | Supabase (PostgreSQL) | Django ORM ile doğrudan PostgreSQL olarak bağlanılacak. Supabase Auth / supabase-py **kullanılmayacak** |
| Frontend | Saf HTML + CSS + JavaScript | Framework yok (React, Vue, Tailwind, Bootstrap yok). Django template'leri ile sunucu tarafında render |
| Statik dosyalar | WhiteNoise | |
| Deployment | Vercel | Python runtime (WSGI) |

**Python paketleri (requirements.txt):**
```
Django>=5.2,<6.0
psycopg[binary]
dj-database-url
python-dotenv
whitenoise
```
Bunların dışında paket eklenmeden önce gerekçesi belirtilmeli.

---

## 3. Genel Kurallar (Claude Code için)

1. Arayüz dili **Türkçe**. `LANGUAGE_CODE = "tr"`, `TIME_ZONE = "Europe/Istanbul"`, `USE_TZ = True`.
2. Kod (değişken, fonksiyon, model adları) **İngilizce**; kullanıcıya görünen metinler Türkçe.
3. Gizli bilgiler (`SECRET_KEY`, `DATABASE_URL`) asla koda yazılmaz; `.env` dosyasından okunur. `.env` → `.gitignore`. Bir `.env.example` dosyası oluşturulur.
4. Tüm form doğrulamaları **sunucu tarafında** yapılır; JavaScript yalnızca kullanıcı deneyimi içindir.
5. CSRF koruması tüm POST formlarında açık kalır.
6. Basit tut: class-based view yerine okunabilirse function-based view tercih edilebilir. Gereksiz soyutlama yok.
7. Her fazın sonunda: `python manage.py check`, migration'lar ve faz için yazılan testler çalıştırılır (`python manage.py test`).
8. Her faz sonunda kısa bir özet ver: ne yapıldı, nasıl test edilir, bilinen eksikler.

---

## 4. Proje Yapısı

```
kararsizim/
├── config/                 # Django proje ayarları
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/               # Kullanıcı modeli, kayıt, giriş, çıkış
├── polls/                  # Anket, seçenek, oy
├── templates/
│   ├── base.html
│   ├── accounts/
│   └── polls/
├── static/
│   ├── css/style.css
│   └── js/
│       ├── poll_form.js    # Seçenek ekle/çıkar
│       └── main.js
├── manage.py
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
└── README.md
```

---

## 5. Veri Modeli

### 5.1 `accounts.User` (özel kullanıcı modeli)
Projenin **en başında** tanımlanmalı (`AUTH_USER_MODEL = "accounts.User"`), sonradan değiştirmek zordur.

- `AbstractUser`'dan türetilir.
- `email`: `EmailField(unique=True)` — zorunlu, büyük/küçük harf duyarsız benzersiz olmalı (kaydetmeden önce küçük harfe çevir).
- `username`: zorunlu, benzersiz. Kurallar: 3–20 karakter, yalnızca harf, rakam, alt çizgi ve nokta. Büyük/küçük harf duyarsız benzersizlik kontrolü yapılmalı.
- `first_name`, `last_name` kullanılmayacak (formda gösterilmez).
- **Giriş e-posta _veya_ kullanıcı adı + parola ile** yapılır (özel authentication backend; `@` içeren değer e-posta, diğeri kullanıcı adı sayılır). *(Kullanıcı kararıyla genişletildi: ilk plan yalnızca e-postaydı.)*

### 5.2 `polls.Poll`
| Alan | Tip | Not |
|---|---|---|
| `question` | CharField(max_length=200) | Zorunlu |
| `description` | TextField(max_length=500, blank=True) | Opsiyonel açıklama |
| `created_by` | FK → User, on_delete=CASCADE, related_name="polls" | |
| `created_at` | DateTimeField(auto_now_add=True) | |
| `is_active` | BooleanField(default=True) | İleride anketi kapatmak için |

- `Meta.ordering = ["-created_at"]`
- Yardımcı: `total_votes` (property veya `annotate` ile).

### 5.3 `polls.Option`
| Alan | Tip | Not |
|---|---|---|
| `poll` | FK → Poll, CASCADE, related_name="options" | |
| `text` | CharField(max_length=100) | |
| `order` | PositiveSmallIntegerField | Gösterim sırası |

- Bir ankette **en az 2, en fazla 5** seçenek. Aynı ankette tekrar eden seçenek metni olamaz (büyük/küçük harf ve baş/son boşluk duyarsız).

### 5.4 `polls.Vote`
| Alan | Tip | Not |
|---|---|---|
| `poll` | FK → Poll, CASCADE, related_name="votes" | Sorgu kolaylığı için |
| `option` | FK → Option, CASCADE, related_name="votes" | |
| `user` | FK → User, null=True, blank=True, SET_NULL | Giriş yapmışsa |
| `voter_key` | CharField(max_length=64) | Tekrar oy engelleme anahtarı |
| `created_at` | DateTimeField(auto_now_add=True) | |

- `UniqueConstraint(fields=["poll", "voter_key"])` → her seçmen bir ankete **tek oy**.
- `voter_key` üretimi:
  - Giriş yapmış kullanıcı: `"u:<user.id>"`
  - Anonim kullanıcı: tarayıcıda saklanan `voter_id` çerezi (UUID4, 1 yıl ömürlü, `HttpOnly`, `SameSite=Lax`) → `"a:<uuid>"`. Çerez yoksa ilk ziyarette bir middleware oluşturur.
- Prototip için bilinen sınırlama: anonim kullanıcı çerezleri silerek tekrar oy verebilir. Kabul edilebilir; ileride iyileştirilecek.
- Kullanıcı kendi anketine oy verebilir (prototipte serbest).
- Oy verildikten sonra **değiştirilemez** (prototip).
- Seçeneğin gerçekten o ankete ait olduğu sunucuda kontrol edilir.

---

## 6. Sayfalar ve URL'ler

| URL | Sayfa | Erişim |
|---|---|---|
| `/` | Ana sayfa: tüm anketler, en yeni üstte, sayfalama (sayfa başı 10) | Herkes |
| `/anket/<id>/` | Anket detayı: soru, açıklama, oluşturan kullanıcı adı, tarih, seçenekler / sonuçlar | Herkes |
| `/anket/<id>/oy/` | Oy verme (yalnızca POST) | Herkes |
| `/anket/yeni/` | Anket oluşturma formu | Yalnızca üyeler (`login_required`, girişe yönlendir, sonra geri dön) |
| `/anket/<id>/sil/` | Anketi sil (onay sayfası + POST) | Yalnızca anket sahibi |
| `/anketlerim/` | Kullanıcının kendi anketleri | Yalnızca üyeler |
| `/kayit/` | Kayıt: kullanıcı adı, e-posta, parola, parola tekrar | Misafirler |
| `/giris/` | Giriş: e-posta veya kullanıcı adı + parola | Misafirler |
| `/cikis/` | Çıkış (yalnızca POST) | Üyeler |

### Davranış detayları
- **Ana sayfa kartı:** soru, kullanıcı adı (`@kullaniciadi`), göreli zaman ("2 saat önce" — Django `timesince`), seçenek sayısı, toplam oy. Kart tıklanınca detaya gider.
- **Detay sayfası:**
  - Kullanıcı henüz oy vermediyse → seçenekler büyük, tıklanabilir renkli butonlar olarak gösterilir. Seçince form gönderilir.
  - Oy verdiyse → sonuçlar: her seçenek için yüzde ve oy sayısı, renkli ilerleme çubuğu; kullanıcının seçtiği işaretli; en çok oy alan vurgulu.
  - ~~"Oy vermeden sonuçları gör" bağlantısı (`?sonuclar=1`)~~ — **kaldırıldı** (kullanıcı kararı): sonuçlar yalnızca oy verdikten sonra görünür.
  - Sayfanın üstünde "← Tüm anketler" geri bağlantısı bulunur.
  - Anket sahibine "Sil" butonu görünür.
- **Oy sonrası:** detay sayfasına yönlendir + Django `messages` ile "Oyun kaydedildi!" bildirimi. Tekrar oy denemesinde "Bu ankete zaten oy verdin." mesajı.
- **Kayıt sonrası:** otomatik giriş yap, ana sayfaya yönlendir.
- **Gezinme çubuğu:** logo "Kararsızım", "Anket Oluştur" butonu (misafirse giriş sayfasına götürür), giriş yapmışsa kullanıcı adı + "Anketlerim" + "Çıkış"; değilse "Giriş" + "Kayıt Ol".
- 404 ve 500 için basit, tasarıma uygun Türkçe sayfalar.

---

## 7. Anket Oluşturma Formu

- Alanlar: Soru (zorunlu), Açıklama (opsiyonel), Seçenekler.
- Varsayılan olarak **2 seçenek alanı** gösterilir.
- "+ Seçenek ekle" butonu (5'e ulaşınca gizlenir/devre dışı kalır), her ek seçeneğin yanında "×" kaldır butonu (2'nin altına inilemez). Bu davranış `static/js/poll_form.js` ile yapılır.
- Sunucu tarafında: boş seçenekler yok sayılır, kalan seçenek sayısı 2–5 arası olmalı, tekrar eden seçenek olmamalı. Hata mesajları Türkçe ve alanın yanında gösterilir; kullanıcının girdiği veriler korunur.
- Anket ve seçenekler tek bir veritabanı transaction'ı (`transaction.atomic`) içinde kaydedilir.
- Uygulama yöntemi: basit bir Django `Form` + `formset` veya `option_1 … option_5` alanları — hangisi daha sade ise.

---

## 8. Arayüz Tasarımı

**Hedef:** açık arka planlı, canlı renkli, renklerin üstüne açık ton (tint) atılmış, temiz ve ferah bir arayüz. Mobil öncelikli (mobile-first), duyarlı.

### 8.1 Renk paleti (CSS değişkenleri)
```css
:root {
  --bg: #FAF9F6;            /* Sıcak kırık beyaz arka plan */
  --surface: #FFFFFF;       /* Kartlar */
  --text: #1F2330;          /* Ana metin */
  --text-muted: #6B7080;
  --border: #ECEAF2;

  --primary: #7C3AED;       /* Canlı mor — ana marka rengi */
  --primary-tint: #F1EAFE;  /* Morun açık tonu */

  /* Seçenek renkleri (sırayla her seçeneğe bir renk) */
  --c1: #FF5A5F; --c1-tint: #FFE8E9;   /* Mercan */
  --c2: #14B8A6; --c2-tint: #DDF7F3;   /* Turkuaz */
  --c3: #F59E0B; --c3-tint: #FEF1D9;   /* Kehribar */
  --c4: #3B82F6; --c4-tint: #E3EEFE;   /* Mavi */
  --c5: #EC4899; --c5-tint: #FDE4F1;   /* Pembe */

  --success: #16A34A;
  --danger: #DC2626;

  --radius: 16px;
  --shadow: 0 4px 20px rgba(31, 35, 48, 0.06);
}
```

### 8.2 Kurallar
- **Yazı tipi:** Google Fonts'tan "Plus Jakarta Sans" (Türkçe karakter desteği var), yedek `system-ui, sans-serif`.
- **Kartlar:** beyaz zemin, 16px köşe, yumuşak gölge, üstte ince renkli şerit veya sol kenarlık.
- **Seçenek butonları:** her seçenek kendi renginin tint'i zeminli, rengin kendisi kenarlık/metin; hover'da renk biraz koyulaşır ve hafif büyür (`transform: translateY(-2px)`).
- **Sonuç çubukları:** tint zemin üzerinde dolu renkli çubuk, genişlik yüzdeye göre, sayfa açılışında CSS geçişi ile soldan dolarak animasyonlu.
- **Ana buton ("Anket Oluştur"):** `--primary` zemin, beyaz yazı, tam yuvarlak köşe (pill).
- **Bildirim mesajları:** sayfanın üstünde tint zeminli kutular, birkaç saniye sonra JS ile kaybolur.
- Maksimum içerik genişliği ~720px, ortalanmış; bol boşluk.
- Erişilebilirlik: yeterli kontrast, odak (`:focus-visible`) halkaları, form alanlarında `<label>`.
- Hafif ve emoji destekli boş durum metinleri (ör. "Henüz anket yok. İlk kararsızlığı sen paylaş! 🤔").

---

## 9. Supabase Bağlantısı

- Supabase projesinin PostgreSQL bağlantı dizesi `DATABASE_URL` olarak `.env`'e yazılır ve `dj-database-url` ile okunur.
- **Vercel (serverless) için:** Supabase **Connection Pooler — Transaction mode (port 6543)** adresi kullanılır. Ayarlar:
  - `CONN_MAX_AGE = 0`
  - `DISABLE_SERVER_SIDE_CURSORS = True` (transaction pooler ile gerekli)
  - `sslmode=require`
- **Migration'lar** yerel makineden, Supabase **Session pooler (5432)** veya doğrudan bağlantı adresiyle çalıştırılır: `python manage.py migrate`.
- Yerel geliştirmede istenirse `DATABASE_URL` tanımlı değilse SQLite'a düşülebilir (opsiyonel, geliştirme kolaylığı için).
- **Güvenlik notu:** Django tabloları `public` şemasında oluşur ve Supabase'in otomatik REST API'si üzerinden erişilebilir hale gelebilir. Tüm tablolarda **RLS (Row Level Security) etkinleştirilmeli** ve hiçbir politika eklenmemeli; Django `postgres` rolüyle bağlandığı için etkilenmez, ama dış API erişimi kapanır. Bunu bir data migration (`RunSQL`) ile yap.

---

## 10. Vercel Deployment

- Önce Vercel'in **güncel Django/Python dokümantasyonu** kontrol edilmeli; yaklaşım değişmiş olabilir.
- Temel yaklaşım:
  - `config/wsgi.py` içinde `app = application` satırı eklenir (Vercel bu değişkeni arar).
  - `vercel.json` ile tüm istekler WSGI uygulamasına yönlendirilir.
  - Statik dosyalar WhiteNoise ile servis edilir; `collectstatic` build sırasında çalıştırılır (veya prototipte `staticfiles/` klasörü commit edilir — hangisi Vercel'de güvenilir çalışıyorsa).
- Vercel ortam değişkenleri: `SECRET_KEY`, `DATABASE_URL`, `DEBUG=False`, `ALLOWED_HOSTS` (ör. `.vercel.app`), `CSRF_TRUSTED_ORIGINS` (ör. `https://*.vercel.app`).
- Production ayarları: `DEBUG=False`, `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`.
- README'ye adım adım deploy talimatı yazılır.

---

## 11. Fazlar

Her fazı aşağıdaki hazır prompt ile Claude Code'a ver. Faz bitince test et, sorun yoksa sonrakine geç.

### Faz 1 — Kurulum ve İskelet
**Kapsam:** Django projesi, `accounts` ve `polls` uygulamaları, ayarlar, `.env` yapısı, özel `User` modeli (henüz arayüz yok), `base.html` iskeleti, statik dosya yapısı, Supabase bağlantısı, ilk migration.
**Bitti sayılır:** `python manage.py runserver` ile boş bir ana sayfa açılıyor, migration'lar Supabase'de çalışmış, admin paneline giriş yapılabiliyor.

> **Prompt:**
> `@KARARSIZIM_PLAN.md dosyasını baştan sona oku. Sadece Faz 1'i uygula: Django projesini bölüm 4'teki yapıya göre kur, bölüm 2'deki paketleri requirements.txt'ye ekle, bölüm 5.1'deki özel User modelini oluştur, .env / .env.example / .gitignore dosyalarını hazırla, bölüm 9'a göre Supabase bağlantısını ayarla ve base.html iskeletini oluştur. Bitince migration'ları çalıştırmam için gereken adımları ve test etme yolunu özetle.`

### Faz 2 — Üyelik (Kayıt / Giriş / Çıkış)
**Kapsam:** Kayıt formu (kullanıcı adı, e-posta, parola x2), e-posta ile giriş, POST ile çıkış, navbar'ın giriş durumuna göre değişmesi, Türkçe hata mesajları, testler.
**Bitti sayılır:** Kayıt olunup otomatik giriş yapılıyor; aynı e-posta/kullanıcı adıyla ikinci kayıt reddediliyor; e-posta hiçbir sayfada görünmüyor.

> **Prompt:**
> `@KARARSIZIM_PLAN.md — Faz 2'yi uygula: bölüm 5.1 ve 6'daki kurallara göre kayıt, giriş (e-posta + parola) ve çıkış akışlarını yap. Navbar'ı bölüm 6'daki gibi giriş durumuna göre düzenle. Kullanıcı adı ve e-posta benzersizliği ile doğrulama kuralları için testler yaz. Şimdilik sade bir stil yeterli.`

### Faz 3 — Anket Oluşturma ve Listeleme
**Kapsam:** `Poll` ve `Option` modelleri, admin kaydı, anket oluşturma formu (bölüm 7) ve dinamik seçenek JS'i, ana sayfa listesi + sayfalama, detay sayfası (henüz oylama yok), "Anketlerim", anket silme.
**Bitti sayılır:** Üye 2–5 seçenekli anket oluşturabiliyor; misafir "Anket Oluştur"a basınca girişe yönlendiriliyor; ana sayfada tüm anketler kullanıcı adıyla görünüyor.

> **Prompt:**
> `@KARARSIZIM_PLAN.md — Faz 3'ü uygula: bölüm 5.2–5.3'teki Poll ve Option modellerini, bölüm 7'deki anket oluşturma formunu (static/js/poll_form.js ile seçenek ekle/çıkar dahil), ana sayfa listesini, detay sayfasını, Anketlerim sayfasını ve sahibine özel silmeyi yap. 2–5 seçenek ve tekrar eden seçenek doğrulamaları için testler yaz.`

### Faz 4 — Oylama ve Sonuçlar
**Kapsam:** `Vote` modeli, anonim seçmen çerezi middleware'i, oy verme view'ı, tekrar oy engelleme, sonuç gösterimi (yüzde, sayı, çubuk), mesajlar, ana sayfada toplam oy sayısı.
**Bitti sayılır:** Misafir ve üye oy verebiliyor; aynı tarayıcı/kullanıcı ikinci kez oy veremiyor; sonuçlar doğru yüzdelerle görünüyor.

> **Prompt:**
> `@KARARSIZIM_PLAN.md — Faz 4'ü uygula: bölüm 5.4'teki Vote modelini ve voter_key mantığını (anonimler için voter_id çerezi oluşturan middleware dahil), oy verme akışını ve bölüm 6'daki sonuç gösterimini yap. Tekrar oy engelleme, başka ankete ait seçeneğe oy verme denemesi ve yüzde hesabı için testler yaz.`

### Faz 5 — Arayüz Tasarımı
**Kapsam:** Bölüm 8'deki tasarımın tamamı: renk değişkenleri, yazı tipi, kartlar, renkli seçenek butonları, animasyonlu sonuç çubukları, form stilleri, bildirimler, boş durumlar, 404/500 sayfaları, mobil uyum.
**Bitti sayılır:** Tüm sayfalar tutarlı, mobilde ve masaüstünde düzgün görünüyor.

> **Prompt:**
> `@KARARSIZIM_PLAN.md — Faz 5'i uygula: bölüm 8'deki tasarım sistemini static/css/style.css'te kur ve tüm template'lere uygula. Framework kullanma, saf CSS ve gerektiği kadar saf JavaScript kullan. Mobil öncelikli yap. Bitince hangi sayfaları kontrol etmem gerektiğini listele.`

### Faz 6 — Vercel'e Yayın
**Kapsam:** Production ayarları, `vercel.json`, WSGI düzenlemesi, statik dosyalar, Supabase RLS migration'ı, README'de deploy talimatı.
**Bitti sayılır:** Uygulama `*.vercel.app` adresinde çalışıyor; kayıt, anket oluşturma ve oylama canlıda sorunsuz.

> **Prompt:**
> `@KARARSIZIM_PLAN.md — Faz 6'yı uygula: bölüm 9 ve 10'a göre uygulamayı Vercel'e hazırla. Önce Vercel'in güncel Django dokümantasyonunu kontrol et. Supabase tablolarında RLS'i açan migration'ı ekle. README.md'ye yerel kurulum ve Vercel deploy adımlarını Türkçe yaz. Benim Vercel panelinde yapmam gerekenleri ayrıca madde madde listele.`

---

## 12. Prototip Kapsamı DIŞINDA (sonraki adımlar)

Prototip tamamlandıktan sonra sırayla değerlendirilecek fikirler:
- Anketi kapatma / süre sınırı (`is_active`, bitiş tarihi)
- Oyu değiştirme
- Arama ve sıralama (en yeni, en çok oy alan)
- Kategoriler/etiketler (yemek, eğlence, alışveriş…)
- Anket paylaşım bağlantısı (WhatsApp vb.) ve Open Graph önizlemesi
- Parola sıfırlama (e-posta gönderimi)
- Hız sınırlama ve spam önlemleri (anonim oylar için daha güçlü koruma)
- Uygunsuz içerik bildirme ve moderasyon
- Karanlık mod
- Yorum yapma

---

## 13. Kabul Kriterleri (Prototip Bitti Kontrol Listesi)

- [ ] Misafir tüm anketleri görebiliyor ve oy verebiliyor
- [ ] Misafir anket oluşturmaya çalışınca giriş sayfasına yönlendiriliyor
- [ ] Kayıt: kullanıcı adı + e-posta + parola; e-posta ve kullanıcı adı benzersiz
- [ ] Giriş e-posta veya kullanıcı adı + parola ile yapılıyor
- [ ] Anketlerde kullanıcı adı görünüyor, e-posta hiçbir yerde görünmüyor
- [ ] Anket en az 2, en fazla 5 seçenekle oluşturulabiliyor
- [ ] Aynı kişi aynı ankete ikinci kez oy veremiyor
- [ ] Sonuçlar yüzde ve oy sayısıyla görünüyor
- [ ] Anket sahibi anketini silebiliyor
- [ ] Arayüz açık arka planlı, canlı renkli ve mobil uyumlu
- [ ] Uygulama Vercel'de, veriler Supabase'de çalışıyor
