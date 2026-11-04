# Tahmince — Kararsızım'dan dönüşüm notları

Bu dosya, mevcut "Kararsızım" anket uygulamasının "Tahmince" tahmin ve puan uygulamasına dönüşümünü özetler.
Eski plan ([KARARSIZIM_PLAN.md](KARARSIZIM_PLAN.md)) tarihsel kayıt olarak kalır.

## Konsept
Üyeler sonucu gelecekte belli olacak konularda **tahmin sorusu** açar; diğer üyeler seçeneklerden birini seçerek **tahmin** yapar.
Süre bitince soru kapanır; soruyu açan kişi sonucu bildirir; doğru tahmin yapan her üye **10 puan** kazanır.
Puanlar yalnızca eğlence içindir; para, bahis, ödeme veya ödül sistemi yoktur.

## Durumlar
| Görünen durum | Veritabanı | Koşul |
|---|---|---|
| Tahmine açık | `status = open` | `closes_at > şimdi` |
| Sonuç bekliyor | `status = open` | `closes_at <= şimdi` (türetilir) |
| Sonuçlandı | `status = resolved` | doğru seçenek + açıklama + (opsiyonel) kaynak |
| İptal edildi | `status = cancelled` | gerekçe zorunlu, puan yok |

## Kurallar
- 2–4 seçenek, 5 kategori (Spor, Teknoloji, Eğlence, Günlük Hayat, Diğer), kapanış gelecekte olmalı.
- İlk tahminden sonra başlık, seçenekler, kapanış zamanı (ve sonuç ölçütü) değiştirilemez; açıklama ve kategori düzenlenebilir.
- Her üye soruya tek tahmin yapar, kapanışa kadar değiştirebilir. Soru sahibi kendi sorusuna tahmin yapamaz, puan alamaz.
- Yalnızca soru sahibi, yalnızca kapanıştan sonra, onay adımıyla ve bir kez sonucu bildirir. Sonuç sonradan değişmez.
- Henüz tahmin almamış soru silinebilir; tahmin almış soru silinemez.
- Puanlar tek işlemde ve yalnızca bir kez dağıtılır.

## Yetki
| | Misafir | Üye | Soru sahibi |
|---|---|---|---|
| Sorular, dağılım, sonuçlar, puan tablosu | ✔ | ✔ | ✔ |
| Tahmin yapma | giriş gerekir | ✔ (kendi sorusu hariç) | ✘ kendi sorusuna |
| Soru oluşturma | giriş gerekir | ✔ | ✔ |
| Düzenle / sil / sonuç / iptal | ✘ | ✘ başkasının sorusunda (404) | ✔ (kurallar dahilinde) |

## Eski veriler
`accounts` (kullanıcılar) ve `polls` (anketler, seçenekler, oylar) tabloları ve verileri **silinmedi, sıfırlanmadı**.
Eski anketler `/eski-anketler/` altında salt okunurdur; oylarından puan üretilmez. Eski adresler (`/anket/<id>/`, `/anketlerim/`, `/populer/`) yeni yerlerine yönlenir.

## Sayfalar
`/` (sekmeler + kategori) · `/soru/<id>/` · `/soru/yeni/` · `/tahminlerim/` · `/sorularim/` · `/puan-tablosu/` · `/eski-anketler/` · `/giris/` `/kayit/`
