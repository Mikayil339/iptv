# Azərbaycan · Türkiyə · Rusiya IPTV

Televizo və digər IPTV tətbiqləri üçün birbaşa URL:

https://raw.githubusercontent.com/Mikayil339/iptv/main/playlist.m3u8

## Avtomatik yeniləmə

GitHub Actions hər 6 saatdan bir yoxlama aparır: Bakı vaxtı ilə təxminən **04:23, 10:23, 16:23, 22:23**. GitHub növbəsinə görə gecikmə mümkündür.

- Əvvəl kanalın HLS siyahısı və video fraqmenti yoxlanılır.
- Nasazlıq həmin işə düşmə daxilində təkrar yoxlanılır.
- İki ardıcıl işə düşmədə uğursuz olan kanal üçün eyni ölkə və kanal identifikatoruna uyğun ehtiyatlar yoxlanılır.
- Video fraqmenti alınan ehtiyat tapılarsa URL yenilənir. Keyfiyyət qeydi olan yüksək ölçülü alternativlərə üstünlük verilir.
- İşləyən ehtiyat tapılmasa kanal silinmir, son ünvan saxlanır.
- Ölkə qrupları və ümumi kanal sayı saxlanır. Sistem avtomatik yeni kanal əlavə etmir.
- Açıq ölkə siyahıları və Azərbaycan canlı yayım səhifəsi hər işə düşmədə yenidən oxunur. Yalnız konfiqurasiyadakı mənbələrdə yayımlanan yeni ünvanlar tapıla bilər.

[Vəziyyət hesabatı](STATUS.md) · [Yoxlamalar](https://github.com/Mikayil339/iptv/actions/workflows/refresh.yml)

`retry_next_run`: birinci uğursuz yoxlama; `replaced`: ehtiyatla əvəzləndi; `unavailable_kept`: ehtiyatlar da açılmadı, kanal saxlanıldı.

## Televizo

Pleylist ayarlarında avtomatik yeniləməni gündəlik aktivləşdirin. Mövcud link dəyişmir. Tətbiqdə həmin ayar yoxdursa, pleylisti əl ilə yeniləyin.

## Əl ilə işə salmaq

GitHub → Actions → Refresh IPTV playlist → Run workflow.

Lokal icra (Python 3.12, əlavə paket tələb olunmur):

```sh
python -m unittest discover -s tests -v
python scripts/refresh.py
```

## Məhdudiyyətlər

Video fraqmentinin alınması uzunmüddətli oynatma, düzgün kanal məzmunu, səs və sizin regionda əlçatanlıq zəmanəti deyil. Keyfiyyət qeydləri mənbələrə əsaslanır. Şifrələnmiş, abunə tələb edən və regional məhdudiyyətli yayımlar açılmaya bilər. Əsas yayım işləyirsə, lazımsız URL dəyişikliyi edilmir. Eyni identifikatoru olan alternativlər arasında uğurlu ilk mənbə seçilir; bütün yayımların faktiki görüntü keyfiyyəti ölçülmür.

GitHub Actions söndürülərsə, yazma icazəsi məhdudlaşdırılarsa və ya GitHub cədvəli gecikərsə yeniləmə dayanacaq. Açıq repozitoriyalarda 60 günlük fəaliyyətsizlikdən sonra cədvəl deaktiv edilə bilər; Actions səhifəsindən yenidən aktivləşdirilir. Hesabat hər uğurlu işə düşmədə repozitoriyaya yazılır.

Mənbələr `sources.json`, yadda saxlanan ehtiyatlar və uğursuzluq sayğacları `health.json` faylındadır. Heç bir şəxsi token və ya ayrıca server tələb olunmur.
