# Azərbaycan · Türkiyə · Rusiya · Futbol və idman

## Pleylist URL

https://raw.githubusercontent.com/Mikayil339/iptv/main/playlist.m3u8

Bu açıq linki  IPTV tətbiqlərinə əlavə edin. Hesab, parol tələb olunmur. Pleylist, mənbələr, loqolar və avtomatik yeniləmə bu GitHub repozitoriyasında saxlanılır. Əvvəlki ayrıca giriş xidmətindən asılılıq yoxdur.

## Avtomatik yeniləmə

GitHub Actions hər 6 saatdan bir — Bakı vaxtı ilə təxminən 04:23, 10:23, 16:23 və 22:23 — açıq mənbələri yenidən oxuyur, HLS siyahılarını və video fraqmentlərini yoxlayır. Cari link eyni icrada iki dəfə açılmazsa, kataloqlardakı və yadda saxlanmış ehtiyat linkləri yoxlayır və video fraqmenti açılan ilk alternativi həmin icrada pleylistə yazır. İşlək ehtiyat tapılmazsa kanal saxlanılır və vəziyyət hesabatında qeyd edilir. Alternativlər yoxlanarkən daha yüksək elan edilmiş keyfiyyətə üstünlük verilir.

Əlavə HD kanallar avtomatik axtarılır. Futbol və idman kanalları Azərbaycan, rus, ingilis və türk dili məlumatlarına əsasən kataloqdan seçilir. Yalnız yoxlamadan keçən yeni yayımlar əlavə edilir. Giriş məlumatı tələb edən hesab linkləri və dəstəklənməyən DRM yayımları idxal edilmir. İctimai yayımların regional məhdudiyyətləri ola bilər; bütün oyunların göstərilməsi zəmanəti yoxdur.

TRT Belgesel Türkiyə qrupunda ayrıca saxlanılır, rəsmi yayımlar və ehtiyatlar təkrar yoxlanılır.

## Loqolar

Loqolar PNG formatında `logos/` qovluğuna yüklənir və həmin GitHub hesabından göstərilir. Xarici şəkil serveri sonradan bağlansa da saxlanılan loqo qalır. Loqolar hər həftə yoxlanılır; uğursuz şəkillər hər icrada yenidən sınanır. Real loqo tapılmayan kanal üçün görünən hərf nişanı yaradılır; bu, rəsmi kanal loqosu deyil. Ətraflı vəziyyət `logo_status.json` faylındadır.

[Vəziyyət](STATUS.md) · [Son nəticə](LAST_RUN.json) · [Avtomatik icralar](https://github.com/Mikayil339/iptv/actions/workflows/refresh.yml)

## Lokal icra

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/refresh.py
python scripts/update_logos.py
```

`source-group` yayım mənbəsinin ölkəsini saxlayır; `group-title` IPTV tətbiqində görünən qrupdur. İdman kanalları ayrıca qrupdadır.

## Kino qrupları

`1080p Russian Movies` qrupuna yalnız ffprobe ilə video ölçüsü ən azı 1080p təsdiqlənən yayımlar daxil edilir. `Türk Filmləri və Dublyaj` üçün minimum 720p-dir. Cine 1 və Tivi 6 film xaricində proqramlar da yayımlaya bilər. Mövcud kanal zəifləyəndə və ya yoxlama alınmayanda silinmir, ölkə qrupuna qaytarılır. Sonrakı yoxlamada keyfiyyət bərpa olunarsa kino qrupuna qayıdır.

Kino mənbələri və kanal seçimi `cinema.json`, son yoxlama nəticələri `cinema_status.json` faylındadır. Hər 6 saatlıq GitHub Actions yenilənməsi kino mənbələrini də yenidən yoxlayır. Kanal adındakı HD yazısı keyfiyyət sübutu sayılmır.
