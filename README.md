# Azərbaycan · Türkiyə · Rusiya · Futbol və idman

## Pleylist URL

https://raw.githubusercontent.com/Mikayil339/iptv/main/playlist.m3u8

Bu açıq linki Televizo və digər IPTV tətbiqlərinə əlavə edin. Hesab, parol və ChatGPT tələb olunmur. Pleylist, mənbələr, loqolar və avtomatik yeniləmə bu GitHub repozitoriyasında saxlanılır. Əvvəlki ayrıca giriş xidmətindən asılılıq yoxdur.

## Avtomatik yeniləmə

GitHub Actions hər 6 saatdan bir — Bakı vaxtı ilə təxminən 04:23, 10:23, 16:23 və 22:23 — açıq mənbələri yenidən oxuyur, HLS siyahılarını və video fraqmentlərini yoxlayır. İki ardıcıl uğursuz yoxlamadan sonra işləyən ehtiyat mənbəni seçir. İşlək ehtiyat tapılmazsa kanal silinmir və vəziyyət hesabatında qeyd edilir. İşləyən HD alternativlərə və ölçülmüş daha qısa cavab müddətinə üstünlük verilir.

Əlavə HD kanallar avtomatik axtarılır. Futbol və idman kanalları Azərbaycan, rus, ingilis və türk dili məlumatlarına əsasən kataloqdan seçilir. Yalnız yoxlamadan keçən yeni yayımlar əlavə edilir. Giriş məlumatı tələb edən hesab linkləri və dəstəklənməyən DRM yayımları idxal edilmir. İctimai yayımların regional məhdudiyyətləri ola bilər; bütün oyunların göstərilməsi zəmanəti yoxdur.

TRT Belgesel Türkiyə qrupunda ayrıca saxlanılır, rəsmi yayımlar və ehtiyatlar təkrar yoxlanılır.

## Loqolar

Loqolar PNG formatında `logos/` qovluğuna yüklənir və həmin GitHub hesabından göstərilir. Xarici şəkil serveri sonradan bağlansa da saxlanılan loqo qalır. Loqolar hər həftə yoxlanılır; uğursuz şəkillər hər icrada yenidən sınanır. Real loqo tapılmayan kanal üçün görünən hərf nişanı yaradılır; bu, rəsmi kanal loqosu deyil. Ətraflı vəziyyət `logo_status.json` faylındadır.

[Vəziyyət](STATUS.md) · [Son nəticə](LAST_RUN.json) · [Avtomatik icralar](https://github.com/Mikayil339/iptv/actions/workflows/refresh.yml)

Televizo-da gündəlik avtomatik pleylist yeniləməsini aktivləşdirin. GitHub cədvəli gecikə və ya uzun fəaliyyətsizlikdən sonra dayandırıla bilər. Lazım olsa Actions → Refresh IPTV playlist → Run workflow ilə əl ilə başladın.

## Lokal icra

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/refresh.py
python scripts/update_logos.py
```

`source-group` yayım mənbəsinin ölkəsini saxlayır; `group-title` IPTV tətbiqində görünən qrupdur. İdman kanalları ayrıca qrupdadır.
