"""PyBionic Web — общий дизайн и языки для веб-страниц ботов.

Исходник лежит в templates/pybionic_web.py, копии в папках ботов делает tools/sync_shared.py.

Как пользоваться в боте:

    import pybionic_web as web

    def do_GET(self):
        lang = web.resolve_lang(self)
        T = web.translator(lang)
        body = web.card(T("w_upload_title"), web.dropzone("file", T("drop_or_click"), "MP4, MP3"))
        web.send_page(self, lang, title=T("w_title"), subtitle=T("w_sub"), emoji="⚡", body=body, script="...")

Язык страницы: ?lang=xx → cookie pb_lang → язык приложения (PYBIONIC_LANG) → en.
Он не меняет язык бота в Telegram — там у каждого человека свой язык.
Тексты: сначала ключ из locales.json бота (обычно w_*), потом общий словарь COMMON ниже.
"""

from __future__ import annotations

import html as _html
import json
import re as _re
import os
import urllib.parse
from typing import Any, Callable, Iterable

try:
    from i18n import SUPPORTED_LANGUAGES, _candidate_langs, get_locales_dict, normalize_lang_tag
except Exception:  # бот без i18n
    SUPPORTED_LANGUAGES = [("ru", "Русский"), ("en", "English")]

    def normalize_lang_tag(raw):  # type: ignore[no-redef]
        return (raw or "en").lower()

    def _candidate_langs(tag):  # type: ignore[no-redef]
        return [tag, "en", "ru"]

    def get_locales_dict():  # type: ignore[no-redef]
        return {}

LANG_ORDER = ["ru", "en", "tg", "uz", "tr", "es", "de", "fr", "it", "pt", "pl", "uk",
              "kk", "ky", "az", "ar", "fa", "hi", "zh-cn", "ja", "ko", "id", "vi", "th"]
LANG_CODES = {c for c, _ in SUPPORTED_LANGUAGES} | set(LANG_ORDER)
RTL = {"ar", "fa"}
esc = _html.escape


def _table(raw: str) -> dict[str, dict[str, str]]:
    """Строки вида  key = ru | en | tg | ...  (24 языка в порядке LANG_ORDER)."""
    out: dict[str, dict[str, str]] = {}
    for line in raw.strip().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, rest = line.partition("=")
        vals = [v.strip() for v in rest.split("|")]
        out[key.strip()] = dict(zip(LANG_ORDER, vals))
    return out


# Порядок: ru | en | tg | uz | tr | es | de | fr | it | pt | pl | uk | kk | ky | az | ar | fa | hi | zh-cn | ja | ko | id | vi | th
COMMON = _table("""
language = Язык | Language | Забон | Til | Dil | Idioma | Sprache | Langue | Lingua | Idioma | Język | Мова | Тіл | Тил | Dil | اللغة | زبان | भाषा | 语言 | 言語 | 언어 | Bahasa | Ngôn ngữ | ภาษา
theme = Тема | Theme | Намуди зоҳирӣ | Ko‘rinish | Tema | Tema | Design | Thème | Tema | Tema | Motyw | Тема | Көрініс | Тема | Mövzu | المظهر | پوسته | थीम | 主题 | テーマ | 테마 | Tema | Giao diện | ธีม
online = Работает | Online | Фаъол | Ishlayapti | Çevrimiçi | En línea | Online | En ligne | Online | Online | Online | Працює | Жұмыс істейді | Иштеп жатат | Onlayn | متصل | آنلاین | ऑनलाइन | 在线 | オンライン | 온라인 | Daring | Trực tuyến | ออนไลน์
port = Порт | Port | Порт | Port | Port | Puerto | Port | Port | Porta | Porta | Port | Порт | Порт | Порт | Port | المنفذ | پورت | पोर्ट | 端口 | ポート | 포트 | Port | Cổng | พอร์ต
choose_file = Выберите файл | Choose a file | Файлро интихоб кунед | Faylni tanlang | Dosya seçin | Elige un archivo | Datei wählen | Choisissez un fichier | Scegli un file | Escolha um arquivo | Wybierz plik | Виберіть файл | Файлды таңдаңыз | Файлды тандаңыз | Fayl seçin | اختر ملفًا | فایلی انتخاب کنید | फ़ाइल चुनें | 选择文件 | ファイルを選択 | 파일 선택 | Pilih berkas | Chọn tệp | เลือกไฟล์
drop_or_click = Нажмите или перетащите файл сюда | Tap or drop a file here | Пахш кунед ё файлро ба ин ҷо кашед | Bosing yoki faylni shu yerga tashlang | Dokunun veya dosyayı buraya bırakın | Toca o suelta un archivo aquí | Tippen oder Datei hierher ziehen | Touchez ou déposez un fichier ici | Tocca o trascina qui un file | Toque ou solte um arquivo aqui | Dotknij lub upuść plik tutaj | Натисніть або перетягніть файл сюди | Басыңыз немесе файлды осында сүйреңіз | Басыңыз же файлды бул жерге сүйрөңүз | Toxunun və ya faylı bura atın | انقر أو أسقط ملفًا هنا | بزنید یا فایل را اینجا بکشید | टैप करें या फ़ाइल यहाँ छोड़ें | 点击或将文件拖到这里 | タップするかファイルをここにドロップ | 탭하거나 파일을 여기에 놓으세요 | Ketuk atau letakkan berkas di sini | Chạm hoặc thả tệp vào đây | แตะหรือลากไฟล์มาวางที่นี่
supported = Поддерживается | Supported | Дастгирӣ мешавад | Qo‘llab-quvvatlanadi | Desteklenen | Compatible | Unterstützt | Pris en charge | Supportati | Suportado | Obsługiwane | Підтримується | Қолдау көрсетіледі | Колдоого алынат | Dəstəklənir | مدعوم | پشتیبانی‌شده | समर्थित | 支持 | 対応形式 | 지원 형식 | Didukung | Hỗ trợ | รองรับ
max_size = до {size} | up to {size} | то {size} | {size} gacha | en fazla {size} | hasta {size} | bis {size} | jusqu’à {size} | fino a {size} | até {size} | do {size} | до {size} | {size} дейін | {size} чейин | {size}-a qədər | حتى {size} | تا {size} | {size} तक | 最多 {size} | 最大 {size} | 최대 {size} | hingga {size} | tối đa {size} | สูงสุด {size}
file_name = Имя файла | File name | Номи файл | Fayl nomi | Dosya adı | Nombre del archivo | Dateiname | Nom du fichier | Nome file | Nome do arquivo | Nazwa pliku | Назва файлу | Файл атауы | Файлдын аты | Fayl adı | اسم الملف | نام فایل | फ़ाइल का नाम | 文件名 | ファイル名 | 파일 이름 | Nama berkas | Tên tệp | ชื่อไฟล์
file_size = Размер | Size | Андоза | Hajmi | Boyut | Tamaño | Größe | Taille | Dimensione | Tamanho | Rozmiar | Розмір | Өлшемі | Өлчөмү | Ölçü | الحجم | حجم | आकार | 大小 | サイズ | 크기 | Ukuran | Kích thước | ขนาด
original = Было | Original | Аввал | Asl | Orijinal | Original | Original | Original | Originale | Original | Oryginał | Було | Бастапқы | Баштапкы | Orijinal | الأصلي | اصلی | मूल | 原始 | 元 | 원본 | Asli | Gốc | ต้นฉบับ
result = Результат | Result | Натиҷа | Natija | Sonuç | Resultado | Ergebnis | Résultat | Risultato | Resultado | Wynik | Результат | Нәтиже | Натыйжа | Nəticə | النتيجة | نتیجه | परिणाम | 结果 | 結果 | 결과 | Hasil | Kết quả | ผลลัพธ์
start = Начать | Start | Оғоз | Boshlash | Başlat | Empezar | Starten | Démarrer | Avvia | Iniciar | Start | Почати | Бастау | Баштоо | Başla | ابدأ | شروع | शुरू करें | 开始 | 開始 | 시작 | Mulai | Bắt đầu | เริ่ม
processing = Обработка… | Processing… | Коркард… | Ishlov berilmoqda… | İşleniyor… | Procesando… | Wird verarbeitet… | Traitement… | Elaborazione… | Processando… | Przetwarzanie… | Обробка… | Өңделуде… | Иштелүүдө… | Emal olunur… | جارٍ المعالجة… | در حال پردازش… | प्रोसेस हो रहा है… | 处理中… | 処理中… | 처리 중… | Memproses… | Đang xử lý… | กำลังประมวลผล…
uploading = Загрузка файла… {pct}% | Uploading… {pct}% | Боргузорӣ… {pct}% | Yuklanmoqda… {pct}% | Yükleniyor… %{pct} | Subiendo… {pct}% | Hochladen… {pct}% | Envoi… {pct}% | Caricamento… {pct}% | Enviando… {pct}% | Wysyłanie… {pct}% | Завантаження… {pct}% | Жүктелуде… {pct}% | Жүктөлүүдө… {pct}% | Yüklənir… {pct}% | جارٍ الرفع… {pct}% | در حال بارگذاری… {pct}% | अपलोड हो रहा है… {pct}% | 上传中… {pct}% | アップロード中… {pct}% | 업로드 중… {pct}% | Mengunggah… {pct}% | Đang tải lên… {pct}% | กำลังอัปโหลด… {pct}%
done = Готово | Done | Тайёр | Tayyor | Tamam | Listo | Fertig | Terminé | Fatto | Pronto | Gotowe | Готово | Дайын | Даяр | Hazırdır | تم | انجام شد | हो गया | 完成 | 完了 | 완료 | Selesai | Xong | เสร็จแล้ว
error = Ошибка | Error | Хато | Xato | Hata | Error | Fehler | Erreur | Errore | Erro | Błąd | Помилка | Қате | Ката | Xəta | خطأ | خطا | त्रुटि | 错误 | エラー | 오류 | Kesalahan | Lỗi | ข้อผิดพลาด
error_conn = Нет связи с ботом. Проверьте, что он запущен. | Can’t reach the bot. Make sure it is running. | Бо бот пайваст нашуд. Санҷед, ки он кор мекунад. | Bot bilan aloqa yo‘q. U ishlayotganini tekshiring. | Bota ulaşılamıyor. Çalıştığından emin olun. | No se puede conectar con el bot. Comprueba que esté en marcha. | Bot nicht erreichbar. Prüfe, ob er läuft. | Impossible de joindre le bot. Vérifiez qu’il est lancé. | Impossibile raggiungere il bot. Controlla che sia avviato. | Não foi possível falar com o bot. Verifique se ele está rodando. | Brak połączenia z botem. Sprawdź, czy działa. | Немає зв’язку з ботом. Перевірте, що він запущений. | Ботпен байланыс жоқ. Оның іске қосылғанын тексеріңіз. | Бот менен байланыш жок. Анын иштеп жатканын текшериңиз. | Botla əlaqə yoxdur. İşlədiyini yoxlayın. | تعذّر الوصول إلى البوت. تأكد من أنه يعمل. | به ربات دسترسی نیست. مطمئن شوید روشن است. | बॉट से संपर्क नहीं हो पा रहा। जाँचें कि वह चल रहा है। | 无法连接机器人。请确认它正在运行。 | ボットに接続できません。起動しているか確認してください。 | 봇에 연결할 수 없습니다. 실행 중인지 확인하세요. | Bot tidak dapat dihubungi. Pastikan bot berjalan. | Không kết nối được bot. Hãy kiểm tra bot đang chạy. | ติดต่อบอทไม่ได้ ตรวจสอบว่าบอททำงานอยู่
download = Скачать | Download | Боргирӣ | Yuklab olish | İndir | Descargar | Herunterladen | Télécharger | Scarica | Baixar | Pobierz | Завантажити | Жүктеп алу | Жүктөп алуу | Yüklə | تنزيل | دانلود | डाउनलोड | 下载 | ダウンロード | 다운로드 | Unduh | Tải xuống | ดาวน์โหลด
delete = Удалить | Delete | Нест кардан | O‘chirish | Sil | Eliminar | Löschen | Supprimer | Elimina | Excluir | Usuń | Видалити | Жою | Өчүрүү | Sil | حذف | حذف | हटाएँ | 删除 | 削除 | 삭제 | Hapus | Xóa | ลบ
deleted = Удалено | Deleted | Нест шуд | O‘chirildi | Silindi | Eliminado | Gelöscht | Supprimé | Eliminato | Excluído | Usunięto | Видалено | Жойылды | Өчүрүлдү | Silindi | تم الحذف | حذف شد | हटा दिया | 已删除 | 削除しました | 삭제됨 | Dihapus | Đã xóa | ลบแล้ว
clear = Очистить | Clear | Тоза кардан | Tozalash | Temizle | Limpiar | Leeren | Effacer | Pulisci | Limpar | Wyczyść | Очистити | Тазалау | Тазалоо | Təmizlə | مسح | پاک کردن | साफ़ करें | 清除 | クリア | 지우기 | Bersihkan | Xóa hết | ล้าง
copy = Копировать | Copy | Нусха бардоштан | Nusxalash | Kopyala | Copiar | Kopieren | Copier | Copia | Copiar | Kopiuj | Копіювати | Көшіру | Көчүрүү | Kopyala | نسخ | کپی | कॉपी करें | 复制 | コピー | 복사 | Salin | Sao chép | คัดลอก
copied = Скопировано | Copied | Нусха шуд | Nusxalandi | Kopyalandı | Copiado | Kopiert | Copié | Copiato | Copiado | Skopiowano | Скопійовано | Көшірілді | Көчүрүлдү | Kopyalandı | تم النسخ | کپی شد | कॉपी हो गया | 已复制 | コピーしました | 복사됨 | Disalin | Đã sao chép | คัดลอกแล้ว
add = Добавить | Add | Илова кардан | Qo‘shish | Ekle | Añadir | Hinzufügen | Ajouter | Aggiungi | Adicionar | Dodaj | Додати | Қосу | Кошуу | Əlavə et | إضافة | افزودن | जोड़ें | 添加 | 追加 | 추가 | Tambah | Thêm | เพิ่ม
save = Сохранить | Save | Захира кардан | Saqlash | Kaydet | Guardar | Speichern | Enregistrer | Salva | Salvar | Zapisz | Зберегти | Сақтау | Сактоо | Yadda saxla | حفظ | ذخیره | सहेजें | 保存 | 保存 | 저장 | Simpan | Lưu | บันทึก
refresh = Обновить | Refresh | Навсозӣ | Yangilash | Yenile | Actualizar | Aktualisieren | Actualiser | Aggiorna | Atualizar | Odśwież | Оновити | Жаңарту | Жаңыртуу | Yenilə | تحديث | به‌روزرسانی | रीफ़्रेश | 刷新 | 更新 | 새로고침 | Muat ulang | Làm mới | รีเฟรช
loading = Загрузка… | Loading… | Бор шуда истодааст… | Yuklanmoqda… | Yükleniyor… | Cargando… | Wird geladen… | Chargement… | Caricamento… | Carregando… | Ładowanie… | Завантаження… | Жүктелуде… | Жүктөлүүдө… | Yüklənir… | جارٍ التحميل… | در حال بارگذاری… | लोड हो रहा है… | 加载中… | 読み込み中… | 불러오는 중… | Memuat… | Đang tải… | กำลังโหลด…
empty = Пока пусто | Nothing here yet | Ҳоло холӣ аст | Hozircha bo‘sh | Henüz boş | Aún no hay nada | Noch leer | Rien pour l’instant | Ancora vuoto | Nada ainda | Na razie pusto | Поки порожньо | Әзірге бос | Азырынча бош | Hələ boşdur | لا شيء بعد | هنوز خالی است | अभी कुछ नहीं | 暂无内容 | まだありません | 아직 없음 | Belum ada | Chưa có gì | ยังไม่มีข้อมูล
settings = Настройки | Settings | Танзимот | Sozlamalar | Ayarlar | Ajustes | Einstellungen | Réglages | Impostazioni | Configurações | Ustawienia | Налаштування | Баптаулар | Жөндөөлөр | Ayarlar | الإعدادات | تنظیمات | सेटिंग्स | 设置 | 設定 | 설정 | Pengaturan | Cài đặt | การตั้งค่า
mode = Режим | Mode | Реҷа | Rejim | Mod | Modo | Modus | Mode | Modalità | Modo | Tryb | Режим | Режим | Режим | Rejim | الوضع | حالت | मोड | 模式 | モード | 모드 | Mode | Chế độ | โหมด
quality = Качество | Quality | Сифат | Sifat | Kalite | Calidad | Qualität | Qualité | Qualità | Qualidade | Jakość | Якість | Сапа | Сапат | Keyfiyyət | الجودة | کیفیت | गुणवत्ता | 质量 | 画質 | 품질 | Kualitas | Chất lượng | คุณภาพ
format = Формат | Format | Формат | Format | Biçim | Formato | Format | Format | Formato | Formato | Format | Формат | Пішім | Формат | Format | الصيغة | قالب | फ़ॉर्मैट | 格式 | 形式 | 형식 | Format | Định dạng | รูปแบบ
preview = Предпросмотр | Preview | Пешнамоиш | Oldindan ko‘rish | Önizleme | Vista previa | Vorschau | Aperçu | Anteprima | Pré-visualização | Podgląd | Попередній перегляд | Алдын ала қарау | Алдын ала көрүү | Önizləmə | معاينة | پیش‌نمایش | पूर्वावलोकन | 预览 | プレビュー | 미리보기 | Pratinjau | Xem trước | ตัวอย่าง
statistics = Статистика | Statistics | Омор | Statistika | İstatistikler | Estadísticas | Statistik | Statistiques | Statistiche | Estatísticas | Statystyki | Статистика | Статистика | Статистика | Statistika | الإحصاءات | آمار | आँकड़े | 统计 | 統計 | 통계 | Statistik | Thống kê | สถิติ
total = Всего | Total | Ҳамагӣ | Jami | Toplam | Total | Gesamt | Total | Totale | Total | Razem | Усього | Барлығы | Бардыгы | Cəmi | الإجمالي | مجموع | कुल | 总计 | 合計 | 합계 | Total | Tổng | ทั้งหมด
status = Статус | Status | Ҳолат | Holat | Durum | Estado | Status | Statut | Stato | Status | Status | Статус | Күйі | Абалы | Status | الحالة | وضعیت | स्थिति | 状态 | 状態 | 상태 | Status | Trạng thái | สถานะ
active = Активно | Active | Фаъол | Faol | Aktif | Activo | Aktiv | Actif | Attivo | Ativo | Aktywne | Активно | Белсенді | Активдүү | Aktiv | نشط | فعال | सक्रिय | 活跃 | 有効 | 활성 | Aktif | Đang hoạt động | ใช้งานอยู่
time = Время | Time | Вақт | Vaqt | Zaman | Hora | Zeit | Heure | Ora | Hora | Czas | Час | Уақыт | Убакыт | Vaxt | الوقت | زمان | समय | 时间 | 時間 | 시간 | Waktu | Thời gian | เวลา
action = Действие | Action | Амал | Amal | İşlem | Acción | Aktion | Action | Azione | Ação | Akcja | Дія | Әрекет | Аракет | Əməliyyat | الإجراء | اقدام | कार्रवाई | 操作 | 操作 | 작업 | Tindakan | Hành động | การกระทำ
reason = Причина | Reason | Сабаб | Sabab | Neden | Motivo | Grund | Raison | Motivo | Motivo | Powód | Причина | Себеп | Себеп | Səbəb | السبب | دلیل | कारण | 原因 | 理由 | 사유 | Alasan | Lý do | เหตุผล
user_id = ID пользователя | User ID | ID-и корбар | Foydalanuvchi ID | Kullanıcı ID | ID de usuario | Benutzer-ID | ID utilisateur | ID utente | ID do usuário | ID użytkownika | ID користувача | Пайдаланушы ID | Колдонуучу ID | İstifadəçi ID | معرّف المستخدم | شناسه کاربر | यूज़र ID | 用户 ID | ユーザー ID | 사용자 ID | ID pengguna | ID người dùng | ID ผู้ใช้
name = Название | Name | Ном | Nomi | Ad | Nombre | Name | Nom | Nome | Nome | Nazwa | Назва | Атауы | Аты | Ad | الاسم | نام | नाम | 名称 | 名前 | 이름 | Nama | Tên | ชื่อ
details = Подробности | Details | Тафсилот | Tafsilotlar | Ayrıntılar | Detalles | Details | Détails | Dettagli | Detalhes | Szczegóły | Подробиці | Толығырақ | Толук маалымат | Təfərrüatlar | التفاصيل | جزئیات | विवरण | 详情 | 詳細 | 세부 정보 | Detail | Chi tiết | รายละเอียด
success = Успешно | Success | Бомуваффақият | Muvaffaqiyatli | Başarılı | Correcto | Erfolgreich | Réussi | Riuscito | Sucesso | Sukces | Успішно | Сәтті | Ийгиликтүү | Uğurlu | نجاح | موفق | सफल | 成功 | 成功 | 성공 | Berhasil | Thành công | สำเร็จ
yes = Да | Yes | Ҳа | Ha | Evet | Sí | Ja | Oui | Sì | Sim | Tak | Так | Иә | Ооба | Bəli | نعم | بله | हाँ | 是 | はい | 예 | Ya | Có | ใช่
no = Нет | No | Не | Yo‘q | Hayır | No | Nein | Non | No | Não | Nie | Ні | Жоқ | Жок | Xeyr | لا | خیر | नहीं | 否 | いいえ | 아니요 | Tidak | Không | ไม่
history = История | History | Таърих | Tarix | Geçmiş | Historial | Verlauf | Historique | Cronologia | Histórico | Historia | Історія | Тарих | Тарых | Tarixçə | السجل | تاریخچه | इतिहास | 历史记录 | 履歴 | 기록 | Riwayat | Lịch sử | ประวัติ
files = Файлы | Files | Файлҳо | Fayllar | Dosyalar | Archivos | Dateien | Fichiers | File | Arquivos | Pliki | Файли | Файлдар | Файлдар | Fayllar | الملفات | فایل‌ها | फ़ाइलें | 文件 | ファイル | 파일 | Berkas | Tệp | ไฟล์
cancel = Отмена | Cancel | Бекор | Bekor qilish | İptal | Cancelar | Abbrechen | Annuler | Annulla | Cancelar | Anuluj | Скасувати | Болдырмау | Жокко чыгаруу | Ləğv et | إلغاء | لغو | रद्द करें | 取消 | キャンセル | 취소 | Batal | Hủy | ยกเลิก
generate = Создать | Generate | Сохтан | Yaratish | Oluştur | Generar | Erstellen | Générer | Genera | Gerar | Utwórz | Створити | Жасау | Түзүү | Yarat | إنشاء | ساختن | बनाएँ | 生成 | 生成 | 생성 | Buat | Tạo | สร้าง
run = Запустить | Run | Иҷро кардан | Ishga tushirish | Çalıştır | Ejecutar | Ausführen | Exécuter | Esegui | Executar | Uruchom | Запустити | Іске қосу | Иштетүү | İşə sal | تشغيل | اجرا | चलाएँ | 运行 | 実行 | 실행 | Jalankan | Chạy | เรียกใช้
password = Пароль | Password | Парол | Parol | Parola | Contraseña | Passwort | Mot de passe | Password | Senha | Hasło | Пароль | Құпиясөз | Сырсөз | Parol | كلمة المرور | رمز عبور | पासवर्ड | 密码 | パスワード | 비밀번호 | Kata sandi | Mật khẩu | รหัสผ่าน
waiting = Ожидание… | Waiting… | Интизорӣ… | Kutilmoqda… | Bekleniyor… | Esperando… | Warten… | En attente… | In attesa… | Aguardando… | Oczekiwanie… | Очікування… | Күту… | Күтүү… | Gözlənilir… | في الانتظار… | در انتظار… | प्रतीक्षा… | 等待中… | 待機中… | 대기 중… | Menunggu… | Đang chờ… | กำลังรอ…
auto = Авто | Auto | Худкор | Avto | Otomatik | Auto | Auto | Auto | Auto | Auto | Auto | Авто | Авто | Авто | Avto | تلقائي | خودکار | ऑटो | 自动 | 自動 | 자동 | Otomatis | Tự động | อัตโนมัติ
open_bot = Бот в Telegram работает отдельно: язык там меняется кнопкой 🌐 внутри бота. | The Telegram bot is separate: change its language with the 🌐 button inside the bot. | Боти Telegram алоҳида кор мекунад: забонро бо тугмаи 🌐 дар дохили бот иваз кунед. | Telegram bot alohida ishlaydi: tilni bot ichidagi 🌐 tugmasi bilan almashtiring. | Telegram botu ayrı çalışır: dilini bot içindeki 🌐 düğmesiyle değiştirin. | El bot de Telegram es independiente: cambia su idioma con el botón 🌐 dentro del bot. | Der Telegram-Bot ist getrennt: Seine Sprache änderst du mit der 🌐-Taste im Bot. | Le bot Telegram est séparé : changez sa langue avec le bouton 🌐 dans le bot. | Il bot Telegram è separato: cambia la sua lingua con il pulsante 🌐 nel bot. | O bot do Telegram é separado: mude o idioma com o botão 🌐 dentro do bot. | Bot w Telegramie działa osobno: język zmienisz przyciskiem 🌐 w bocie. | Бот у Telegram працює окремо: мову там змінює кнопка 🌐 у боті. | Telegram-бот бөлек жұмыс істейді: тілді боттағы 🌐 түймесімен ауыстырыңыз. | Telegram-бот өзүнчө иштейт: тилди боттогу 🌐 баскычы менен алмаштырыңыз. | Telegram botu ayrıca işləyir: dilini bot daxilindəki 🌐 düyməsi ilə dəyişin. | بوت تيليجرام منفصل: غيّر لغته بزر 🌐 داخل البوت. | ربات تلگرام جداست: زبان آن را با دکمه 🌐 داخل ربات عوض کنید. | Telegram बॉट अलग चलता है: उसकी भाषा बॉट के अंदर 🌐 बटन से बदलें। | Telegram 机器人是独立的：请在机器人内用 🌐 按钮更改其语言。 | Telegram ボットは別です。言語はボット内の 🌐 ボタンで変更します。 | 텔레그램 봇은 별도입니다. 봇 안의 🌐 버튼으로 언어를 바꾸세요. | Bot Telegram terpisah: ubah bahasanya dengan tombol 🌐 di dalam bot. | Bot Telegram hoạt động riêng: đổi ngôn ngữ bằng nút 🌐 trong bot. | บอท Telegram แยกกัน: เปลี่ยนภาษาด้วยปุ่ม 🌐 ในบอท
light = Светлая | Light | Равшан | Yorug‘ | Açık | Claro | Hell | Clair | Chiaro | Claro | Jasny | Світла | Ашық | Ачык | Açıq | فاتح | روشن | हल्का | 浅色 | ライト | 밝게 | Terang | Sáng | สว่าง
dark = Тёмная | Dark | Торик | Qorong‘i | Koyu | Oscuro | Dunkel | Sombre | Scuro | Escuro | Ciemny | Темна | Қараңғы | Караңгы | Tünd | داكن | تیره | गहरा | 深色 | ダーク | 어둡게 | Gelap | Tối | มืด
need_file = Сначала выберите файл. | Choose a file first. | Аввал файлро интихоб кунед. | Avval faylni tanlang. | Önce bir dosya seçin. | Primero elige un archivo. | Wähle zuerst eine Datei. | Choisissez d’abord un fichier. | Scegli prima un file. | Escolha um arquivo primeiro. | Najpierw wybierz plik. | Спочатку виберіть файл. | Алдымен файлды таңдаңыз. | Адегенде файлды тандаңыз. | Əvvəlcə fayl seçin. | اختر ملفًا أولًا. | ابتدا یک فایل انتخاب کنید. | पहले एक फ़ाइल चुनें। | 请先选择文件。 | まずファイルを選んでください。 | 먼저 파일을 선택하세요. | Pilih berkas terlebih dahulu. | Hãy chọn tệp trước. | เลือกไฟล์ก่อน
""")


# ---------------------------------------------------------------------------
# Язык
# ---------------------------------------------------------------------------
def _norm(code: str | None) -> str | None:
    if not code:
        return None
    c = normalize_lang_tag(code)
    return c if c in LANG_CODES else None


def resolve_lang(handler: Any) -> str:
    """?lang= → cookie pb_lang → язык приложения → en. Запоминает выбор в handler._pb_set_lang."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(getattr(handler, "path", "")).query).get("lang", [None])[0]
    lang = _norm(q)
    if lang:
        handler._pb_set_lang = lang
        return lang
    cookie = handler.headers.get("Cookie", "") if getattr(handler, "headers", None) else ""
    for part in cookie.split(";"):
        k, _, v = part.strip().partition("=")
        if k == "pb_lang" and _norm(v):
            return _norm(v)  # type: ignore[return-value]
    return _norm(os.environ.get("PYBIONIC_LANG") or os.environ.get("LANG")) or "en"


def tr(key: str, lang: str, **kw: Any) -> str:
    strings = (get_locales_dict() or {}).get("strings", {})
    entry = strings.get(key) or COMMON.get(key)
    val = key
    if isinstance(entry, dict):
        for code in _candidate_langs(lang):
            if entry.get(code):
                val = str(entry[code])
                break
        else:
            val = str(next(iter(entry.values()), key))
    elif isinstance(entry, str):
        val = entry
    if kw:
        try:
            val = val.format(**kw)
        except (KeyError, IndexError, ValueError):
            pass
    return val


def translator(lang: str) -> Callable[..., str]:
    return lambda key, **kw: tr(key, lang, **kw)


def js_dict(lang: str) -> dict[str, str]:
    """Все тексты страницы для JS: общий словарь + ключи w_* бота."""
    keys = list(COMMON) + [k for k in (get_locales_dict() or {}).get("strings", {}) if k.startswith("w_")]
    return {k: tr(k, lang) for k in keys}


# ---------------------------------------------------------------------------
# Компоненты (возвращают HTML-строки; тексты передавайте уже переведёнными)
# ---------------------------------------------------------------------------
def attrs(**kw: Any) -> str:
    out = []
    for k, v in kw.items():
        if v is None or v is False:
            continue
        name = k.rstrip("_").replace("_", "-")
        out.append(name if v is True else f'{name}="{esc(str(v), quote=True)}"')
    return (" " + " ".join(out)) if out else ""


# ---------------------------------------------------------------------------
# Иконки (линейные, 24×24, цвет = currentColor)
# ---------------------------------------------------------------------------
_ICONS = {
    "link": '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8"/><path d="M21 3v5h-5"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>',
    "film": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4M3 16h4M17 8h4M17 16h4M3 12h18"/>',
    "music": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "file": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "sparkles": '<path d="M12 3l1.8 4.7L18.5 9.5 13.8 11.3 12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "clipboard": '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
    "mic": '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M19 10a7 7 0 0 1-14 0M12 17v5"/>',
    "zap": '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "play": '<path d="M6 4l14 8-14 8z"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "unlock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.5-2"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "send": '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    "code": '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
    "wave": '<path d="M2 12h2l3-7 4 14 4-10 3 6h4"/>',
}


def icon(name: str, size: int = 18) -> str:
    path = _ICONS.get(name, _ICONS["sparkles"])
    return (f'<svg class="pb-ico" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')


# ---------------------------------------------------------------------------
# Компоненты (возвращают HTML-строки; тексты передавайте уже переведёнными)
# ---------------------------------------------------------------------------
def hero(title: str, subtitle: str, emoji: str, chips: Iterable[str] = (), art: str = "") -> str:
    """Заставка страницы: заголовок, описание, плашки возможностей и анимированная картинка."""
    chips_html = "".join(f'<span class="pb-chip">{esc(c)}</span>' for c in chips)
    pic = art or f"""<div class="pb-art" aria-hidden="true">
      <svg viewBox="0 0 200 200" class="pb-art-svg"><defs>
        <linearGradient id="pbg1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="var(--brand)"/><stop offset="1" stop-color="var(--brand2)"/></linearGradient>
        <radialGradient id="pbg2" cx=".3" cy=".3" r=".8"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>
        <circle class="pb-orbit" cx="100" cy="100" r="84" fill="none" stroke="url(#pbg1)" stroke-width="1.5" stroke-dasharray="4 10" opacity=".55"/>
        <circle class="pb-orbit r2" cx="100" cy="100" r="64" fill="none" stroke="url(#pbg1)" stroke-width="1" stroke-dasharray="2 8" opacity=".45"/>
        <rect x="52" y="52" width="96" height="96" rx="30" fill="url(#pbg1)" class="pb-art-core"/>
        <rect x="52" y="52" width="96" height="96" rx="30" fill="url(#pbg2)"/>
        <circle class="pb-dot d1" cx="100" cy="16" r="6" fill="var(--brand)"/>
        <circle class="pb-dot d2" cx="184" cy="100" r="4.5" fill="var(--brand2)"/>
        <circle class="pb-dot d3" cx="36" cy="150" r="5" fill="var(--brand)"/>
      </svg><span class="pb-art-emoji">{emoji}</span></div>"""
    return (f'<section class="pb-hero"><div class="pb-hero-text"><h2>{esc(title)}</h2>'
            f'<p>{esc(subtitle)}</p>{f"<div class=pb-chips>{chips_html}</div>" if chips_html else ""}</div>{pic}</section>')


def card(title: str, body: str, icon_name: str = "", aside: str = "", id: str | None = None, cls: str = "", icon: str = "") -> str:
    head = ""
    if title:
        ico = f'<span class="pb-card-ico">{globals()["icon"](icon_name)}</span>' if icon_name else (f'<span class="pb-card-emo">{icon}</span>' if icon else "")
        head = f'<div class="pb-card-head"><h3>{ico}{esc(title)}</h3>{aside}</div>'
    return f'<section class="pb-card {cls}"{attrs(id=id)}>{head}{body}</section>'


def grid(*cols: str, min_width: int = 300) -> str:
    return f'<div class="pb-grid" style="--min:{min_width}px">{"".join(cols)}</div>'


def field(label: str, control: str, hint: str = "", for_: str | None = None) -> str:
    h = f'<p class="pb-hint">{esc(hint)}</p>' if hint else ""
    return f'<div class="pb-field"><label{attrs(for_=for_)}>{esc(label)}</label>{control}{h}</div>'


def input_(id: str, placeholder: str = "", type: str = "text", value: str = "", icon_name: str = "", **kw: Any) -> str:
    inp = f'<input class="pb-input"{attrs(id=id, name=id, type=type, placeholder=placeholder or None, value=value or None, **kw)}>'
    if icon_name:
        return f'<div class="pb-input-wrap">{icon(icon_name)}{inp}</div>'
    return inp


def textarea(id: str, placeholder: str = "", rows: int = 5, value: str = "", **kw: Any) -> str:
    return f'<textarea class="pb-input"{attrs(id=id, name=id, rows=rows, placeholder=placeholder or None, **kw)}>{esc(value)}</textarea>'


def select(id: str, options: Iterable[tuple[str, str]], selected: str | None = None, **kw: Any) -> str:
    opts = "".join(f'<option value="{esc(v, quote=True)}"{" selected" if v == selected else ""}>{esc(lbl)}</option>' for v, lbl in options)
    return f'<div class="pb-select"><select class="pb-input"{attrs(id=id, name=id, **kw)}>{opts}</select></div>'


def button(label: str, id: str | None = None, kind: str = "primary", type: str = "button", icon_name: str = "", cls: str = "", **kw: Any) -> str:
    ico = icon(icon_name) if icon_name else ""
    return f'<button class="pb-btn pb-btn-{kind} {cls}"{attrs(id=id, type=type, **kw)}>{ico}<span>{esc(label)}</span></button>'


def link_button(label: str, href: str, kind: str = "primary", id: str | None = None, icon_name: str = "", cls: str = "", **kw: Any) -> str:
    ico = icon(icon_name) if icon_name else ""
    return f'<a class="pb-btn pb-btn-{kind} {cls}"{attrs(id=id, href=href, **kw)}>{ico}<span>{esc(label)}</span></a>'


def segmented(id: str, options: Iterable[tuple[str, str]], selected: str | None = None, sub: dict[str, str] | None = None,
              icons: dict[str, str] | None = None) -> str:
    """Плитки-переключатели (один вариант). Значение: document.getElementById(id).dataset.value"""
    items = []
    for v, lbl in options:
        s = f'<small>{esc(sub[v])}</small>' if sub and v in sub else ""
        ico = f'<span class="pb-seg-ico">{icon(icons[v], 20)}</span>' if icons and v in icons else ""
        if ico:
            lbl = _re.sub(r"^[^\w(]+", "", lbl).strip() or lbl  # эмодзи в тексте не дублирует иконку
        items.append(f'<button type="button" class="pb-seg-btn{" on" if v == selected else ""}" data-value="{esc(v, quote=True)}" '
                     f'aria-pressed="{"true" if v == selected else "false"}">{ico}<b>{esc(lbl)}</b>{s}</button>')
    return f'<div class="pb-seg" id="{esc(id)}" data-value="{esc(selected or "", quote=True)}" role="group">{"".join(items)}</div>'


def toggles(items: Iterable[tuple[str, str, bool]]) -> str:
    """Переключатели: [(id, подпись, включён)]"""
    return '<div class="pb-toggles">' + "".join(
        f'<label class="pb-toggle"><input type="checkbox"{attrs(id=i, name=i, checked=on)}><i></i><span>{esc(lbl)}</span></label>' for i, lbl, on in items
    ) + "</div>"


def range_(id: str, min: float, max: float, value: float, step: float = 1, unit: str = "") -> str:
    return (f'<div class="pb-range"><input type="range"{attrs(id=id, name=id, min=min, max=max, step=step, value=value)}>'
            f'<output for="{esc(id)}" data-unit="{esc(unit, quote=True)}">{esc(str(value))}{esc(unit)}</output></div>')


def dropzone(id: str, title: str, hint: str = "", accept: str = "", multiple: bool = False, icon_name: str = "upload") -> str:
    """Выбор файла. Выбранные файлы: pb.files('<id>'); событие pb:files на элементе #<id>-zone."""
    return (f'<label class="pb-drop" id="{esc(id)}-zone"><input type="file" hidden{attrs(id=id, name=id, accept=accept or None, multiple=multiple)}>'
            f'<span class="pb-drop-ico">{icon(icon_name, 26)}</span><strong data-default="{esc(title, quote=True)}">{esc(title)}</strong>'
            f'<span class="pb-hint">{esc(hint)}</span></label>')


def progress(id: str) -> str:
    return (f'<div class="pb-progress" id="{esc(id)}" hidden><div class="pb-progress-top"><p class="pb-hint"></p><b class="pb-pct"></b></div>'
            f'<div class="pb-bar"><i></i></div></div>')


def stats(items: Iterable[tuple[str, str] | tuple[str, str, str] | tuple[str, str, str, str]]) -> str:
    """[(подпись, значение, id?, иконка?)]"""
    out = []
    for it in items:
        lbl, val = it[0], it[1]
        sid = it[2] if len(it) > 2 else None
        ico = f'<span class="pb-stat-ico">{icon(it[3])}</span>' if len(it) > 3 and it[3] else ""
        out.append(f'<div class="pb-stat">{ico}<b data-count{attrs(id=sid)}>{esc(str(val))}</b><span>{esc(lbl)}</span></div>')
    return f'<div class="pb-stats">{"".join(out)}</div>'


def table(headers: list[str], rows: Iterable[Iterable[str]], empty: str = "", id: str | None = None, raw: bool = False) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    rows = list(rows)
    body = "".join("<tr>" + "".join(f"<td>{c if raw else esc(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    if not rows and empty:
        body = f'<tr class="pb-empty-row"><td colspan="{max(len(headers), 1)}">{esc(empty)}</td></tr>'
    return f'<div class="pb-table"><table{attrs(id=id)}><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def empty_state(text: str, icon_name: str = "folder", id: str | None = None) -> str:
    return f'<div class="pb-empty"{attrs(id=id)}><span class="pb-empty-ico">{icon(icon_name, 28)}</span><p>{esc(text)}</p></div>'


def note(text: str, kind: str = "info", icon_name: str = "") -> str:
    ico = icon(icon_name or ("alert" if kind == "warn" else "sparkles"), 16)
    return f'<p class="pb-note pb-note-{kind}">{ico}<span>{esc(text)}</span></p>'


def result_box(id: str) -> str:
    return f'<div class="pb-result" id="{esc(id)}" hidden></div>'


def human_bytes(n: float | int | None) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


# ---------------------------------------------------------------------------
# Страница
# ---------------------------------------------------------------------------
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&family=Unbounded:wght@500;700&display=swap">')

CSS = r"""
:root{--brand:#0a84ff;--brand2:color-mix(in oklab,var(--brand) 45%,#8b5cf6);
--bg:#f4f6fb;--bg2:#eef1f8;--surface:rgba(255,255,255,.78);--solid:#fff;--surface2:#f1f4f9;--fg:#0f1623;--muted:#5b6678;--line:rgba(15,22,35,.09);
--ok:#0f9d6b;--warn:#c27c0e;--bad:#e5484d;--accent-fg:#fff;
--sh1:0 1px 2px rgba(16,24,40,.05),0 8px 24px -8px rgba(16,24,40,.12);--sh2:0 2px 4px rgba(16,24,40,.06),0 18px 40px -12px rgba(16,24,40,.22);
--r:18px;--r2:12px;--ease:cubic-bezier(.2,.8,.2,1);
--font:"Onest",system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans",sans-serif;--disp:"Unbounded","Onest",system-ui,sans-serif;--mono:ui-monospace,"SF Mono","JetBrains Mono",Consolas,monospace}
:root[data-theme="dark"]{--bg:#070b12;--bg2:#0b111b;--surface:rgba(18,25,38,.72);--solid:#111827;--surface2:rgba(255,255,255,.04);--fg:#e8edf5;--muted:#8b97aa;--line:rgba(255,255,255,.08);
--sh1:0 1px 0 rgba(255,255,255,.04) inset,0 10px 30px -12px rgba(0,0,0,.6);--sh2:0 1px 0 rgba(255,255,255,.05) inset,0 24px 50px -16px rgba(0,0,0,.7);color-scheme:dark}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#070b12;--bg2:#0b111b;--surface:rgba(18,25,38,.72);--solid:#111827;--surface2:rgba(255,255,255,.04);--fg:#e8edf5;--muted:#8b97aa;--line:rgba(255,255,255,.08);
--sh1:0 1px 0 rgba(255,255,255,.04) inset,0 10px 30px -12px rgba(0,0,0,.6);--sh2:0 1px 0 rgba(255,255,255,.05) inset,0 24px 50px -16px rgba(0,0,0,.7);color-scheme:dark}}
*{box-sizing:border-box}[hidden]{display:none!important}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;min-height:100vh;background:var(--bg);color:var(--fg);font:15px/1.6 var(--font);letter-spacing:-.005em;overflow-x:hidden}
.pb-bgfx{position:fixed;inset:0;z-index:-1;overflow:hidden;pointer-events:none}
.pb-bgfx i{position:absolute;width:52vmax;height:52vmax;border-radius:50%;filter:blur(70px);opacity:.33;animation:pbdrift 26s var(--ease) infinite alternate}
.pb-bgfx i:nth-child(1){background:var(--brand);top:-22vmax;left:-14vmax}
.pb-bgfx i:nth-child(2){background:var(--brand2);bottom:-26vmax;right:-16vmax;animation-delay:-9s;animation-duration:32s}
.pb-bgfx i:nth-child(3){background:color-mix(in oklab,var(--brand) 40%,#22d3ee);top:30%;left:45%;width:30vmax;height:30vmax;opacity:.18;animation-duration:38s}
.pb-bgfx::after{content:"";position:absolute;inset:0;background-image:radial-gradient(color-mix(in srgb,var(--fg) 9%,transparent) 1px,transparent 1px);background-size:22px 22px;mask-image:linear-gradient(to bottom,#000,transparent 70%)}
@keyframes pbdrift{0%{transform:translate(0,0) scale(1)}100%{transform:translate(8vmax,6vmax) scale(1.15)}}
.pb-wrap{max-width:1080px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.pb-top{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 70%,transparent);backdrop-filter:saturate(1.6) blur(16px);-webkit-backdrop-filter:saturate(1.6) blur(16px);border-bottom:1px solid var(--line)}
.pb-top .pb-wrap{display:flex;align-items:center;gap:12px;padding-block:10px}
.pb-logo{width:40px;height:40px;flex:none;border-radius:12px;display:grid;place-items:center;font-size:20px;background:linear-gradient(135deg,var(--brand),var(--brand2));box-shadow:0 6px 18px -6px var(--brand)}
.pb-ttl{min-width:0;flex:1}.pb-ttl h1{margin:0;font:700 15.5px/1.2 var(--font);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pb-ttl p{margin:0;color:var(--muted);font-size:12px;display:flex;align-items:center;gap:6px}
.pb-live{width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 0 color-mix(in srgb,var(--ok) 60%,transparent);animation:pbpulse 2s infinite}
@keyframes pbpulse{70%{box-shadow:0 0 0 7px transparent}100%{box-shadow:0 0 0 0 transparent}}
.pb-tools{display:flex;align-items:center;gap:6px;flex:none}
.pb-langbox{position:relative;display:flex;align-items:center}
.pb-langbox .pb-ico{position:absolute;inset-inline-start:10px;color:var(--muted);pointer-events:none}
.pb-langbox select{appearance:none;-webkit-appearance:none;height:38px;padding:0 12px 0 32px;border:1px solid var(--line);background:var(--surface);color:var(--fg);border-radius:12px;font:500 13.5px var(--font);max-width:170px;cursor:pointer}
[dir="rtl"] .pb-langbox select{padding:0 32px 0 12px}
.pb-iconbtn{width:38px;height:38px;border-radius:12px;border:1px solid var(--line);background:var(--surface);color:var(--fg);display:grid;place-items:center;cursor:pointer;transition:transform .2s var(--ease)}
.pb-iconbtn:hover{transform:rotate(-12deg)}
.pb-main{display:grid;gap:18px;padding-block:20px 8px}
.pb-hero{position:relative;display:grid;grid-template-columns:1fr auto;align-items:center;gap:20px;padding:26px 28px;border-radius:24px;overflow:hidden;
background:linear-gradient(135deg,color-mix(in srgb,var(--brand) 16%,var(--solid)),color-mix(in srgb,var(--brand2) 12%,var(--solid)));border:1px solid var(--line);box-shadow:var(--sh1)}
.pb-hero::before{content:"";position:absolute;inset:0;background:radial-gradient(600px 200px at 10% 0%,color-mix(in srgb,var(--brand) 22%,transparent),transparent);pointer-events:none}
.pb-hero-text{position:relative;display:grid;gap:10px;min-width:0}
.pb-hero h2{margin:0;font:700 clamp(22px,4vw,32px)/1.15 var(--disp);letter-spacing:-.02em;text-wrap:balance}
.pb-hero p{margin:0;color:var(--muted);font-size:15px;max-width:58ch}
.pb-chips{display:flex;flex-wrap:wrap;gap:6px}
.pb-chip{padding:4px 10px;border-radius:99px;font-size:12.5px;font-weight:600;background:color-mix(in srgb,var(--solid) 70%,transparent);border:1px solid var(--line);backdrop-filter:blur(6px)}
.pb-art{position:relative;width:150px;height:150px;flex:none}
.pb-art-svg{width:100%;height:100%;overflow:visible}
.pb-art-emoji{position:absolute;inset:0;display:grid;place-items:center;font-size:46px;filter:drop-shadow(0 6px 12px rgba(0,0,0,.25));animation:pbfloat 5s var(--ease) infinite}
.pb-art-core{animation:pbcore 6s var(--ease) infinite;transform-origin:100px 100px}
.pb-orbit{transform-origin:100px 100px;animation:pbspin 28s linear infinite}.pb-orbit.r2{animation-duration:18s;animation-direction:reverse}
.pb-dot{transform-origin:100px 100px;animation:pbspin 14s linear infinite}.pb-dot.d2{animation-duration:20s;animation-direction:reverse}.pb-dot.d3{animation-duration:24s}
@keyframes pbspin{to{transform:rotate(360deg)}}@keyframes pbfloat{50%{transform:translateY(-7px)}}@keyframes pbcore{50%{transform:rotate(8deg) scale(1.04)}}
.pb-grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(min(var(--min,300px),100%),1fr));align-items:start}
.pb-card{position:relative;background:var(--surface);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid var(--line);border-radius:var(--r);padding:20px;box-shadow:var(--sh1);display:grid;gap:16px;min-width:0;
animation:pbup .6s var(--ease) both;transition:box-shadow .3s var(--ease),transform .3s var(--ease)}
.pb-card:hover{box-shadow:var(--sh2)}
.pb-main>*:nth-child(2){animation-delay:.06s}.pb-main>*:nth-child(3){animation-delay:.12s}.pb-grid>.pb-card:nth-child(2){animation-delay:.1s}.pb-grid>.pb-card:nth-child(3){animation-delay:.16s}.pb-grid>.pb-card:nth-child(4){animation-delay:.22s}
@keyframes pbup{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.pb-card-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.pb-card h3{margin:0;display:flex;align-items:center;gap:10px;font:650 16px/1.3 var(--font)}
.pb-card-ico{width:32px;height:32px;border-radius:10px;display:grid;place-items:center;color:var(--brand);background:color-mix(in srgb,var(--brand) 14%,transparent);flex:none}
.pb-card-emo{font-size:20px}
.pb-field{display:grid;gap:7px}.pb-field>label{font-size:13px;font-weight:600;color:var(--muted)}
.pb-input{width:100%;min-height:46px;padding:11px 14px;border:1px solid var(--line);border-radius:var(--r2);background:var(--surface2);color:var(--fg);font:inherit;transition:border-color .2s,box-shadow .2s,background .2s}
.pb-input:hover{border-color:color-mix(in srgb,var(--brand) 35%,var(--line))}
.pb-input:focus{outline:none;border-color:var(--brand);box-shadow:0 0 0 4px color-mix(in srgb,var(--brand) 20%,transparent);background:var(--solid)}
.pb-input-wrap{position:relative;display:flex;align-items:center;flex:999 1 220px}.pb-input-wrap .pb-ico{position:absolute;inset-inline-start:14px;color:var(--muted)}
.pb-input-wrap .pb-input{padding-inline-start:42px}
.pb-select{position:relative}.pb-select::after{content:"";position:absolute;inset-inline-end:14px;top:50%;width:8px;height:8px;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);transform:translateY(-70%) rotate(45deg);pointer-events:none}
.pb-select select{appearance:none;-webkit-appearance:none;padding-inline-end:36px;cursor:pointer}
textarea.pb-input{resize:vertical;font-family:var(--mono);font-size:13.5px;line-height:1.5}
.pb-hint{margin:0;color:var(--muted);font-size:12.5px}
.pb-btn{position:relative;overflow:hidden;display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:46px;padding:11px 18px;border-radius:var(--r2);border:1px solid transparent;font:650 15px var(--font);cursor:pointer;text-decoration:none;transition:transform .15s var(--ease),box-shadow .25s var(--ease),filter .2s,background .2s;-webkit-tap-highlight-color:transparent}
.pb-btn:active{transform:scale(.98)}.pb-btn[disabled]{opacity:.55;cursor:not-allowed;transform:none}
.pb-btn-primary{background:linear-gradient(135deg,var(--brand),var(--brand2));color:var(--accent-fg);box-shadow:0 8px 22px -10px var(--brand)}
.pb-btn-primary:hover:not([disabled]){box-shadow:0 12px 28px -10px var(--brand);filter:brightness(1.06)}
.pb-btn-primary::after{content:"";position:absolute;inset:0;background:linear-gradient(110deg,transparent 30%,rgba(255,255,255,.35) 50%,transparent 70%);transform:translateX(-120%);transition:transform .7s var(--ease)}
.pb-btn-primary:hover::after{transform:translateX(120%)}
.pb-btn-ghost{background:var(--surface2);color:var(--fg);border-color:var(--line)}.pb-btn-ghost:hover{border-color:color-mix(in srgb,var(--brand) 40%,var(--line));color:var(--brand)}
.pb-btn-danger{background:transparent;color:var(--bad);border-color:color-mix(in srgb,var(--bad) 35%,transparent)}.pb-btn-danger:hover{background:color-mix(in srgb,var(--bad) 10%,transparent)}
.pb-btn-sm{min-height:36px;padding:7px 12px;font-size:13.5px;border-radius:10px}
.pb-btn.busy span{opacity:.75}.pb-btn.busy::before{content:"";width:16px;height:16px;border-radius:50%;border:2px solid currentColor;border-right-color:transparent;animation:pbspin .7s linear infinite}
.pb-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}.pb-row>.pb-btn{flex:1 1 140px}.pb-row>.pb-input{flex:999 1 220px;width:auto}.pb-row>.pb-input+.pb-btn,.pb-row>.pb-input-wrap+.pb-btn{flex:0 0 auto}
.pb-seg{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}
.pb-seg-btn{position:relative;display:grid;gap:3px;justify-items:center;padding:14px 10px;border-radius:14px;border:1px solid var(--line);background:var(--surface2);color:var(--fg);font:inherit;cursor:pointer;text-align:center;transition:transform .2s var(--ease),border-color .2s,background .2s,box-shadow .2s}
.pb-seg-btn:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--brand) 40%,var(--line))}
.pb-seg-btn b{font-weight:650}.pb-seg-btn small{color:var(--muted);font-size:12px}
.pb-seg-ico{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;color:var(--muted);background:var(--surface2);transition:all .25s var(--ease)}
.pb-seg-btn.on{border-color:var(--brand);background:color-mix(in srgb,var(--brand) 10%,var(--solid));box-shadow:0 0 0 3px color-mix(in srgb,var(--brand) 18%,transparent)}
.pb-seg-btn.on .pb-seg-ico{color:#fff;background:linear-gradient(135deg,var(--brand),var(--brand2))}
.pb-seg-btn.on::after{content:"✓";position:absolute;top:8px;inset-inline-end:10px;width:18px;height:18px;border-radius:50%;display:grid;place-items:center;font-size:11px;color:#fff;background:var(--brand);animation:pbpop .3s var(--ease)}
@keyframes pbpop{from{transform:scale(0)}to{transform:scale(1)}}
.pb-toggles{display:flex;flex-wrap:wrap;gap:8px}
.pb-toggle{display:inline-flex;align-items:center;gap:10px;padding:8px 14px 8px 8px;border-radius:99px;border:1px solid var(--line);background:var(--surface2);cursor:pointer;font-size:14px;user-select:none;transition:border-color .2s}
.pb-toggle input{position:absolute;opacity:0;pointer-events:none}
.pb-toggle i{position:relative;width:34px;height:20px;border-radius:99px;background:color-mix(in srgb,var(--muted) 35%,transparent);transition:background .25s}
.pb-toggle i::after{content:"";position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.3);transition:transform .25s var(--ease)}
.pb-toggle input:checked+i{background:var(--brand)}.pb-toggle input:checked+i::after{transform:translateX(14px)}
.pb-toggle:has(input:checked){border-color:color-mix(in srgb,var(--brand) 45%,var(--line))}
.pb-toggle input:focus-visible+i{outline:2px solid var(--brand);outline-offset:2px}
.pb-range{display:flex;align-items:center;gap:14px}
.pb-range input{flex:1;appearance:none;-webkit-appearance:none;height:6px;border-radius:99px;background:linear-gradient(90deg,var(--brand) var(--p,50%),color-mix(in srgb,var(--muted) 25%,transparent) var(--p,50%));outline:none}
.pb-range input::-webkit-slider-thumb{-webkit-appearance:none;width:22px;height:22px;border-radius:50%;background:#fff;border:3px solid var(--brand);box-shadow:0 2px 6px rgba(0,0,0,.25);cursor:grab;transition:transform .15s}
.pb-range input::-webkit-slider-thumb:active{transform:scale(1.15)}
.pb-range input::-moz-range-thumb{width:18px;height:18px;border-radius:50%;background:#fff;border:3px solid var(--brand)}
.pb-range output{min-width:70px;text-align:center;font-weight:700;font-variant-numeric:tabular-nums;padding:4px 10px;border-radius:9px;background:var(--surface2);border:1px solid var(--line)}
.pb-drop{position:relative;display:grid;justify-items:center;gap:8px;text-align:center;padding:30px 18px;border-radius:var(--r);cursor:pointer;
background:radial-gradient(120% 90% at 50% 0%,color-mix(in srgb,var(--brand) 9%,transparent),transparent 70%),var(--surface2);border:2px dashed color-mix(in srgb,var(--brand) 35%,var(--line));transition:background .25s,border-color .25s,transform .25s var(--ease)}
.pb-drop:hover{border-color:var(--brand);background:color-mix(in srgb,var(--brand) 6%,var(--surface2))}
.pb-drop.over{border-color:var(--brand);transform:scale(1.015);background:color-mix(in srgb,var(--brand) 10%,var(--surface2))}
.pb-drop.over .pb-drop-ico{animation:pbbounce .6s var(--ease) infinite alternate}
.pb-drop.has{border-style:solid;border-color:var(--ok)}.pb-drop.has .pb-drop-ico{background:var(--ok)}
.pb-drop-ico{width:56px;height:56px;border-radius:18px;display:grid;place-items:center;color:#fff;background:linear-gradient(135deg,var(--brand),var(--brand2));box-shadow:0 10px 24px -10px var(--brand);transition:background .3s}
@keyframes pbbounce{to{transform:translateY(-6px)}}
.pb-drop strong{font-weight:650;overflow-wrap:anywhere}
.pb-progress{display:grid;gap:8px;animation:pbup .3s var(--ease)}
.pb-progress-top{display:flex;justify-content:space-between;align-items:baseline;gap:10px}.pb-pct{font-variant-numeric:tabular-nums;font-size:13px}
.pb-bar{height:10px;border-radius:99px;background:color-mix(in srgb,var(--muted) 18%,transparent);overflow:hidden}
.pb-bar i{display:block;height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,var(--brand),var(--brand2));background-size:200% 100%;transition:width .4s var(--ease);position:relative;overflow:hidden}
.pb-bar i::after{content:"";position:absolute;inset:0;background:repeating-linear-gradient(-45deg,rgba(255,255,255,.22) 0 8px,transparent 8px 16px);animation:pbstripe 1s linear infinite}
@keyframes pbstripe{to{background-position:22px 0}}
.pb-progress.indet .pb-bar i{width:40%!important;animation:pbslide 1.3s var(--ease) infinite}
@keyframes pbslide{0%{transform:translateX(-110%)}100%{transform:translateX(260%)}}
.pb-progress.ok .pb-bar i{background:var(--ok)}.pb-progress.ok .pb-bar i::after{display:none}
.pb-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
.pb-stat{position:relative;padding:14px 16px;border-radius:14px;background:var(--surface2);border:1px solid var(--line);display:grid;gap:2px;overflow:hidden}
.pb-stat::after{content:"";position:absolute;inset-inline-end:-30px;top:-30px;width:80px;height:80px;border-radius:50%;background:radial-gradient(color-mix(in srgb,var(--brand) 25%,transparent),transparent 70%)}
.pb-stat-ico{color:var(--brand);margin-bottom:4px}
.pb-stat b{font:700 24px/1.15 var(--disp);font-variant-numeric:tabular-nums;overflow-wrap:anywhere;letter-spacing:-.02em}.pb-stat span{color:var(--muted);font-size:12.5px}
.pb-table{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--surface2)}
.pb-table table{width:100%;border-collapse:collapse;font-size:13.5px}
.pb-table th,.pb-table td{text-align:start;padding:10px 14px;border-bottom:1px solid var(--line);vertical-align:top}
.pb-table th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
.pb-table tbody tr{transition:background .2s}.pb-table tbody tr:hover{background:color-mix(in srgb,var(--brand) 6%,transparent)}
.pb-table tr:last-child td{border-bottom:0}.pb-empty-row td{color:var(--muted);text-align:center;padding:22px}
.pb-empty{display:grid;justify-items:center;gap:8px;padding:26px 12px;color:var(--muted);text-align:center}
.pb-empty-ico{width:60px;height:60px;border-radius:20px;display:grid;place-items:center;color:var(--brand);background:color-mix(in srgb,var(--brand) 12%,transparent);animation:pbfloat 4s var(--ease) infinite}
.pb-empty p{margin:0;max-width:34ch}
.pb-note{margin:0;display:flex;gap:10px;align-items:flex-start;padding:11px 14px;border-radius:var(--r2);font-size:13px;background:var(--surface2);color:var(--muted);border:1px solid var(--line)}
.pb-note .pb-ico{flex:none;margin-top:2px;color:var(--brand)}
.pb-note-warn{background:color-mix(in srgb,var(--warn) 10%,var(--solid));color:var(--fg)}.pb-note-warn .pb-ico{color:var(--warn)}
.pb-result{padding:16px;border-radius:14px;border:1px solid color-mix(in srgb,var(--ok) 40%,transparent);background:color-mix(in srgb,var(--ok) 8%,var(--solid));display:grid;gap:12px;animation:pbup .4s var(--ease)}
.pb-result.err{border-color:color-mix(in srgb,var(--bad) 40%,transparent);background:color-mix(in srgb,var(--bad) 8%,var(--solid))}
.pb-list{display:grid;gap:12px}
.pb-item{display:grid;gap:10px;padding:14px;border:1px solid var(--line);border-radius:14px;background:var(--surface2);animation:pbup .45s var(--ease) both;transition:border-color .2s,transform .2s var(--ease)}
.pb-item:hover{border-color:color-mix(in srgb,var(--brand) 35%,var(--line))}
.pb-item-top{display:flex;gap:12px;align-items:center}
.pb-item-ico{width:42px;height:42px;border-radius:12px;flex:none;display:grid;place-items:center;color:#fff;background:linear-gradient(135deg,var(--brand),var(--brand2))}
.pb-item-top b{overflow-wrap:anywhere;font-weight:650;line-height:1.35}
.pb-meta{display:flex;flex-wrap:wrap;gap:8px;color:var(--muted);font-size:12.5px;align-items:center;margin-top:2px}
.pb-tag{display:inline-block;padding:1px 8px;border-radius:7px;background:color-mix(in srgb,var(--brand) 15%,transparent);color:var(--brand);font-weight:700;font-size:11px;letter-spacing:.03em}
.pb-item video,.pb-item audio,.pb-item img{width:100%;border-radius:12px;max-height:320px;background:#000}
.pb-item audio{background:transparent}
.pb-skel{height:72px;border-radius:14px;background:linear-gradient(90deg,var(--surface2),color-mix(in srgb,var(--muted) 14%,transparent),var(--surface2));background-size:300% 100%;animation:pbskel 1.4s ease infinite}
@keyframes pbskel{to{background-position:-150% 0}}
.pb-mono{font-family:var(--mono);font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere}
.pb-console{background:#0a0f17;color:#d6e4f0;border-radius:14px;padding:14px;min-height:130px;max-height:400px;overflow:auto;border:1px solid rgba(255,255,255,.06)}
.pb-foot{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;padding-block:22px 34px;color:var(--muted);font-size:12.5px}
.pb-foot span{display:flex;align-items:center;gap:6px}
.pb-toast{position:fixed;left:50%;bottom:calc(20px + env(safe-area-inset-bottom,0px));z-index:30;display:flex;align-items:center;gap:10px;max-width:min(92vw,520px);padding:12px 16px;border-radius:14px;
background:color-mix(in srgb,var(--solid) 92%,transparent);backdrop-filter:blur(12px);color:var(--fg);border:1px solid var(--line);font-size:14px;box-shadow:var(--sh2);opacity:0;transform:translate(-50%,16px) scale(.98);pointer-events:none;transition:opacity .3s var(--ease),transform .3s var(--ease)}
.pb-toast.show{opacity:1;transform:translate(-50%,0) scale(1)}.pb-toast .pb-ico{flex:none;color:var(--ok)}.pb-toast.err .pb-ico{color:var(--bad)}.pb-toast.err{border-color:color-mix(in srgb,var(--bad) 40%,var(--line))}
:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
@media (max-width:640px){.pb-hero{grid-template-columns:1fr;padding:20px}.pb-art{width:110px;height:110px;position:absolute;inset-inline-end:-6px;top:-6px;opacity:.9}.pb-art-emoji{font-size:34px}.pb-hero-text{padding-inline-end:84px}}
@media (max-width:520px){.pb-ttl p{display:none}.pb-langbox select{max-width:116px}.pb-card{padding:16px}.pb-main{gap:14px}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
"""

JS = r"""
(function(){
const root=document.documentElement;
try{const th=localStorage.getItem('pb_theme');if(th)root.dataset.theme=th;}catch(e){}
const ICO={check:'<path d="M20 6 9 17l-5-5"/>',alert:'<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>'};
const svg=n=>'<svg class="pb-ico" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+ICO[n]+'</svg>';
window.pb={
 t(k,v){let s=(window.PB_T||{})[k]||k;if(v)for(const n in v)s=s.split('{'+n+'}').join(v[n]);return s;},
 bytes(n){n=+n||0;const u=['B','KB','MB','GB'];let i=0;while(n>=1024&&i<3){n/=1024;i++}return (i?n.toFixed(1):n)+' '+u[i]},
 toast(msg,err){const el=document.getElementById('pb-toast');el.innerHTML=svg(err?'alert':'check')+'<span></span>';el.lastChild.textContent=msg;
  el.className='pb-toast show'+(err?' err':'');clearTimeout(el._t);el._t=setTimeout(()=>el.className='pb-toast'+(err?' err':''),err?6000:2800)},
 progress(id,pct,text){const el=document.getElementById(id);if(!el)return;el.hidden=false;el.classList.toggle('indet',pct==null);el.classList.toggle('ok',pct===100);
  el.querySelector('.pb-bar i').style.width=(pct==null?'':Math.max(0,Math.min(100,pct))+'%');el.querySelector('.pb-hint').textContent=text||'';
  el.querySelector('.pb-pct').textContent=pct==null?'':Math.round(pct)+'%'},
 hide(id){const el=document.getElementById(id);if(el)el.hidden=true},
 busy(btn,on){if(!btn)return;btn.disabled=!!on;btn.classList.toggle('busy',!!on)},
 files(id){const el=document.getElementById(id);return el&&el.files?Array.from(el.files):[]},
 async json(url,opt){let r;try{r=await fetch(url,opt)}catch(e){throw new Error(pb.t('error_conn'))}
  const tx=await r.text();let d;try{d=JSON.parse(tx)}catch(e){d={ok:r.ok,error:tx.slice(0,300)}}
  if(!r.ok&&!d.error)d.error='HTTP '+r.status;return d},
 post(url,data){const isForm=data instanceof FormData;return pb.json(url,{method:'POST',body:isForm?data:new URLSearchParams(data||{})})},
 postJSON(url,obj){return pb.json(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj||{})})},
 upload(url,form,onPct){return new Promise((res,rej)=>{const x=new XMLHttpRequest();x.open('POST',url);
  x.upload.onprogress=e=>{if(e.lengthComputable&&onPct)onPct(Math.round(e.loaded*100/e.total))};
  x.onload=()=>{let d;try{d=JSON.parse(x.responseText)}catch(e){d={ok:x.status<300,raw:x.responseText,error:x.status>=300?x.responseText.slice(0,300):''}}
   if(x.status>=300&&!d.error)d.error='HTTP '+x.status;res(d)};x.onerror=()=>rej(new Error(pb.t('error_conn')));x.send(form)})},
 copy(text){const done=()=>pb.toast(pb.t('copied'));try{navigator.clipboard.writeText(text).then(done,()=>fb())}catch(e){fb()}
  function fb(){const t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();try{document.execCommand('copy');done()}catch(e){}t.remove()}},
 esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))},
 count(el,to){to=+to;if(!isFinite(to)||matchMedia('(prefers-reduced-motion: reduce)').matches){el.textContent=to;return}
  const from=+(el.dataset.v||0),t0=performance.now(),d=700;el.dataset.v=to;
  (function step(t){const k=Math.min(1,(t-t0)/d),e=1-Math.pow(1-k,3);el.textContent=Math.round(from+(to-from)*e).toLocaleString(window.PB_LANG);if(k<1)requestAnimationFrame(step)})(t0)}
};
document.addEventListener('click',e=>{const b=e.target.closest('.pb-seg-btn');if(!b)return;const g=b.parentElement;
 g.querySelectorAll('.pb-seg-btn').forEach(x=>{x.classList.toggle('on',x===b);x.setAttribute('aria-pressed',x===b)});g.dataset.value=b.dataset.value;g.dispatchEvent(new CustomEvent('change',{bubbles:true}))});
document.querySelectorAll('.pb-range input').forEach(r=>{const o=r.parentElement.querySelector('output');
 const f=()=>{o.textContent=r.value+(o.dataset.unit||'');r.style.setProperty('--p',((r.value-r.min)*100/(r.max-r.min))+'%')};r.addEventListener('input',f);f()});
document.querySelectorAll('.pb-drop').forEach(z=>{const inp=z.querySelector('input[type=file]');const lbl=z.querySelector('strong');
 const show=()=>{const fs=Array.from(inp.files||[]);z.classList.toggle('has',fs.length>0);
  lbl.textContent=fs.length?(fs.length==1?fs[0].name+' · '+pb.bytes(fs[0].size):fs.length+' × '+pb.t('files')):lbl.dataset.default;
  z.dispatchEvent(new CustomEvent('pb:files',{detail:fs,bubbles:true}))};
 inp.addEventListener('change',show);
 ['dragenter','dragover'].forEach(ev=>z.addEventListener(ev,e=>{e.preventDefault();z.classList.add('over')}));
 ['dragleave','drop'].forEach(ev=>z.addEventListener(ev,e=>{e.preventDefault();z.classList.remove('over')}));
 z.addEventListener('drop',e=>{if(e.dataTransfer&&e.dataTransfer.files.length){inp.files=e.dataTransfer.files;show()}})});
document.querySelectorAll('[data-count]').forEach(el=>{const v=el.textContent.trim();if(/^\d+$/.test(v)){el.textContent='0';pb.count(el,v)}});
const ls=document.getElementById('pb-lang');if(ls)ls.addEventListener('change',()=>{document.cookie='pb_lang='+ls.value+';path=/;max-age=31536000;samesite=lax';
 const u=new URL(location.href);u.searchParams.set('lang',ls.value);document.body.style.transition='opacity .2s';document.body.style.opacity='.4';location.href=u.toString()});
const tb=document.getElementById('pb-theme');if(tb){const cur=()=>root.dataset.theme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
 const paint=()=>{tb.innerHTML=cur()==='dark'?tb.dataset.sun:tb.dataset.moon;tb.title=pb.t(cur()==='dark'?'light':'dark')};paint();
 tb.addEventListener('click',()=>{root.dataset.theme=cur()==='dark'?'light':'dark';try{localStorage.setItem('pb_theme',root.dataset.theme)}catch(e){}paint()})}
})();
"""


def render_page(lang: str, *, title: str, subtitle: str = "", emoji: str = "⚡", body: str = "", script: str = "",
                brand: str = "#0a84ff", port: int | str | None = None, hero_html: str = "") -> str:
    """Полная HTML-страница: шапка (название, язык, тема), заставка, содержимое, подвал."""
    options = "".join(
        f'<option value="{c}"{" selected" if c == lang else ""}>{esc(lbl)}</option>' for c, lbl in SUPPORTED_LANGUAGES
    )
    status = f'<span class="pb-live"></span>{esc(tr("online", lang))}{(" · " + esc(tr("port", lang)) + " " + esc(str(port))) if port else ""}'
    d = ' dir="rtl"' if lang in RTL else ""
    sun, moon = icon("sun"), icon("moon")
    return f"""<!doctype html>
<html lang="{esc(lang)}"{d}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="{esc(brand)}">
<title>{esc(title)}</title>
{FONTS}
<style>{CSS}:root{{--brand:{esc(brand)}}}</style>
</head>
<body>
<div class="pb-bgfx" aria-hidden="true"><i></i><i></i><i></i></div>
<header class="pb-top"><div class="pb-wrap">
  <div class="pb-logo" aria-hidden="true">{emoji}</div>
  <div class="pb-ttl"><h1>{esc(title)}</h1><p>{status}</p></div>
  <div class="pb-tools">
    <label class="pb-langbox">{icon("globe", 16)}<select id="pb-lang" aria-label="{esc(tr('language', lang), quote=True)}">{options}</select></label>
    <button class="pb-iconbtn" id="pb-theme" type="button" aria-label="{esc(tr('theme', lang), quote=True)}" data-sun="{esc(sun, quote=True)}" data-moon="{esc(moon, quote=True)}">{moon}</button>
  </div>
</div></header>
<main class="pb-wrap">
<div class="pb-main">
{hero_html}
{body}
</div>
<footer class="pb-foot"><span>{icon("globe", 14)}{esc(tr("open_bot", lang))}</span><span>{icon("zap", 14)}PyBionic</span></footer>
</main>
<div class="pb-toast" id="pb-toast" role="status" aria-live="polite"></div>
<script>window.PB_T={json.dumps(js_dict(lang), ensure_ascii=False).replace("</", "<\\/")};window.PB_LANG={json.dumps(lang)};</script>
<script>{JS}</script>
<script>{script}</script>
</body>
</html>"""


def send_html(handler: Any, html_text: str, status: int = 200) -> None:
    raw = html_text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    lang = getattr(handler, "_pb_set_lang", None)
    if lang:
        handler.send_header("Set-Cookie", f"pb_lang={lang}; Path=/; Max-Age=31536000; SameSite=Lax")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def send_page(handler: Any, lang: str, **kw: Any) -> None:
    send_html(handler, render_page(lang, **kw))


def send_json(handler: Any, data: Any, status: int = 200) -> None:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)
