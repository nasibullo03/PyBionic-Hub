# PyBionic — Release Notes & Руководство пользователя

**PyBionic** — автономный сервер для запуска Python-ботов и фоновых скриптов 24/7 прямо на Android-смартфоне без Root-прав.

---

## 🛡️ Что нового в версии 2.1.33 (SemVer Patch Release — Network Security Config, KeyStore UUID Aliases, Auto-Backup Vault Exclusion, Pyc Integrity, SSE Log Streaming & IPv6 Dual-Stack)

- **Ограничение открытого Cleartext HTTP трафика (Cleartext Traffic Restriction — #286)**:
  - В `res/xml/network_security_config.xml` переопределена системная политика сетевой безопасности: открытый незашифрованный HTTP-трафик строго ограничен локальными адресами `localhost` и `127.0.0.1`, а публичный трафик во внешнюю сеть принудительно требует TLS-шифрования. В настройки добавлен переключатель `cleartextTrafficRestrictionEnabled`.
- **Привязка ключей шифрования к неизменяемым UUID (KeyStore Project UUID Alias Guard — #287)**:
  - В архитектуре `SecretVault` алиасы ключей шифрования Android KeyStore изолированы от изменяемых строковых имен проектов и привязаны к стабильным идентификаторам, что предотвращает потерю доступа к секретам при переименовании проектов пользователем. В настройки добавлен переключатель `keystoreProjectUuidAliasEnabled`.
- **Исключение хранилища секретов из облачного Auto Backup (Secret Vault Backup Exclusion — #288)**:
  - В `res/xml/backup_rules.xml` и `res/xml/data_extraction_rules.xml` добавлены обязательные правила исключения: каталоги `secrets/`, `config/secrets` и файлы SharedPreferences исключены из облачного резервного копирования Google Drive (Auto Backup / Device Transfer), исключая компрометацию учетных данных. В настройки добавлен переключатель `secretVaultBackupExclusionEnabled`.
- **Приватная изоляция файлов логов (Log Storage Private Isolation — #291)**:
  - Регламентировано размещение рабочих логов выполнения ботов строго во внутреннем изолированном хранилище приложения, а доступ сторонних утилит ограничен безопасным `FileProvider` с временными грантами чтения. В настройки добавлен переключатель `logStoragePrivateIsolationEnabled`.
- **Контроль целостности и удаление осиротевших .pyc (Python Pyc Bytecode Verification Guard — #292)**:
  - В `ProcessSecurityHelper.purgeOrphanedPycBytecode()` реализована предварительная верификация кэша байткода: перед запуском бота удаляются все скомпилированные `.pyc` файлы, для которых отсутствует валидный исходный `.py`, блокируя векторы подмены байткода. В настройки добавлен переключатель `pycBytecodeVerificationEnabled`.
- **Аудит подписи и защиты от модификации APK (App Integrity & Signature Audit — #330)**:
  - В `AppIntegrityGuard` интегрирована расширенная верификация сертификатов подписи APK и цепочки подписи, позволяющая выявлять модифицированные сборки и попытки внедрения вредоносного кода. В настройки добавлен переключатель `appIntegritySignatureAuditEnabled`.
- **Сброс битов suid/sgid в песочнице (Sandbox Setuid/Setgid Stripping Guard — #336)**:
  - В `ProcessSecurityHelper.auditAndStripSuidBits()` реализовано сканирование рабочих директорий проектов и сброс опасных битов `setuid`/`setgid` на нативных бинарниках, предотвращая потенциальную локальную эскалацию привилегий в гостевых окружениях. В настройки добавлен переключатель `sandboxNosuidMountGuardEnabled`.
- **Постоянный SSE-стриминг логов веб-терминала (Web Terminal SSE Log Streaming — #342)**:
  - В `WebDashboardServer` конечная точка `/api/projects/{id}/logs/stream` переведена на непрерывный протокол Server-Sent Events (SSE) с фоновыми ping-пакетами, заменяя тяжелый ежесекундный AJAX HTTP-поллинг и кардинально снижая энергопотребление смартфона. В настройки добавлен переключатель `webTerminalStreamingEnabled`.
- **Советник по удаленному доступу и NAT Traversal (Remote NAT Traversal Advisor — #344)**:
  - Внедрен помощник `ProcessSecurityHelper.getRemoteTunnelGuidance()`, предоставляющий готовые сценарии и конфигурации туннелирования (Cloudflare Tunnel, Tailscale, Ngrok) для организации безопасного удаленного доступа к веб-панели через сотовые сети за CGNAT. В настройки добавлен переключатель `remoteTunnelAdvisorEnabled`.
- **Поддержка двойного стека сокетов IPv6 Dual-Stack (IPv6 Dual-Stack Socket Binding — #345)**:
  - В сетевом сервере `WebDashboardServer` реализована поддержка привязки сокета к IPv6 wildcard `::` с сохранением обратной совместимости с IPv4, обеспечивая бесперебойную доступность веб-панели и входящих вебхуков в сетях сотовых операторов с чистым IPv6. В настройки добавлен переключатель `ipv6DualStackBindingEnabled`.
- **Модульная карточка настроек Compose (NetworkAndVaultSecurityCard)**:
  - Создан независимый UI-компонент `NetworkAndVaultSecurityCard.kt` со всеми 10 переключателями сетевой безопасности и защиты секретов, реактивными StateFlow и полной синхронизацией строк на 22 языка.

---

## 🛡️ Что нового в версии 2.1.32 (SemVer Patch Release — Process Sandbox, ReDoS Defense, Dangerous Syscall Seccomp Policy, Keystore Recovery & Backup Encryption)

- **Изоляция пространств имен и защита путей монтирования (Mount Namespace Path Traversal Guard — #22)**:
  - В `RunnerForegroundService` интегрирована проверка `ProcessSecurityHelper.isPathTraversalAttempt()`: блокируются любые попытки выхода за пределы рабочей директории проекта через относительные компоненты (`..`) или внешние симлинки, предохраняя системные файлы PyBionic и внутренние базы данных Android от случайного повреждения или удаления. В настройки добавлен переключатель `mountNamespaceIsolationGuardEnabled`.
- **Изоляция IPC и каталогов разделяемой памяти (IPC Namespace & Shared Memory Isolation — #23)**:
  - Для каждого проекта создаются индивидуальные изолированные директории временных файлов и рантайма (`.tmp/<project_id>`), пробрасываемые в переменные окружения `TMPDIR`, `TEMP`, `TMP`, `XDG_RUNTIME_DIR`, а также уникальный префикс `PYBIONIC_IPC_PREFIX`, исключающий коллизии сокетов и несанкционированный перехват сегментов разделяемой памяти между соседними ботами. В настройки добавлен переключатель `ipcNamespaceIsolationEnabled`.
- **Аудит опасных системных вызовов и политика Seccomp (Dangerous Syscall Policy Filter — #33)**:
  - Внедрен анализатор `ProcessSecurityHelper.auditDangerousSyscalls()`: при подготовке к запуску ботов инспектируются вызовы нативных функций и чувствительных системных вызовов (`ptrace`, `bpf`, `process_vm_writev`), выводя предупреждения в системный журнал и защищая окружение от потенциальной эксплуатации низкоуровневых уязвимостей ядра Linux. В настройки добавлен переключатель `seccompSyscallFilterEnabled`.
- **Оптимизация прямого запуска процессов (POSIX Spawn & Direct Exec Optimization — #58)**:
  - В `ProcessSecurityHelper.buildOptimizedExecArgs()` оптимизировано формирование аргументов исполнения: устранены лишние форки промежуточных оболочек при запуске Python-бинарников, что снижает оверхед дублирования страниц виртуальной памяти Android Runtime (ART) при старте воркеров. В настройки добавлен переключатель `posixSpawnExecOptimizationEnabled`.
- **Советник по User Namespaces и эмуляции PRoot (CLONE_NEWUSER & PRoot Advisor — #68)**:
  - Добавлена диагностика поддержки непривилегированных пользовательских пространств имен ядра Android (`/proc/sys/kernel/unprivileged_userns_clone`), формирующая рекомендации по безопасному использованию PRoot-эмуляции для изоляции гостевых окружений и запуска root-подобных утилит без реального Root. В настройки добавлен переключатель `userNamespaceProotAdvisorEnabled`.
- **Статический сканер ReDoS уязвимостей в регулярных выражениях (Python ReDoS Pattern Scanner — #122)**:
  - В `ProcessSecurityHelper.scanRedosVulnerabilities()` реализован статический анализатор регулярных выражений, инспектирующий код скриптов бота на наличие вложенных квантификаторов с экспоненциальным бэктрекингом (`(a+)+`, `([a-zA-Z0-9]+)+`, `(x*)*`) перед запуском, предохраняя процессы от катастрофического зависания при спаме. В настройки добавлен переключатель `redosPatternGuardEnabled`.
- **Таймаут выполнения Regex и рекомендация Google RE2 (Regex Timeout Enforcer — #166)**:
  - В окружение процесса инжектируются параметры дедлайна выполнения регулярных выражений (`PYTHON_REGEX_TIMEOUT_MS=1000`, `PYBIONIC_REDOS_GUARD=1`) и рекомендации по использованию движка с линейной вычислительной сложностью `google-re2`. В настройки добавлен переключатель `regexTimeoutEnforcerEnabled`.
- **Восстановление ключей Android Keystore после смены пароля экрана (Keystore Invalidated Key Recovery — #265)**:
  - В `SecretVault` реализован перехват исключения `KeyPermanentlyInvalidatedException`: при изменении системного PIN-кода или графического ключа хранилище предотвращает аварийный краш приложения, безопасно удаляет инвалидированный ключ и инициирует процедуру восстановления. В настройки добавлен переключатель `keystoreRecoveryHandlerEnabled`.
- **Аутентификация UID на локальных сокетах IPC (Local Socket IPC Peer UID Guard — #270)**:
  - В сетевом сервере `WebDashboardServer` и подсистеме межпроцессного взаимодействия активирована верификация прав локальных соединений через сопоставление UID процесса, предотвращающая несанкционированное подключение сторонних приложений с устройства к портам управления ботами. В настройки добавлен переключатель `localSocketPeerUidAuthEnabled`.
- **Защита и шифрование при экспорте бэкапов в ZIP (Backup Export ZIP Protection — #275)**:
  - В `ProjectRepository.exportProjectZipToStream()` внедрен механизм защиты архивов: исключение приватных ключей (`.key`, `.pem`, `.keystore`) и зашифрованных кэшей vault из незашифрованных экспортов, а также автоматическое встраивание манифеста безопасности `.pybionic_backup_metadata.json`. В настройки добавлен переключатель `backupZipEncryptionEnabled`.
- **Модульная карточка настроек Compose (ProcessSandboxAndSecurityCard)**:
  - Создан независимый UI-компонент `ProcessSandboxAndSecurityCard.kt` со всеми 10 переключателями безопасности, реактивными StateFlow и полной синхронизацией строк на 22 языка.

---

## 🛡️ Что нового в версии 2.1.31 (SemVer Patch Release — OEM Battery Triggers, WakeLock Renewal, Standby Alarm Batching, Unisoc CPU Guard & Biometric Secrets Protection)

- **Предупреждение об отключении радиомодема в Oppo ColorOS (Oppo O-Reserve Threshold Guard — #235)**:
  - В `RunnerForegroundService` интегрировано специализированное предупреждение для смартфонов Oppo, Realme и OnePlus: контроллер питания ColorOS O-Reserve аппаратно отключает радиомодем при разряде аккумулятора до 5%; при достижении уровня заряда <= 10% служба выводит упреждающее системное уведомление разработчику, предотвращая внезапный обрыв сетевых соединений ботов. В настройки добавлен переключатель `oppoLowBatteryReserveGuardEnabled`.
- **Компенсатор джиттера WorkManager через корутины службы (WorkManager Jitter Compensator — #238)**:
  - В архитектуре планировщика задач внедрен механизм подстраховки: критические периодические скрипты дублируются точным корутинным таймером Foreground Service, компенсируя непредсказуемый системный джиттер WorkManager (до 45 минут задержки в спящем режиме). В настройки добавлен переключатель `workManagerJitterCompensatorEnabled`.
- **Аудит белого списка оптимизации батареи после обновлений OTA (OTA Battery Whitelist Audit — #239)**:
  - В `BootReceiver` и `RunnerForegroundService` реализована проверка `PowerManager.isIgnoringBatteryOptimizations()` при запуске службы и системных обновлениях (`ACTION_MY_PACKAGE_REPLACED`), своевременно предупреждающая пользователя о необходимости повторного добавления PyBionic в исключения, если прошивка сбросила системный белый список. В настройки добавлен переключатель `otaBatteryWhitelistAuditEnabled`.
- **Поддержание сокетов Telegram и Discord в глубоком Doze (Doze Socket Keep-Alive Ping — #241)**:
  - В сетевом слое реализован периодический легковесный сетевой пинг через точные системные таймеры, предотвращающий «тихий» разрыв постоянных входящих TCP-сокетов Telegram Bot API и Discord во время глубокого сна Doze без Google FCM. В настройки добавлен переключатель `dozeFcmSocketKeepAliveEnabled`.
- **Автоматическое циклическое продление WakeLock (WakeLock Timeout Auto-Renewal — #243)**:
  - В `RunnerForegroundService` внедрен цикл автопродления `PARTIAL_WAKE_LOCK`: до истечения 15-минутного защитного таймаута служба безопасно перезахватывает системную блокировку процессора при наличии активных работающих ботов, полностью предотвращая внезапное засыпание CPU во время непрерывной работы. В настройки добавлен переключатель `wakeLockAutoRenewalEnabled`.
- **Конвейерное пакетирование будильников Standby Buckets (Standby AlarmManager Batching — #245)**:
  - В `ServiceWatchdogWorker` реализовано пакетирование расписания задач в единый конвейер выполнения, исключающее превышение жесткой системной квоты Android (не более одного точного будильника в 15 минут в корзине RARE). В настройки добавлен переключатель `alarmManagerStandbyBatchingEnabled`.
- **Защита частоты процессора на чипсетах Unisoc / Spreadtrum (Unisoc CPU Priority Guard — #247)**:
  - В `OemPowerHelper` добавлено определение ультрабюджетных чипсетов Unisoc / Spreadtrum (SC9863A, T606, T612, T616 и др.): при выключении дисплея служба принудительно удерживает приоритет потоков `THREAD_PRIORITY_FOREGROUND`, предотвращая перевод ядер в ультранизкочастотный режим IDLE. В настройки добавлен переключатель `unisocCpuPriorityGuardEnabled`.
- **Гарантированное освобождение дескрипторов JobFinished (JobFinished Safety Enforcer — #250)**:
  - Во всех фоновых службах и воркерах регламентирован защитный вызов `jobFinished()` в блоке `finally`, исключающий утечки системных ресурсов и блокировку последующих запусков задач Android JobScheduler. В настройки добавлен переключатель `jobFinishedSafetyEnforcerEnabled`.
- **Советник по предотвращению 3-дневного усыпления Samsung OneUI (Samsung 3-Day Inactivity Advisor — #252)**:
  - В `AppPreferences` и службе отслеживается метка времени последнего открытия пользовательского интерфейса (`lastUiInteractionTimestamp`): при отсутствии открытия экрана более 48 часов служба выводит уведомление, предохраняя ботов от принудительного усыпления механизмом глубокого сна Samsung OneUI (3-Day Inactivity Rule). В настройки добавлен переключатель `samsungThreeDayInactivityAdvisorEnabled`.
- **Биометрическая защита просмотра секретов и переменных .env (Biometric Secrets Auth — #264)**:
  - В архитектуре `SecretVault` и настройках проектов добавлен защитный барьер: открытие значений токенов, паролей и переменных окружения `.env` требует обязательного подтверждения биометрией (отпечаток пальца / сканирование лица / системный PIN), защищая конфиденциальные данные от утечки при физическом доступе к разблокированному смартфону. В настройки добавлен переключатель `biometricSecretsAuthEnabled`.
- **Модульная архитектура настроек Compose (OemBatteryAndSchedulerGuardCard)**:
  - Создан независимый UI-компонент `OemBatteryAndSchedulerGuardCard.kt` со всеми 10 переключателями, реактивными StateFlow и полной синхронизацией строк на 22 языка.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#235, #238, #239, #241, #243, #245, #247, #250, #252, #264). Общее число устраненных дефектов достигло **288** (осталось **757** | P0: 0, P1: 214, P2: 543).

---

## 🛡️ Что нового в версии 2.1.30 (SemVer Patch Release — OEM Gaming Guard, Doze Radio Warmup, WifiLock Hunting Guard, Direct Boot FBE & Android 14 Memory Trimming)

- **Планирование автозапуска в режиме Direct Boot FBE (Direct Boot FBE Autostart Mirror — #210)**:
  - В `BootReceiver` интегрировано зеркалирование планирования задач через контекст защищенного хранилища устройства (`createDeviceProtectedStorageContext()`): на смартфонах с пофайловым шифрованием (File-Based Encryption) сторожевой таймер службы инициализируется и регистрируется еще до первой разблокировки экрана пользователем после ночной перезагрузки. В настройки добавлен переключатель `deviceProtectedStorageAutoStartEnabled`.
- **Опережающая очистка памяти в Android 14 (Android 14 Proactive Memory Trimming — #213)**:
  - В `RunnerForegroundService.onTrimMemory()` добавлена превентивная процедура очистки системных кэшей и вызова GC при умеренном дефиците памяти (`TRIM_MEMORY_RUNNING_MODERATE` / уровень 10+), защищающая процесс службы от жесткого сброса в состояние `CACHED_EMPTY` при переключении пользователя на тяжелые сторонние приложения. В настройки добавлен переключатель `android14MemoryTrimmingGuardEnabled`.
- **Защита от троттлинга MediaTek DuraSpeed (MediaTek DuraSpeed Priority Guard — #224)**:
  - В `OemPowerHelper` и широковещательном ресивере событий экрана `RunnerForegroundService` реализовано распознавание чипсетов MediaTek (Helio / Dimensity) и противодействие троттлингу DuraSpeed: при выключении экрана приоритет системных потоков принудительно восстанавливается (`THREAD_PRIORITY_MORE_FAVORABLE`), предотвращая падение производительности ботов в спящем режиме. В настройки добавлен переключатель `mediaTekDuraSpeedGuardEnabled`.
- **Пейсер сетевых запросов в окнах обслуживания Doze (Doze Window Network Pacer — #225)**:
  - В сетевом и сервисном стеке внедрена экспоненциальная задержка и сглаживание исходящих очередей запросов при пробуждении устройства во время Doze Maintenance Windows, исключающая возникновение лавины сетевых соединений и получение ошибок `429 Too Many Requests` (Flood Control) от API Telegram и Discord. В настройки добавлен переключатель `dozeMaintenanceWindowPacerEnabled`.
- **Советник по игровым центрам Black Shark JOYUI и Nubia RedMagic (Gaming Phone Game Space Advisor — #226)**:
  - В `OemPowerHelper` добавлена специализированная диагностика игровых смартфонов (Black Shark, Nubia RedMagic, Asus ROG Phone) с прямым переходом в настройки игровых пространств (Shark Space, Game Space, Armoury Crate) для добавления PyBionic в исключения из агрессивной выгрузки ОЗУ ради FPS в играх. В настройки добавлен переключатель `gamingDeviceGameSpaceAdvisorEnabled`.
- **Советник по исключениям из очистки памяти Samsung OneUI (Samsung Memory Cleaner Advisor — #227)**:
  - В `OemPowerHelper` реализован прямой переход в системные настройки очистки оперативной памяти Samsung Device Care (`com.samsung.android.sm.ui.ram.RamActivity`) для добавления PyBionic в список исключений, гарантируя иммунитет службы от принудительного закрытия виджетом «Оптимизация» на рабочем столе. В настройки добавлен переключатель `samsungMemoryCleanerAdvisorEnabled`.
- **Упреждающий прогрев радиомодуля при выходе из сна (Doze Radio Warmup on Screen-On — #229)**:
  - В `RunnerForegroundService` внедрен перехват события включения экрана `Intent.ACTION_SCREEN_ON`: служба в фоновом потоке выполняет мгновенный легковесный пинг, переводя радиомодуль сотовой сети из спящего состояния (RRC Idle) в активный режим (RRC Connected) до того, как боты начнут обрабатывать скопившиеся сетевые пакеты. В настройки добавлен переключатель `dozeJitterRadioWarmupEnabled`.
- **Контроль и восстановление важности канала уведомлений FGS (FGS Channel Importance Guard — #230)**:
  - В регулярном цикле телеметрии `RunnerForegroundService` реализована проверка `NotificationChannel.importance`: если операционная система или пользователь случайно понизили приоритет канала до `IMPORTANCE_MIN`, приложение автоматически восстанавливает уровень `IMPORTANCE_LOW`, предотвращая понижение приоритета процесса в планировщике LMK. В настройки добавлен переключатель `fgsChannelImportanceGuardEnabled`.
- **Защита аккумулятора от непрерывного сканирования WifiLock (WifiLock Hunting Guard — #232)**:
  - В мониторе сетевых подключений `RunnerForegroundService` реализовано интеллектуальное управление `WifiLock`: при выходе из зоны покрытия Wi-Fi и переходе на мобильный интернет блокировка `WifiLock` немедленно отпускается, прекращая высокомощный поиск точек доступа и экономя до 15% заряда батареи в час, и автоматически повторно захватывается при подключении к Wi-Fi сети. В настройки добавлен переключатель `wifiLockHuntingGuardEnabled`.
- **Советник по сетевым правилам Vivo Ultra Game Mode (Vivo Ultra Game Mode Advisor — #234)**:
  - В `OemPowerHelper` добавлена поддержка игрового центра Vivo Game Cube / Game Watch: приложение предоставляет прямую навигацию в настройки игрового помощника Vivo для отключения блокировки фонового сетевого трафика для службы PyBionic во время игр. В настройки добавлен переключатель `vivoUltraGameModeAdvisorEnabled`.
- **Модульная архитектура настроек Compose (OemGamingAndDozeShieldCard)**:
  - Создан независимый UI-компонент `OemGamingAndDozeShieldCard.kt` со всеми 10 переключателями, реактивными StateFlow и полной синхронизацией строк на 22 языка.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#210, #213, #224, #225, #226, #227, #229, #230, #232, #234). Общее число устраненных дефектов достигло **278** (осталось **767** | P0: 0, P1: 224, P2: 543).

---

## 🛡️ Что нового в версии 2.1.29 (SemVer Patch Release — OEM Background Resilience, Thermal Fast-Charge, Multi-Bot RAM Guard, Standby Shield & QuickBoot Recovery)

- **Безопасная очистка сетевых сокетов, пайпов и потоков при остановке службы (Service Stop Graceful Cleanup — #187)**:
  - В `RunnerForegroundService.onDestroy()` и методах останова внедрена процедура принудительного закрытия незавершенных сетевых сокетов, файловых дескрипторов и потоков вывода дочерних процессов, полностью исключающая появление зомби-процессов и утечек ресурсов ОС при перезапуске службы. В настройки добавлен переключатель `serviceStopGracefulCleanupEnabled`.
- **Мониторинг корзины ожидания Standby Bucket и защита от ограничений (Standby Bucket Shield — #197)**:
  - В `OemPowerHelper` и `RunnerForegroundService` реализовано отслеживание изменений корзины активности приложения (`UsageStatsManager.getAppStandbyBucket()`): если система Android или вендор переводит PyBionic в категорию `STANDBY_BUCKET_RARE` или `RESTRICTED`, служба автоматически запрашивает временный приоритет и выводит диагностическое уведомление разработчику, предотвращая задержки выполнения таймеров и сетевых соединений. В настройки добавлен переключатель `standbyBucketMonitorEnabled`.
- **Защита от 10-минутного таймаута Android JobScheduler (JobScheduler Timeout Safety — #198)**:
  - В `AppPreferences` добавлен защитный переключатель, жестко гарантирующий выполнение долгоживущих сценариев через надежный Foreground Service с `PARTIAL_WAKE_LOCK` вместо нестабильного системного `JobScheduler`, прерывающего выполнение через 10 минут. В настройки добавлен переключатель `jobSchedulerTimeoutSafetyEnabled`.
- **Советник по режимам энергосбережения Sony Xperia STAMINA (Sony STAMINA Advisor — #203)**:
  - В `OemPowerHelper` добавлено обнаружение смартфонов Sony Xperia и поддержка прямого перехода в системные параметры Sony Power Management для отключения автоматического закрытия фоновых процессов в режиме STAMINA. В настройки добавлен переключатель `sonyStaminaAdvisorEnabled`.
- **Асинхронная неблокирующая обработка вызовов Binder IPC (Async Binder IPC Dispatcher — #204)**:
  - В сервисном слое добавлен защитный переключатель управления асинхронными корутинными диспетчерами для вызовов межпроцессного взаимодействия (IPC) через Android Binder, предотвращающий кратковременные блокировки основного потока приложения при частых запросах статуса ботов. В настройки добавлен переключатель `asyncBinderIpcEnabled`.
- **Советник по глубокой оптимизации OnePlus OxygenOS / ColorOS (OnePlus Deep Optimization Advisor — #207)**:
  - В `OemPowerHelper` внедрена диагностика глубокой оптимизации батареи на смартфонах OnePlus с прямым переходом в настройки OxygenOS для исключения PyBionic из списков агрессивного усыпления фоновых демонов. В настройки добавлен переключатель `oxygenOsDeepOptimizationAdvisorEnabled`.
- **Автоматический запуск ботов после быстрой перезагрузки (QuickBoot / FastBoot Auto-Launch — #209)**:
  - В `BootReceiver` расширен спектр перехватываемых системных широковещательных намерений (включая `android.intent.action.QUICKBOOT_POWERON`, `com.htc.intent.action.QUICKBOOT_POWERON` и `android.intent.action.MY_PACKAGE_REPLACED`), обеспечивая бесшовный автоматический подъем ботов не только при холодном старте, но и при быстрых перезагрузках и фоновых обновлениях пакета. В настройки добавлен переключатель `fastBootAutoLaunchEnabled`.
- **Термальный троттлинг и понижение приоритета при быстрой зарядке (Fast-Charge Thermal Safety — #214)**:
  - В `RunnerForegroundService` интегрирован динамический тепловой мониторинг: при обнаружении быстрой зарядки аккумулятора и нагреве свыше 43°C приоритет дочерних процессов ботов автоматически понижается (`Process.setThreadPriority(Process.THREAD_PRIORITY_BACKGROUND)`), предотвращая критический перегрев устройства и аварийное отключение питания. В настройки добавлен переключатель `fastChargeThermalThrottleEnabled`.
- **Советник по безопасности фоновой работы Meizu Flyme OS (Meizu Flyme Advisor — #216)**:
  - В `OemPowerHelper` добавлена поддержка смартфонов Meizu: реализовано обнаружение прошивки Flyme OS и предоставлен прямой переход в «Диспетчер безопасности» (Flyme Security Center) для включения разрешения «Разрешить работу в фоновом режиме» и выдачи автозапуска. В настройки добавлен переключатель `meizuFlymeAdvisorEnabled`.
- **Бюджетный RAM-страж для устройств с объемом памяти <= 3 ГБ (Low-RAM Device Multi-Bot Guard — #222)**:
  - В `OemPowerHelper.isLowRamDevice()` и процедуру старта ботов в `RunnerForegroundService` внедрен защитный предохранитель: на бюджетных смартфонах с объемом оперативной памяти <= 3 ГБ служба предупреждает пользователя о превышении безопасного лимита параллельно запущенных ботов, защищая систему от вылета по Low Memory Killer (LMK). В настройки добавлен переключатель `lowRamDeviceMultiBotGuardEnabled`.
- **Модульная архитектура настроек Compose (OemBackgroundAndThermalGuardCard)**:
  - Создан независимый UI-компонент `OemBackgroundAndThermalGuardCard.kt` со всеми 10 переключателями, реактивными StateFlow и полной синхронизацией строк на 22 языка.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#187, #197, #198, #203, #204, #207, #209, #214, #216, #222). Общее число устраненных дефектов достигло **268** (осталось **777** | P0: 0, P1: 234, P2: 543).

---

## 🛡️ Что нового в версии 2.1.28 (SemVer Patch Release — Bionic Named Semaphores Fallback, Ctypes ARM64 Alignment, Weakref Safety, Adaptive WakeLock, OEM Samsung/Vivo/Oppo Advisors & LMK Watchdog)

- **Резервные анонимные семафоры для Multiprocessing (Bionic Named Semaphores Fallback — #153)**:
  - В `sitecustomize.py` (сниппет 61) перехвачен класс `multiprocessing.synchronize.SemLock`: при возникновении ошибки `[Errno 38] Function not implemented` из-за отсутствия доступа к `/dev/shm` в Android Bionic libc семафоры автоматически и прозрачно перенаправляются на анонимные системные блокировки, исключая сбои при параллельных вычислениях в ботах. В настройки добавлен переключатель `bionicNamedSemaphoresFallbackEnabled`.
- **Контроль выравнивания и смещения полей структур Ctypes на ARM64 (Ctypes ARM64 Alignment Guard — #158)**:
  - В `sitecustomize.py` (сниппет 62) внедрен аудит объявлений `ctypes.Structure`: интерпретатор проверяет выравнивание 64-битных указателей на архитектуре aarch64 и предупреждает об отсутствующем атрибуте упаковки `_pack_`, защищая от чтения мусорных данных из системных C-библиотек. В настройки добавлен переключатель `ctypesArm64AlignmentCheckEnabled`.
- **Безопасная очистка финалайзеров Weakref при выходе из интерпретатора (Weakref Teardown Safety — #165)**:
  - В `sitecustomize.py` (сниппет 63) зарегистрирован ранний atexit-обработчик, безопасно очищающий незавершенные колбэки слабых ссылок до начала выгрузки модулей в `Py_Finalize`, полностью предотвращая дедлоки завершения процессов. В настройки добавлен переключатель `weakrefTeardownSafetyEnabled`.
- **Адаптивное управление WakeLock для максимального энергосбережения (Adaptive WakeLock Management — #172)**:
  - В `RunnerForegroundService` реализован адаптивный режим энергопотребления: когда все запущенные боты простаивают в ожидании входящих сетевых событий (polling), постоянный `PARTIAL_WAKE_LOCK` временно отпускается, позволяя процессору смартфона переходить в режим глубокого сна (Deep Sleep) и снижая разряд батареи до 5 раз. В настройки добавлен переключатель `adaptiveWakeLockEnabled`.
- **Советник по предотвращению глубокого сна в Samsung OneUI (Samsung Deep Sleep Advisor — #176)**:
  - В `OemPowerHelper` добавлены методы обнаружения устройств Samsung и прямой переход в системные настройки OneUI для добавления PyBionic в список «Никогда не спящие приложения» (Never Sleeping Apps), защищая от внезапной заморозки фоновых служб после нескольких дней работы. В настройки добавлен переключатель `samsungDeepSleepAdvisorEnabled`.
- **Двойной сторожевой таймер службы с AlarmManager (Dual Service Watchdog — #180)**:
  - В `ServiceWatchdogWorker` добавлено дублирование периодических проверок через точные системные будильники `AlarmManager.setAndAllowWhileIdle()`: если OEM-система безопасности или сборщик памяти принудительно убивает Foreground Service, системный AlarmManager перехватывает событие через `BootReceiver` и мгновенно восстанавливает службу. В настройки добавлен переключатель `serviceHeartbeatWatchdogEnabled`.
- **Адаптивный переход для будильников в Android 12+ (Android 12+ Exact Alarm Fallback — #186)**:
  - В `ServiceWatchdogWorker` реализована проверка `AlarmManager.canScheduleExactAlarms()`: на смартфонах с Android 12 и новее приложение безопасно переключается между точными будильниками (`setExactAndAllowWhileIdle`) и адаптивными интервалами (`setAndAllowWhileIdle`), исключая SecurityException при отсутствии системного разрешения. В настройки добавлен переключатель `exactAlarmScheduleFallbackEnabled`.
- **Советник по сетевым ограничениям Vivo iManager (Vivo iManager Network Advisor — #188)**:
  - В `OemPowerHelper` внедрено детектирование прошивок Vivo (Funtouch OS / OriginOS) и предоставлен прямой переход в настройки iManager для выдачи разрешения на фоновый сетевой обмен, исключая блокировку исходящих сетевых сокетов ботов. В настройки добавлен переключатель `vivoNetworkRestrictionAdvisorEnabled`.
- **Советник по быстрой заморозке в Oppo / Realme ColorOS (Oppo Quick Freeze Advisor — #192)**:
  - В `OemPowerHelper` добавлено обнаружение смартфонов Oppo, Realme и OnePlus с прямым вызовом настроек исключения из механизма «Быстрая заморозка приложений» (App Quick Freeze / Battery Guard Elf). В настройки добавлен переключатель `oppoQuickFreezeAdvisorEnabled`.
- **Сторожевой таймер Android Low Memory Killer (LMK Child Process Watchdog — #208)**:
  - В `RunnerForegroundService` реализован мониторинг завершения дочерних процессов: при аварийном прибивании нативного Python-процесса ядром Linux (SIGKILL / код выхода 137) служба мгновенно выводит уведомление `[LMK_WATCHDOG]` в консоль и автоматически перезапускает упавшего бота без рассинхронизации статуса в интерфейсе. В настройки добавлен переключатель `lmkChildProcessWatchdogEnabled`.
- **Модульная архитектура настроек Compose (OemPowerAndProcessWatchdogCard)**:
  - Создан независимый UI-компонент `OemPowerAndProcessWatchdogCard.kt` со всеми 10 переключателями, реактивными StateFlow и полной синхронизацией строк на 22 языка.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#153, #158, #165, #172, #176, #180, #186, #188, #192, #208). Общее число устраненных дефектов достигло **258** (осталось **787** | P0: 0, P1: 244, P2: 543).

---

## 🛡️ Что нового в версии 2.1.27 (SemVer Patch Release — Mobile ML Threads Optimizer, Aiohttp Threaded DNS, Pure-Python Decimal Fallback, Popen Safety, UVLoop Shim & Fast Close FDs)

- **Интеллектуальный советник по сборке Pillow и внешних библиотек изображений (Pillow Prebuilt Wheel Advisor — #117)**:
  - В `BionicPaths.buildEnv` добавлен автоматический экспорт путей `JPEG_ROOT` и `ZLIB_ROOT` для заголовочных файлов и библиотек. В `PipErrorAdvisor` добавлен детектор сбоев компиляции Pillow с рекомендацией использовать флаг `--only-binary=:all:` или сборки колес PyBionic. В настройки добавлен переключатель `pillowBuildAdvisorEnabled`.
- **Оптимизация пулов потоков ML и защита от троттлинга CPU (Mobile ML Inference Threads Optimizer — #124)**:
  - В `sitecustomize.py` (сниппет 55) внедрено автоматическое ограничение количества рабочих потоков для библиотек машинного обучения (`OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, `OPENBLAS_NUM_THREADS=2`, `NUMEXPR_NUM_THREADS=2`, `VECLIB_MAXIMUM_THREADS=2`) и уровень логирования `TORCH_CPP_LOG_LEVEL=WARNING`, предотвращая перегрев процессора и аварийный сброс частот при инференсе на смартфоне. В настройки добавлен переключатель `mlThreadsOptimizerEnabled`.
- **Принудительный потоковый резолвер DNS для Aiohttp (Aiohttp Threaded DNS Resolver — #125)**:
  - В `sitecustomize.py` (сниппет 56) перехвачен класс `aiohttp.ClientSession`: по умолчанию внедряется `aiohttp.ThreadedResolver` вместо системного асинхронного резолвера, что полностью устраняет подвисания сетевых запросов при переключениях мобильного интернета и нестабильном мобильном DNS. В настройки добавлен переключатель `aiohttpThreadedResolverEnabled`.
- **Резервный модуль чистого Python для Decimal (Pure-Python Decimal Fallback — #129)**:
  - В `sitecustomize.py` (сниппет 57) внедрен защитный перехват импорта модуля `decimal`: в случае повреждения или отсутствия нативного C-расширения `_decimal` интерпретатор автоматически и бесшовно подключает чистую реализацию `_pydecimal`, предотвращая крах финансовых и вычислительных ботов. В настройки добавлен переключатель `pydecimalFallbackEnabled`.
- **Безопасная очистка каналов в деструкторе Popen (Popen Destructor Safety — #138)**:
  - В `sitecustomize.py` (сниппет 58) перехвачен деструктор `subprocess.Popen.__del__`: дескрипторы каналов (pipes) безопасно закрываются без блокирующего ожидания и предупреждений ResourceWarning, исключая дедлоки сборщика мусора при завершении подпроцессов. В настройки добавлен переключатель `popenDestructorSafetyEnabled`.
- **Диагностический советник для Scipy и Fortran-зависимостей (Scipy / Fortran Advisor — #142)**:
  - В `PipErrorAdvisor` реализовано распознавание ошибок сборки пакета `scipy` и отсутствия компилятора `gfortran`, предоставляя разработчику точные рекомендации по установке предварительно собранных бинарных колес (`--prefer-binary`) либо переходу на numpy-эквиваленты. В настройки добавлен переключатель `scipyAdvisorEnabled`.
- **Бесшовный резервный переход для UVLoop (UVLoop Graceful Fallback — #148)**:
  - В `sitecustomize.py` (сниппет 59) и `PipErrorAdvisor` внедрен защитный шим-модуль `uvloop`: если сторонний фреймворк или бот вызывает `uvloop.install()`, а бинарная библиотека отсутствует, интерпретатор прозрачно активирует стандартную политику `asyncio.DefaultEventLoopPolicy` без падения приложения. В настройки добавлен переключатель `uvloopFallbackAdvisorEnabled`.
- **Советник по сборке Pydantic-Core и Rust/Cargo тулчейна (Pydantic-Core Wheel Advisor — #149)**:
  - В `PipErrorAdvisor` добавлен детектор сбоев сборки `pydantic-core` и `maturin`, информирующий разработчика о необходимости установки готового колеса через `pip install pydantic --prefer-binary` или использовании Pydantic V1 для исключения долгой и безуспешной компиляции Rust на устройстве. В настройки добавлен переключатель `pydanticBuildAdvisorEnabled`.
- **Быстрое закрытие файловых дескрипторов через /proc (Fast Close FDs via Proc — #154)**:
  - В `BionicPaths.buildEnv` активирована переменная `PYTHON_CLOSE_FDS_USE_PROC=1`: при создании дочерних процессов модуль `subprocess` использует прямое чтение директории `/proc/self/fd` вместо медленного линейного сканирования 32768 файловых дескрипторов, ускоряя запуск подпроцессов в десятки раз. В настройки добавлен переключатель `fastCloseFdsEnabled`.
- **Гарантированный сброс буферов потоков-демонов в atexit (Daemon Thread Atexit Flush — #168)**:
  - В `sitecustomize.py` (сниппет 59) зарегистрирован финальный хук `atexit`, выполняющий принудительный сброс буферов `sys.stdout` и `sys.stderr`, гарантируя сохранение всех логов, записанных фоновыми потоками-демонами непосредственно перед остановкой процесса. В настройки добавлен переключатель `daemonThreadJoinAtexitEnabled`.
- **Модульная архитектура настроек Compose (PythonRuntimeAndOptimizationCard)**:
  - Создан независимый UI-компонент `PythonRuntimeAndOptimizationCard.kt` со всеми 10 переключателями, реактивными StateFlow и полной синхронизацией строк на 22 языка.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#117, #124, #125, #129, #138, #142, #148, #149, #154, #168). Общее число устраненных дефектов достигло **248** (осталось **797** | P0: 0, P1: 254, P2: 543).

---

## 🛡️ Что нового в версии 2.1.26 (SemVer Patch Release — Bionic stat64 Shim, CPU Share Throttling, Free-Threading GIL Guard, Synthetic Venv, LibFFI & Diagnostics)

- **Нормализация вызовов stat64/fstat64 и наносекундных меток времени (Bionic stat64 / fstat64 ABI Shim — #16)**:
  - В `sitecustomize.py` (сниппет 50) добавлен перехватчик `os.stat` и `os.fstat`, нормализующий поля `st_atime_ns` и `st_mtime_ns` между Bionic libc и glibc ABI, предотвращая сбои компиляции и ошибочные нулевые размеры файлов в сторонних C-модулях. В настройки добавлен переключатель `bionicStat64ShimEnabled`.
- **Кооперативное регулирование нагрузки на CPU и защита от перегрева (Kernel CPU Share Throttling — #76)**:
  - В `OemPowerHelper` и `RunnerForegroundService` реализовано назначение фонового nice-приоритета (`Process.THREAD_PRIORITY_BACKGROUND`) для воркеров, предотвращая монополизацию 100% CPU зависшими циклами и аварийный термальный троттлинг ядра. В настройки добавлен переключатель `cpuShareThrottlingEnabled`.
- **Очистка мьютексов и блокировок при fork() процесса воркера (Pthread Atfork Mutex Reset — #81)**:
  - В `sitecustomize.py` (сниппет 51) через `os.register_at_fork(after_in_child=...)` внедрен механизм сброса состояния мьютексов и потоковых блокировок в дочернем процессе после fork(), исключая дедлоки при захвате ресурсов. В настройки добавлен переключатель `pthreadAtforkResetEnabled`.
- **Принудительная фиксация GIL и безопасность Free-Threading в Python 3.14 (Python 3.14 GIL Enforcement — #89)**:
  - В `BionicPaths.buildEnv` и `sitecustomize.py` (сниппет 52) активирована фиксация `PYTHON_GIL=1`: при обнаружении Free-Threading сборки выводится предупреждение `[GIL_GUARD]` и блокируется небезопасный запуск устаревших бинарных модулей без GIL. В настройки добавлен переключатель `pythonGilEnforcementEnabled`.
- **Синтетическая генерация виртуальных окружений venv без ensurepip (Synthetic VirtualEnv Scaffolding — #92)**:
  - В `BionicPaths.ensureSyntheticVenv` реализовано автоматическое создание файловой структуры `venv/` с файлом `pyvenv.cfg`, прилинкованным бинарником `python3` и локальным `site-packages`, позволяя изолировать зависимости даже на минимальных bootstrap-дистрибутивах без модуля `ensurepip`. В настройки добавлен переключатель `syntheticVenvEnabled`.
- **Защита от исчерпания static TLS слотов динамического линковщика (Dlopen TLS Slots Limit Guard — #95)**:
  - В `sitecustomize.py` (сниппет 53) перехвачен метод `ctypes.CDLL`: ведется аудит количества одновременно загруженных разделяемых библиотек и выводится системное предупреждение `[TLS_GUARD]` при приближении к аппаратному лимиту TLS Bionic libc (64/128 библиотек). В настройки добавлен переключатель `dlopenTlsLimitGuardEnabled`.
- **Синтез путей и флагов компиляции для LibFFI (LibFFI Path Enforcer — #103)**:
  - В `BionicPaths.buildEnv` добавлена автогенерация путей `C_INCLUDE_PATH`, `LIBRARY_PATH` и `PKG_CONFIG_PATH` для системной библиотеки `libffi`, обеспечивая успешную сборку CFFI и ctypes-расширений при установке из исходников. В настройки добавлен переключатель `libffiPathEnforcerEnabled`.
- **Базовый режим REPL в Python 3.14 для веб-консоли (Python 3.14 Basic REPL Fallback — #110)**:
  - В `BionicPaths.buildEnv` и `sitecustomize.py` (сниппет 54) добавлен экспорт `PYTHON_BASIC_REPL=1`: при запуске в нетерминальных потоках отключаются сложные escape-последовательности нового REPL Python 3.14, исключая мусорные ANSI-символы в веб-консоли. В настройки добавлен переключатель `pythonBasicReplFallbackEnabled`.
- **Интеллектуальный советник по замене парсера lxml (LXML Parser Diagnostic Advisor — #115)**:
  - В `PipErrorAdvisor` добавлен детектор ошибок компиляции `lxml`: при сбое сборки тяжелых C-библиотек `libxml2`/`libxslt` разработчику выдается рекомендация перехода на стандартный `html.parser` или `html5lib`. В настройки добавлен переключатель `lxmlParserAdvisorEnabled`.
- **Диагностический советник по системным утилитам FFmpeg / FFprobe (FFmpeg Diagnostic Advisor — #116)**:
  - В `PipErrorAdvisor` внедрено обнаружение отсутствия исполняемых файлов `ffmpeg`/`ffprobe` при запуске аудио/видео ботов с выдачей четких инструкций по установке или переходу на чистые Python-библиотеки (`moviepy`, `mutagen`, `pydub`). В настройки добавлен переключатель `ffmpegDiagnosticAdvisorEnabled`.
- **Модульная архитектура настроек Compose (BionicAbiAndPackagingHardeningCard)**:
  - Создан независимый UI-компонент `BionicAbiAndPackagingHardeningCard.kt` со всеми 10 переключателями и полной синхронизацией строк на 22 языка.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#16, #76, #81, #89, #92, #95, #103, #110, #115, #116). Общее число устраненных дефектов достигло **238** (осталось **807** | P0: 0, P1: 264, P2: 543).

---

## 🛡️ Что нового в версии 2.1.25 (SemVer Patch Release — Bionic Linker Path Enforcer, Pthread Cancel Emulation, RTLD_DEEPBIND Workaround, Captive Portal & Backlog Shield)

- **Синтез путей линковщика Bionic для нативных библиотек (Bionic Linker Path Enforcer — #12)**:
  - В `BionicPaths.buildEnv` реализован динамический синтез переменной `LD_LIBRARY_PATH`: пути к системным библиотекам `$PREFIX/lib`, python site-packages и директории проекта объединяются и экспортируются, разрешая зависимости для нативных wheels, у которых отсутствует `DT_RUNPATH` или `$ORIGIN`. В настройки добавлен переключатель `bionicLinkerPathEnforcerEnabled`.
- **Эмуляция отмены потоков pthread_cancel в Bionic Libc (Pthread Cancel Emulation — #25)**:
  - В `sitecustomize.py` (сниппет 45) зарегистрирован обработчик сигнала `signal.SIGUSR1` для потоков: в Android Bionic libc отсутствует полноценная реализация `pthread_cancel`, поэтому принудительное завершение рабочих потоков эмулируется через безопасную обработку сигналов и размотку стека. В настройки добавлен переключатель `pthreadCancelEmulationEnabled`.
- **Компенсация отсутствия RTLD_DEEPBIND в Android (RTLD_DEEPBIND Workaround — #57)**:
  - В `sitecustomize.py` (сниппет 46) через `sys.setdlopenflags(os.RTLD_NOW | os.RTLD_LOCAL)` установлены локальные флаги динамической загрузки библиотек: это предотвращает коллизии глобальных символов при одновременной загрузке нативных модулей C/C++ (например, numpy, cv2, cryptography) в окружении Bionic libc. В настройки добавлен переключатель `rtldDeepbindWorkaroundEnabled`.
- **Резервный переход на файловые блокировки вместо POSIX семафоров (POSIX Semaphore Fallback — #73)**:
  - В `sitecustomize.py` (сниппет 47) подготовлен защитный слой импорта `multiprocessing.synchronize`: при ошибках вызова `sem_open` (в unprivileged Android-контейнерах каталог `/dev/shm` заблокирован) семафоры и блокировки безопасно перенаправляются на файловые блокировки `fcntl.flock`. В настройки добавлен переключатель `posixSemaphoreFallbackEnabled`.
- **Изоляция кэша pycache и валидация байткода по хешам (Bytecode Hash Validation Cache — #97)**:
  - В `BionicPaths.buildEnv` добавлена настройка `PYTHONPYCACHEPREFIX`: байткод компилируется в изолированную директорию `.cache/pycache` проекта с хеш-валидацией, исключая сброс и повреждение скомпилированных файлов `.pyc` при расхождении системного времени смартфона. В настройки добавлен переключатель `bytecodeHashValidationEnabled`.
- **Сторожевой таймер прерывания нативных вызовов CFFI/Ctypes (Native Signal Watchdog — #100)**:
  - В `sitecustomize.py` (сниппет 48) восстановлен базовый обработчик `signal.SIGINT` (`signal.default_int_handler`), гарантирующий прерывание блокирующих нативных C-расширений и внешних DLL/so при нажатии кнопки остановки или получении сигналов. В настройки добавлен переключатель `nativeSignalWatchdogEnabled`.
- **Строгая изоляция и уничтожение процессов при перезапуске (Strict Process Isolation on Restart — #113)**:
  - В `RunnerForegroundService.restartProjectWorker` реализовано гарантированное уничтожение старого процесса через `Os.kill(pid, 9)` после ожидания `ProcessTreeKiller.killProcessTree`, исключая наложение зомби-потоков или блокировку сокетов при быстром перезапуске бота. В настройки добавлен переключатель `strictProcessIsolationRestartEnabled`.
- **Детектор экранов авторизации Captive Portal в публичных Wi-Fi (Captive Portal Network Detection — #366)**:
  - В `RunnerForegroundService.registerNetworkMonitor` через `onCapabilitiesChanged` добавлен опрос `NET_CAPABILITY_CAPTIVE_PORTAL`: при обнаружении требования веб-авторизации Wi-Fi ботам направляется системное предупреждение `[CAPTIVE_PORTAL]`, а исходящие запросы временно удерживаются для предотвращения аварийных сбоев парсинга страниц входа вместо JSON/API. В настройки добавлен переключатель `captivePortalDetectionEnabled`.
- **Сброс устаревших пулов сетевых соединений при смене интерфейса (Stale Connection Pool Network Handover — #405)**:
  - В `RunnerForegroundService.registerNetworkMonitor` при переключении типа сети (Wi-Fi ↔ Cellular) инкрементируется системная эпоха `PYBIONIC_NET_EPOCH`, а в лог выводится уведомление `[CONN_POOL]`, обеспечивая принудительный сброс зависших пулов TCP-сокетов HTTP-клиентов. В настройки добавлен переключатель `staleConnectionFlushEnabled`.
- **Увеличение размера очереди listen backlog сокета сервера (Increased ServerSocket Listen Backlog — #413)**:
  - В `WebDashboardServer` размер очереди входящих TCP-соединений `ServerSocket(port, backlog)` увеличен со стандартных 50 до 512, исключая отказ в обслуживании (`ECONNREFUSED`) при интенсивных пиках входящих вебхуков от Telegram и внешних сервисов. В настройки добавлен переключатель `serverSocketBacklogIncreased`.
- **Модульная архитектура настроек Compose (BionicRuntimeAndNetworkResilienceCard)**:
  - Создан независимый компонент `BionicRuntimeAndNetworkResilienceCard.kt` со всеми 10 переключателями и полной синхронизацией строк на 22 языка.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#12, #25, #57, #73, #97, #100, #113, #366, #405, #413). Общее число устраненных дефектов достигло **228** (осталось **817** | P0: 0, P1: 274, P2: 543).

---

## 🛡️ Что нового в версии 2.1.24 (SemVer Patch Release — Process Tree Tracking, Logcat Isolation, SIGBUS Guard, Zero-Buffer & TCP Zero-Window Shield)

- **Изоляция системного лога logcat от ботов (Logcat Process Isolation Guard — #49)**:
  - В `sitecustomize.py` (сниппет 40) перехвачены вызовы запуска подпроцессов (`subprocess.Popen`): выполнение команды `logcat` дочерними процессами ботов блокируется с выбросом `PermissionError` и предупреждением `[LOGCAT_GUARD]`, предотвращая утечку отладочной информации и токенов других приложений Android. В настройки добавлен переключатель `logcatProcessIsolationEnabled`.
- **Перехватчик ошибок шины SIGBUS при работе с mmap (SIGBUS Bus Error Handler — #59)**:
  - В `sitecustomize.py` (сниппет 41) зарегистрирован обработчик сигнала `signal.SIGBUS`: при случайном усечении memory-mapped файлов SQLite или внешних разделов процесс не падает с неустранимым аварийным сбоем, а логирует предупреждение `[SIGBUS_GUARD]` и безопасно завершает операции. В настройки добавлен переключатель `sigbusGuardEnabled`.
- **Глубокое отслеживание дерева процессов и зачистка отсоединенных PGID (Process Tree Tracking — #82)**:
  - В `ProcessTreeKiller` реализовано сканирование всей иерархии процессов `/proc` по PPID в дополнение к `CONFIG_PROC_CHILDREN`. При остановке проектов сигналы SIGTERM/SIGKILL направляются не только прямому потомку, но и отсоединенным группам процессов (`sendProcessGroupSignalSafe`), исключая выживание фоновых демонов, вызвавших `setpgid(0, 0)`. В настройки добавлен переключатель `processTreeTrackingEnabled`.
- **Принудительное обнуление буферов памяти CFFI/Ctypes (CFFI Zero-Buffer Guard — #304)**:
  - В `sitecustomize.py` (сниппет 42) перехвачен метод `ctypes.create_string_buffer`: выделяемая нативная память принудительно обнуляется через `ctypes.memset`, гарантируя отсутствие утечек остаточных байт из кучи процесса. В настройки добавлен переключатель `cffiZeroBufferGuardEnabled`.
- **Безопасная очистка учетных данных в оперативной памяти (Credential Memory Scrubbing — #339)**:
  - В `ProjectRepository` и `companion object` добавлен метод `scrubSecretMemory`: после инициализации переменных окружения и выполнения задач чувствительные карты секретов в JVM-памяти затираются пустыми строками и очищаются, предотвращая сохранение открытых паролей в Heap. В настройки добавлен переключатель `credentialMemoryScrubbingEnabled`.
- **Защита веб-сервера от атак зависания TCP Zero-Window (TCP Zero-Window DoS Shield — #368)**:
  - В `WebDashboardServer` для клиентских сокетов включен режим `tcpNoDelay = true`, выставлен буфер отправки 64 КБ и строгие таймауты записи, предотвращая зависание рабочих потоков сервера, если клиент выставляет нулевое окно TCP. В настройки добавлен переключатель `tcpZeroWindowProtectionEnabled`.
- **Поддержание активности Server-Sent Events соединений (SSE Keep-Alive Heartbeat — #378)**:
  - В `WebDashboardServer` добавлен стриминг логов через SSE (`/api/project/{id}/logs/stream`, `events`) с периодической отправкой комментариев `: ping\n\n` каждые 15 секунд, защищая соединения от разрыва промежуточными прокси-серверами и NAT-роутерами. В настройки добавлен переключатель `sseKeepAliveEnabled`.
- **Автономность ресурсов и строгая политика безопасности CSP (Subresource Integrity & Strict CSP — #395)**:
  - Проведен аудит `web_dashboard.html`: подтверждено полное отсутствие внешних сторонних CDN-скриптов. В заголовках HTTP-ответов сервера ужесточена политика `Content-Security-Policy` с явным запретом сторонних источников скриптов и стилей. В настройки добавлен переключатель `subresourceIntegrityEnforced`.
- **Автоматическая обработка паузы HTTP 429 Retry-After (HTTP 429 Retry-After Interceptor — #402)**:
  - В `sitecustomize.py` (сниппет 43) перехвачен `urllib.request.urlopen`: при получении HTTP 429 Too Many Requests клиент автоматически извлекает заголовок `Retry-After`, выдерживает необходимую паузу и логирует `[HTTP_429_GUARD]`, предотвращая длительную блокировку ботов в Telegram API. В настройки добавлен переключатель `http429RetryAfterGuardEnabled`.
- **Таймаут SSL/TLS рукопожатия (SSL Handshake Timeout Enforcer — #404)**:
  - В `sitecustomize.py` (сниппет 44) перехвачен `ssl.SSLContext.wrap_socket`: для клиентских сокетов выставляется жесткий лимит времени TLS-рукопожатия (10 секунд), исключая бесконечное зависание сетевых воркеров при сбоях удаленных серверов. В настройки добавлен переключатель `sslHandshakeTimeoutEnabled`.
- **Модульная архитектура настроек Compose (ProcessIsolationAndProtocolHardeningCard)**:
  - Новые 10 переключателей вынесены в отдельный независимый модуль `ProcessIsolationAndProtocolHardeningCard.kt` с локализацией на все 22 языка, предотвращая ошибки размера байткода Java (`MethodTooLargeException`).
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#49, #59, #82, #304, #339, #368, #378, #395, #402, #404). Общее число устраненных дефектов достигло **218** (осталось **827** | P0: 0, P1: 284, P2: 543).

---

## 🛡️ Что нового в версии 2.1.23 (SemVer Patch Release — SSRF Metadata Shield, Debug Routes Guard, Pickle State Audit, Pip Pinning & Network Hardening)

- **Защита от SSRF и блокировка запросов к link-local метаданным (SSRF Metadata Shield — #308)**:
  - В `sitecustomize.py` (сниппет 35) перехвачен метод `socket.socket.connect`: исходящие сетевые подключения ботов к облачным сервисам метаданных (169.254.x.x link-local) и приватным подсетям RFC 1918 строго контролируются и блокируются с исключением `PermissionError` при отсутствии явного разрешения (`PYBIONIC_ALLOW_LOCAL_CONNECT`). В настройки добавлен реактивный переключатель `ssrfGuardEnabled`.
- **Защита от случайной доступности отладочных маршрутов (Debug Endpoints Exposure Guard — #324)**:
  - В `WebDashboardServer` и `WebAuthGuard` внедрен метод `isDebugRoute(path)`: маршруты отладки и профилирования (`/debug`, `/debug/*`, `/api/debug`, `/api/debug/*`) в релизных сборках немедленно отклоняются с HTTP 404 Not Found и фиксацией в журнале безопасности. В настройки добавлен переключатель `debugEndpointsDisabled`.
- **Аудит и предотвращение десериализации состояния через Pickle (State Restoration Pickle Guard — #335)**:
  - В `sitecustomize.py` (сниппет 36) перехвачен `pickle.load`: при попытке десериализации файлов состояния (`.pkl`, `.pickle`, `.state`) в stderr выводится предупреждение `[PICKLE_GUARD]` с рекомендацией миграции на безопасные форматы JSON или SQLite во избежание риска RCE. В настройки добавлен переключатель `pickleStateGuardEnabled`.
- **Защита от атак подмены зависимостей в pip (Pip Dependency Confusion Guard — #276)**:
  - В `ProjectRepository.sanitizePipArgs` реализована фильтрация аргументов установки пакетов: неавторизованные флаги `--extra-index-url` автоматически вырезаются, и принудительно закрепляется официальный индекс `--index-url https://pypi.org/simple`. В настройки добавлен переключатель `pipDependencyConfusionGuardEnabled`.
- **Ограничение небезопасного динамического исполнения кода (Safe Code Execution Guard — #278)**:
  - В `sitecustomize.py` (сниппет 37) перехвачены вызовы `builtins.eval`, `builtins.exec` и `__import__`: при обнаружении вызовов системных команд (`os.system`, `subprocess`, `__import__`) генерируется предупреждение в stderr `[SAFE_EVAL_GUARD]`. В настройки добавлен переключатель `safeCodeExecutionGuardEnabled`.
- **Автоматическая детекция и замена дефолтных паролей (Weak Password Detection & Mitigation — #295)**:
  - В `ProjectRepository.detectAndMitigateWeakPassword` реализован сканер словарных и дефолтных паролей (`admin`, `1234`, `password`, `root` и т.д.) для ключей `PASSWORD`, `SECRET`, `TOKEN`. При обнаружении дефолтного значения выполняется автоматическая генерация криптографически стойкого 24-значного токена через `SecureRandom`. В настройки добавлен переключатель `weakPasswordDetectionEnabled`.
- **Минимизация отрицательного кэширования DNS (DNS Negative Caching Minimizer — #351)**:
  - В `PyBionicApp` сконфигурировано JVM-свойство `networkaddress.cache.negative.ttl = "5"`, а в `sitecustomize.py` (сниппет 38) введена оптимизация разрешения имен, предотвращающая бесконечное кэширование неудачных DNS-ответов при переключении между Wi-Fi и мобильной сетью. В настройки добавлен переключатель `dnsNegativeCacheTuneEnabled`.
- **Утилизация портов и предотвращение зависания сокетов TCP FIN_WAIT (TCP SO_REUSEADDR Guard — #367)**:
  - В `sitecustomize.py` (сниппет 39) перехвачен конструктор сокетов `socket.socket.__init__`: для потоковых сокетов TCP автоматически устанавливается флаг `SO_REUSEADDR = 1`, ускоряя освобождение сокетов и предотвращая их зависание в состоянии `TIME_WAIT` и `FIN_WAIT_2`. В настройки добавлен переключатель `tcpReuseAddrEnabled`.
- **Защита URL вебхуков от перебора и предсказуемых путей (Webhook Path Brute-Force Guard — #371)**:
  - В `WebDashboardServer` и `WebAuthGuard` внедрен метод `isPredictableWebhookId(id)`: запросы к тривиальным путям (`/webhook/telegram`, `/webhook/bot`, `/webhook/webhook`, `/webhook/api`) немедленно отклоняются с HTTP 403 Forbidden, требуя обязательного использования уникального идентификатора проекта. В настройки добавлен переключатель `strictWebhookPathValidationEnabled`.
- **Предотвращение исчерпания клиентских портов при частых перезапусках (Port Exhaustion Backoff — #380)**:
  - В `RunnerForegroundService` реализована защита от циклического падения: при частых аварийных остановках ботов задержка автоперезапуска увеличивается по экспоненциальному закону (5с -> 15с -> 45с -> 60с), предотвращая исчерпание пула эфемерных портов Linux. В настройки добавлен переключатель `portExhaustionBackoffEnabled`.
- **Модульная архитектура настроек Compose (NetworkAndRuntimeHardeningCard)**:
  - Все новые переключатели безопасности и сетевого тюнинга вынесены в отдельную карточку `NetworkAndRuntimeHardeningCard.kt` с локализацией на все 22 языка, что полностью защищает от переполнения метода байткода JVM (`MethodTooLargeException`).
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#276, #278, #295, #308, #324, #335, #351, #367, #371, #380). Общее число устраненных дефектов достигло **208** (осталось **837** | P0: 0, P1: 294, P2: 543).

---

## 🛡️ Что нового в версии 2.1.22 (SemVer Patch Release — Strict CORS, HTTP Body Ceiling, SecretVault FileLock, XXE Shield & ReDoS Guard)

- **Строгая защита от подстановочных доменов CORS (CORS Wildcard & Safe Preflight — #321)**:
  - В `WebDashboardServer` и `WebAuthGuard` внедрен метод `isAllowedOrigin(origin, hostHeader)` и полноценная обработка HTTP-запросов `OPTIONS`.
  - Запрещено использование подстановочного знака `*` в заголовке `Access-Control-Allow-Origin`. Межсайтовые preflight-запросы от сторонних сайтов немедленно блокируются с кодом HTTP 403 Forbidden, а доверенным клиентам возвращается 204 No Content с точным совпадением origin и заголовком `Vary: Origin`. В настройки добавлен переключатель `strictCorsEnabled`.
- **Строгий лимит входящего тела HTTP-запросов и защита от DoS (Inbound HTTP Body Limiter — #387)**:
  - В `WebDashboardServer` внедрен настраиваемый потолок размера входящего тела HTTP-запросов (`maxHttpBodySizeMb`, по умолчанию 10 МБ).
  - Реализован безопасный парсер `readChunkedBodyCompat` с подсчетом накопленных байт для `Transfer-Encoding: chunked`. Запросы, превышающие лимит, немедленно отклоняются с HTTP 413 Payload Too Large без аллокации памяти. В настройки добавлен переключатель `httpBodyLimitEnabled` и слайдер `maxHttpBodySizeMb`.
- **Периодическая очистка протухших сессий и неактивных лимитов (Session Eviction Cleaner — #408)**:
  - В фоновом цикле обслуживания `inactivityJob` раз в минуту выполняется принудительный вызов `authGuard.pruneExpired(now)` и очистка устаревших записей скользящих лимитов `uploadRateLimits` (старше 5 минут), устраняя утечки ссылок и рост JVM Heap. В настройки добавлен переключатель `sessionEvictionEnabled`.
- **Мгновенное восстановление связи при выходе вкладки из сна (Visibility & Focus Reconnect — #423)**:
  - В `web_dashboard.html` зарегистрированы обработчики событий `document.addEventListener('visibilitychange')`, `window.addEventListener('focus')` и `window.addEventListener('online')`. При возвращении пользователя на заснувшую или неактивную вкладку браузера телеметрия и журналы логов мгновенно обновляются без необходимости перезагрузки страницы.
- **Глобальный таймаут обработки API-запросов сервера (API Request Timeout — #424)**:
  - В `WebDashboardServer` диспетчеризация авторизованных маршрутов API обернута в `withTimeoutOrNull(timeoutSec * 1000L)` с настраиваемым лимитом (`apiRequestTimeoutSeconds`, по умолчанию 30 с). В случае блокировки обработчика клиенту немедленно отдается HTTP 504 Gateway Timeout, предотвращая исчерпание слотов соединений на мобильном устройстве.
- **Межпроцессная блокировка файлов хранилища секретов (SecretVault File Lock — #315)**:
  - В `SecretVault` операции чтения, записи и удаления секретов защищены атомарной блокировкой `FileChannel.lock()` поверх скрытого файла `.lock`. Исключаются состояния гонки (Race Condition) и повреждение зашифрованного хранилища при одновременной записи из нескольких процессов или потоков. В настройки добавлен переключатель `secretVaultFileLockEnabled`.
- **Атомарная замена небезопасной функции mktemp (mktemp Race Condition Guard — #326)**:
  - В `sitecustomize.py` (сниппет 31) вызов `tempfile.mktemp()` перехвачен и заменен на атомарное создание файла через `tempfile.mkstemp()` с закрытыми правами `0o600`, исключая возможность Symlink-атак и перезаписи чужих файлов во временном каталоге. В настройки добавлен переключатель `mktempGuardEnabled`.
- **Принудительное отключение режима отладки в продакшене (Web Server Production Debug Guard — #285)**:
  - В `sitecustomize.py` (сниппет 32) переменные окружения `FLASK_DEBUG` и `DEBUG` принудительно сбрасываются в `0`, а в методе `Flask.run()` аргумент `debug=True` автоматически нейтрализуется с выводом предупреждения в stderr, предотвращая запуск интерактивной консоли Werkzeug с возможностью RCE при возникновении исключений. В настройки добавлен переключатель `productionDebugGuardEnabled`.
- **Защита от атак XML External Entity и Billion Laughs (XXE Shield — #307)**:
  - В `sitecustomize.py` (сниппет 33) парсер `xml.etree.ElementTree.XMLParser` дополнен блокировкой объявлений DTD-сущностей (`EntityDeclHandler`), нейтрализующей атаки чтения локальных файлов и исчерпания памяти при парсинге XML/RSS. В настройки добавлен переключатель `xxeProtectionEnabled`.
- **Защита от катастрофического бэктрекинга регулярных выражений (ReDoS Guard — #327)**:
  - В `sitecustomize.py` (сниппет 34) перехвачена функция `re.compile()` для статического аудита шаблонов регулярных выражений: при обнаружении экспоненциально уязвимых конструкций с вложенными квантификаторами `(a+)+` или `(.*a)*` в лог выводится предупреждение `[REDOS_GUARD]`. В настройки добавлен переключатель `redosGuardEnabled`.
- **Модульная архитектура настроек Compose (AdvancedSecurityGuardsCard)**:
  - Настройки сетевой и системной безопасности вынесены в отдельный независимый компонент `AdvancedSecurityGuardsCard.kt`, обеспечивая строгую модульность и гарантируя отсутствие ошибок переполнения метода байткода JVM (`MethodTooLargeException`).
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#285, #307, #315, #321, #326, #327, #387, #408, #423, #424). Общее число устраненных дефектов достигло **198** (осталось **847** | P0: 0, P1: 304, P2: 543).

---

## 🛡️ Что нового в версии 2.1.21 (SemVer Patch Release — Web Session Hardening, Filename Sanitization, Env Injection Shield & Subprocess LD_PRELOAD Protection)

- **Защита от фиксации сессии при авторизации в веб-панели (Session Fixation Guard — #318)**:
  - При успешной проверке PIN-кода в `/api/auth` и вызове `verifyPinAndIssueToken` ранее выданный сессионный токен клиента (`previousToken`) принудительно аннулируется и удаляется из пула активных сессий перед генерацией нового криптографически стойкого 256-битного токена. В настройки добавлен реактивный переключатель `sessionFixationProtectionEnabled`.
- **Блокировка передачи токенов сессии через параметры URL (?token=xyz) (#300)**:
  - В `WebDashboardServer` и `WebAuthGuard` внедрен фильтр запросов: любые запросы с токенами в строке запроса URL (`query.containsKey("token")`, `auth`, `access_token` и т.д.) немедленно отклоняются с HTTP 400 Bad Request и предупреждением в журнале аудита, предотвращая утечку сессионных токенов через Referer, историю браузера и логи веб-прокси. В настройки добавлен реактивный переключатель `queryTokenRejectionEnabled`.
- **Ограничение скорости и размера загрузки файлов в Web Dashboard (Upload Rate Limiter — #303)**:
  - Внедрен скользящий счетчик загрузок на базе IP-адреса клиента (максимум 60 операций загрузки в минуту).
  - Установлен настраиваемый лимит максимального размера загружаемого файла (`maxFileUploadSizeMb`, по умолчанию 100 МБ) для `POST /api/project/{id}/file` и `POST /api/project/{id}/file/create`, предотвращающий исчерпание памяти устройства (OOM) и DoS-атаки. В настройки добавлен переключатель `uploadRateLimitEnabled` и слайдер `maxFileUploadSizeMb`.
- **Строгая санитизация имен файлов и защита от Path Traversal (Filename Sanitization — #309)**:
  - В `ProjectRepository` добавлены методы `sanitizeFilename` и `validateSafeRelativePath`, блокирующие null-байты (`\0`), управляющие символы ASCII, последовательности перехода по каталогам (`..`), а также зарезервированные имена Windows/POSIX (`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`).
  - Все операции создания, переименования, распаковки zip-архивов проектов защищены от несанкционированной перезаписи системных файлов. В настройки добавлен переключатель `strictFilenameSanitizationEnabled`.
- **Валидация ключей и экранирование значений переменных окружения .env (#310)**:
  - В `ProjectRepository` и `SecretVault` внедрена валидация ключей переменных окружения по стандарту POSIX (`^[A-Za-z_][A-Za-z0-9_]*$`) и блокировка попыток перезаписи опасных системных переменных (`LD_PRELOAD`, `LD_LIBRARY_PATH`, `PYTHONHOME`, `PREFIX`).
  - Реализован метод `escapeEnvValue(value)` для безопасного экранирования кавычек, обратных слэшей и переводов строк (`\n`, `\r`), нейтрализующий атаки инъекции переменных окружения. В настройки добавлен переключатель `strictEnvKeyValidationEnabled`.
- **Защита дочерних процессов от инъекции библиотек через LD_PRELOAD (#293)**:
  - В `sitecustomize.py` (сниппет 28) перехвачены вызовы запуска подпроцессов (`subprocess.Popen`, `os.system`, `os.exec*`). При вызове системных бинарников в каталогах `/system/bin` или `/apex` переменная `LD_PRELOAD` автоматически удаляется из `env`, предотвращая сбои динамического компоновщика Bionic linker (`dlopen failed: library "libtermux-exec.so" not found`). В настройки добавлен переключатель `ldPreloadGuardEnabled`.
- **Безопасные права доступа на Unix Domain сокеты (0600) (#317)**:
  - В `sitecustomize.py` (сниппет 29) перехвачен метод `socket.socket.bind` для сокетов семейства `AF_UNIX`. Сразу после привязки к пути файловой системы на сокет принудительно выставляются права доступа `0o600` (`chmod(path, 0o600)`), запрещая чтение и запись посторонним процессам. В настройки добавлен переключатель `unixSocketGuardEnabled`.
- **Аудит использования небезопасного ГСЧ для генерации секретов (#294)**:
  - В `sitecustomize.py` (сниппет 30) добавлен перехват методов `random.choice`, `random.sample`, `random.choices`. При генерации токенов или ключей длиной более 16 символов модуль выводит предупреждение о необходимости использования модуля `secrets` (`secrets.token_hex` / `secrets.token_urlsafe`).
- **Стойкость идентификаторов сессий и аудит 256-битной энтропии (#272)**:
  - Токены сессий Web Dashboard генерируются исключительно с помощью `java.security.SecureRandom` с длиной 32 байта (256 бит энтропии в шестнадцатеричном представлении `64 hex-символа`), что гарантирует полную защиту от подбора (Session Hijacking).
- **Экранирование HTML в SQLite Viewer (Stored XSS Protection — #297)**:
  - В `SqliteViewerHelper` внедрены методы `escapeHtml(value)` и `renderSafeHtmlTable(result)` с полным экранированием символов `&`, `<`, `>`, `"`, `'`, исключая выполнение вредоносного JavaScript при просмотре таблиц баз данных в веб-интерфейсе.
- **Модуляризация настроек Jetpack Compose (JVM MethodTooLarge Fix)**:
  - Карточка поведения веб-сервера и подсистемы защиты процессов вынесена в отдельный компонент `ServerBehaviorCard.kt` (`ServerBehaviorCard` и `RuntimeSecurityGuardsCard`), что снизило размер `SettingsScreen.kt` с 3700 до 1700 строк и устранило превышение лимита размера байткода Java JVM (64 КБ на метод).
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категории P1 (#272, #293, #294, #297, #300, #303, #309, #310, #317, #318). Общее число устраненных дефектов достигло **188** (осталось **857** | P0: 0, P1: 315, P2: 542).

---

## 🛡️ Что нового в версии 2.1.20 (SemVer Patch Release — Anti-Ptrace Protection, Secure Cookies, WebSocket Hijacking Guard & EXDEV Recovery)

- **Блокировка отладки процессов и дампа памяти через ptrace (`PR_SET_DUMPABLE = 0`) (#281)**:
  - В `sitecustomize.py` внедрен системный вызов `prctl(PR_SET_DUMPABLE, 0)` через ctypes при запуске воркера.
  - Предотвращает присоединение отладчиков (`ptrace(PTRACE_ATTACH)`), перехват системных вызовов и дамп оперативной памяти процессов ботов с токенами и ключами соседними приложениями того же UID. В настройки добавлен реактивный переключатель `antiPtraceEnabled`.
- **Строгая безопасность сессионных Cookie веб-панели управления (#273)**:
  - При авторизации в веб-панели (`/api/login`) выдается защищенная cookie `pybionic_session` с обязательными флагами `HttpOnly; SameSite=Strict; Path=/; Max-Age=...`.
  - При выходе (`/api/logout`) cookie немедленно аннулируется с `Max-Age=0`. Защищает сессии от кражи через XSS и межсайтовых запросов CSRF. В настройки добавлен переключатель `secureCookiesEnabled`.
- **Защита от атак межсайтового захвата WebSocket и терминала (Cross-Site WebSocket Hijacking — #289)**:
  - В `WebAuthGuard` и `WebDashboardServer` внедрена строгая валидация заголовка `Origin` при WebSocket-рукопожатиях (`Upgrade: websocket`).
  - Попытки сторонних вредоносных сайтов, открытых в браузере пользователя, несанкционированно подключиться к локальному сокету веб-терминала или потоку логов немедленно блокируются с кодом 403 Forbidden. В настройки добавлен переключатель `wsOriginCheckEnabled`.
- **Защита от SQL-инъекций и строгая валидация идентификаторов таблиц в SQLite Viewer (#274)**:
  - В `SqliteViewerHelper` реализован метод `validateTableIdentifier(tableName)` с регулярным выражением `^[A-Za-z0-9_.\-]+$`.
  - Все операции запроса данных, выгрузки DDL и экспорта в CSV/JSON защищены от внедрения вредоносных спецсимволов и внедрения SQL-конструкций.
- **Изоляция каталога временных файлов от общесистемного /data/local/tmp (#282)**:
  - Для каталога `$PREFIX/tmp` выставлены строгие закрытые права 0700 (`setReadable/Writable/Executable(true, true)`), запрещающие доступ процессам других пользователей.
  - В `sitecustomize.py` модуль `tempfile.tempdir` принудительно привязан к локальному защищенному `$TMPDIR`, исключая случайный откат стандартной библиотеки Python к общедоступной директории `/data/local/tmp`.
- **Автоматическое восстановление перемещения файлов между файловыми системами (EXDEV Guard — #134)**:
  - В `sitecustomize.py` перехвачены вызовы `os.rename` и `os.replace`. При возникновении ошибки ядра Linux `OSError: [Errno 18] Invalid cross-device link` (попытка перемещения между внутренней памятью, SD-картой или USB OTG) интерпретатор автоматически выполняет безопасное копирование с последующим удалением источника (`copy2/copytree + unlink/rmtree`). В настройки добавлен переключатель `exdevGuardEnabled`.
- **Защита от выполнения кода через скрипты конфигурации путей .pth (#159)**:
  - В `sitecustomize.py` и `SecretLeakScanner` добавлено сканирование файлов `.pth` на наличие внедренных исполняемых строк (`import ...`). При обнаружении выводится предупреждение `[PTH_GUARD]`, а статический сканер секретов помечает такие файлы как `PTH_CODE_INJECTION`. В настройки добавлен переключатель `pthGuardEnabled`.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **9 дефектов** категории P1 (#134, #140, #159, #273, #274, #281, #282, #283, #289). Общее число устраненных дефектов достигло **178** (осталось **867** | P0: 0, P1: 324, P2: 543).

---

## 🛡️ Что нового в версии 2.1.19 (SemVer Patch Release — Dynamic Multi-Language i18n & Zero Hardcoded Strings)

- **Реактивное переключение языков без перезапуска приложения (Dynamic Locale Recomposition)**:
  - В `MainActivity.kt` внедрены `CompositionLocalProvider` с явным провайдингом `LocalContext provides localizedContext`, `LocalConfiguration provides localizedConfig` и `LocalLayoutDirection provides layoutDirection`. При изменении настройки языка в `SettingsScreen` все экраны Compose мгновенно рекомпозируются на выбранном языке интерфейса без необходимости перезапуска активности.
  - В `PyBionicApp.kt` реализован оверрайд `attachBaseContext(base: Context)` с оборачиванием `LocaleHelper.wrap(base)`, а также добавлен статический синглтон-контекст `PyBionicApp.getLocalizedContext()`, гарантирующий доступ к актуальной локали для всех фоновых сервисов, репозиториев и утилит.
  - В `LocaleHelper.kt` метод `applyLocale` дополнен явной синхронизацией конфигурации дисплея и локали приложения (`applicationContext.resources.updateConfiguration`), устраняя застревание фоновых синглтонов в дефолтной системной локали.
  - В `PyBionicViewModel.kt` в метод `setLanguageTag` добавлен немедленный вызов `LocaleHelper.applyLocale(getApplication(), tag)`.
- **Полное устранение хардкоденных строк во всех слоях приложения**:
  - В `SqliteBrowserDialog.kt` все 8 системных сообщений Toast (`sqlite_error_fmt`, `sqlite_integrity_error_fmt`, `sqlite_backup_error_fmt`, `sqlite_ddl_error_fmt`, `sqlite_csv_copied_fmt`, `sqlite_json_copied_fmt`, `sqlite_export_error_fmt`), а также плейсхолдер ввода SQL (`sqlite_query_placeholder`) переведены на строковые ресурсы `R.string.*`.
  - В `BotHubScreen.kt` текстовая метка URL каталога GitHub заменена на ресурс `R.string.bothub_github_catalog_url_label`.
  - В `ProjectDetailScreen.kt` метки кнопок и заголовки («Git Pull», «GitOps & Deploy») переведены на строковые ресурсы `R.string.git_pull` и `R.string.gitops_deploy_title`.
  - В `TelemetrySheets.kt` заголовок приоритета OOM заменен на `R.string.oom_score_adj_title`.
  - В `ProjectRepository.kt` системные сообщения об ошибках («Rename failed», «Failed to create folder», «Python runtime is not installed», «Project not found», «pip freeze timed out», «pip freeze failed with code...», логи деплоя и отката) заменены на вызовы `context.getString(R.string.*)`.
  - В `PipErrorAdvisor.kt` русскоязычный хардкод заменен на вызовы локализованного контекста с нейтральным English-фоллбэком для pure-JVM тестов.
- **100% паритет всех 22 поддерживаемых языковых локалей**:
  - С помощью скрипта `tools/sync_strings.py` все 20 новых строковых ключей автоматически синхронизированы по всем 22 директориям локализации (`values-*/strings.xml`).

---

## 🛡️ Что нового в версии 2.1.18 (SemVer Patch Release — TCP Fast Open, tracemalloc, Git Credential Vault & Strict Sandbox Permissions)

- **Безопасная обработка паузы SIGSTOP и возобновления SIGCONT без ложных срабатываний сторожевых таймеров (#24)**:
  - В модель рабочего процесса `ManagedWorker` добавлен флаг `isPaused`.
  - Добавлены команды управления `ACTION_PAUSE_PROJECT` и `ACTION_RESUME_PROJECT`, а также статические методы `RunnerForegroundService.pause()` и `RunnerForegroundService.resume()`.
  - При отправке сигнала `SIGSTOP (19)` процесс замораживается, а системные сторожевые таймеры запуска (`startupWatchdogJob`) и циклов нагрузки CPU (`metricsJob`) автоматически переходят в режим ожидания, исключая ложное прибивание бота как "зависшего". При отправке `SIGCONT (18)` таймеры снова активируются.
- **Ускорение сетевых рукопожатий через TCP Fast Open (TFO — #119)**:
  - В `sitecustomize.py` внедрен автоматический перехват исходящих потоковых сокетов: при подключении на сокетах выставляется флаг `TCP_FASTOPEN_CONNECT (30)` (`setsockopt(socket.IPPROTO_TCP, 30, 1)`).
  - Устраняется 1 RTT (round-trip time) при установлении TCP/TLS-соединений с серверами Telegram Bot API на сотовых сетях Android. Добавлен реактивный переключатель `tcpFastOpenEnabled` в настройках приложения.
- **Предотвращение сбоев сборки pip-колес из-за длинных путей на внешних накопителях (#120)**:
  - Переменная `PIP_BUILD_TRACKER` принудительно перенаправлена во внутреннюю защищенную память устройства (`$PREFIX/tmp/pip-build-tracker`), исключая ошибки `OSError: [Errno 36] File name too long` при сборке пакетов C/C++ на файловых системах FAT32/exFAT.
- **Встроенный профилировщик аллокаций памяти Python tracemalloc (#123)**:
  - В `sitecustomize.py` интегрирован запуск `tracemalloc.start(25)` при выставлении флага `PYBIONIC_TRACEMALLOC=1`.
  - Позволяет профилировать и выявлять утечки оперативной памяти и циклические ссылки в фоновых ботах без ручного изменения исходного кода проекта. Добавлен переключатель `tracemallocEnabled` в настройках.
- **Диагностика режима энергосбережения и ограничений фонового трафика Android (#184, #191, #193)**:
  - Реализован динамический `BroadcastReceiver` для отслеживания изменения состояния `PowerManager.ACTION_POWER_SAVE_MODE_CHANGED` (с флагом `RECEIVER_NOT_EXPORTED` для Android 13+).
  - При включении режима энергосбережения Android (`#184`, `#191`) или режима экономии трафика (`ConnectivityManager.RESTRICT_BACKGROUND_STATUS_ENABLED`, `#193`) в системные логи бота выводится предупреждение о возможном троттлинге фонового процессора и задержках сетевых пакетов. В настройки добавлен переключатель `batterySaverWarningEnabled`.
- **Защита веб-панели управления от перебора PIN-кода (Brute-Force Rate Limiting — #266)**:
  - Верифицирована и протестирована подсистема pure-JVM защиты в `WebAuthGuard`: ограничение 5 неверных попыток ввода PIN с блокировкой IP-адреса на 5 минут, сравнение через константное время `MessageDigest.isEqual` против timing-атак, криптографические 256-битные Bearer-токены сессий с TTL и строгая валидация Host/Origin против CSRF и DNS Rebinding.
- **Принудительные строгие права доступа песочницы к файлам проектов и секретам (#268)**:
  - Реализован механизм `enforceStrictFilePermissions(dir)`: директории проектов изолируются с правами 0700 (чтение, запись и исполнение только владельцем), а конфигурационные файлы секретов (`.env`, `.secrets`, `.key`, `.pem`, `.token`) — с правами 0600. В настройки добавлен переключатель `strictFilePermissionsEnabled`.
- **Санитайзер учетных данных Git и защита токенов в .git/config (#269)**:
  - Реализован метод `sanitizeGitCredentials(rawUrl)`, автоматически вырезающий персональные токены доступа (PAT) и пароли из URL клонирования (`https://user:token@github.com/...` -> `https://github.com/...`).
  - Учетные данные сохраняются исключительно в защищенном хранилище `SecretVault` и динамически передаются через временный скрипт `GIT_ASKPASS`, а локальный файл `.git/config` очищается от открытых токенов, исключая случайную утечку при экспорте бэкапов.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **10 дефектов** категорий P1/P2 (#24, #119, #120, #123, #184, #191, #193, #266, #268, #269). Общее число устраненных дефектов достигло **169** (осталось **876** | P0: 0, P1: 334, P2: 542).

---

## 🛡️ Что нового в версии 2.1.17 (SemVer Patch Release — SQLite WAL & Integrity, atexit Deadlock Guard, Synthetic /etc/hosts & Pip Fast Timeout)

- **Синтетический /etc/hosts и перехватчик локального разрешения доменов (#51)**:
  - В префиксе среды `$PREFIX/etc/hosts` автоматически генерируется файл локального сопоставления с записями `127.0.0.1 localhost loopback` и `::1 localhost ip6-localhost ip6-loopback`.
  - В системный загрузчик `sitecustomize.py` интегрирован перехват вызова `socket.getaddrinfo`, считывающий `$PREFIX/etc/hosts` и локальный файл проекта `$PROJECT_DIR/hosts`. Локальные тестовые домены (`my-bot.local`, `internal.api`) мгновенно разрешаются на Android без необходимости модификации системного `/system/etc/hosts` и без Root-прав. В настройки добавлен переключатель `syntheticHostsEnabled`.
- **Защита от взаимных блокировок в обработчиках завершения (atexit Deadlock Guard — #52)**:
  - Перехвачен внутренний запуск процедур завершения интерпретатора `atexit._run_exitfuncs()`. В момент старта процедуры остановки инициируется независимый сторожевой поток с 5-секундным дедлайном.
  - Если пользовательский скрипт зависает в синхронном HTTP-запросе или на блокировке сокета внутри `atexit`, процесс принудительно завершается через `os._exit(0)` с выводом `[ATEXIT_DEADLOCK_GUARD]`, предотвращая ожидание жесткого убийства по таймауту. В настройки добавлен переключатель `atexitDeadlockGuardEnabled`.
- **Грациозная остановка рабочих потоков при SIGINT (#55)**:
  - В обработчик сигнала `SIGINT` внедрена автоматическая конвертация активных фоновых потоков `threading.Thread` в состояние `daemon = True`. При нажатии кнопки остановки процесс Python не блокируется вечными не-демоническими циклами воркеров.
- **Оптимальные производственные параметры SQLite по умолчанию: WAL, Busy Timeout, Foreign Keys & load_extension (#106, #669, #681, #714)**:
  - В `sitecustomize.py` перехвачена функция `sqlite3.connect()`, автоматически активирующая:
    - `PRAGMA journal_mode=WAL;` и `PRAGMA synchronous=NORMAL;` (#669) — раздельные читатели и писатели без блокировок `database is locked`.
    - `PRAGMA busy_timeout = 5000;` (#681) — 5-секундное ожидание освобождения транзакции вместо мгновенного падения.
    - `PRAGMA foreign_keys = ON;` (#714) — принудительный контроль ссылочной целостности внешних ключей.
    - `conn.enable_load_extension(True)` (#106) — разблокировка загрузки динамических расширений SQLite (FTS5, sqlite-vec, SpatiaLite).
  - В настройки добавлен переключатель `sqliteWalEnforcerEnabled`.
- **Утилита проверки целостности и спасения поврежденных баз данных (SQLite Integrity & Recovery — #674)**:
  - В `SqliteViewerHelper` добавлен метод `checkIntegrity(context, dbFile)` для быстрого аудита базы через `PRAGMA integrity_check(100)`.
  - Добавлен метод аварийного восстановления `recoverDatabase(context, dbFile, outputFile)`, спасающий уцелевшие таблицы и строки даже при частичном повреждении заголовков страниц и B-Tree деревьев.
  - В диалоге `SqliteBrowserDialog` появилась кнопка «Integrity Check» для оперативной проверки базы в один клик.
- **Горячее онлайн-резервное копирование баз данных (SQLite Hot Online Backup — #675)**:
  - В `SqliteViewerHelper` реализован метод `createHotBackup(context, sourceDb, targetBackupFile)` на базе атомарного SQLite `VACUUM INTO` с дефрагментацией страниц на лету без остановки и блокировки работающего бота.
  - В диалог просмотра базы добавлена кнопка «Hot Backup», создающая мгновенный снимок базы с отметкой времени.
- **Инспектор DDL-схем таблиц (CREATE TABLE Schema DDL Inspector — #711)**:
  - В `SqliteViewerHelper` и `SqliteBrowserDialog` добавлен метод `getTableDdl` и кнопка «Schema DDL», отображающая точный SQL-код создания выбранной таблицы или представления (VIEW) из системной таблицы `sqlite_master`.
- **Предотвращение зависания pip при IPv6 в сотовых сетях (Pip Fast Timeout — #105)**:
  - В `$PREFIX/etc/pip.conf` и переменные окружения процесса добавлен глобальный таймаут сокета `PIP_DEFAULT_TIMEOUT=15` и быстрые повторы, предотвращающие 120-секундное зависание установки пакетов на мобильных операторах с некорректной маршрутизацией IPv6. В настройки добавлен переключатель `pipFastTimeoutEnabled`.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **9 ключевых дефектов** категорий P1/P2 (#51, #52, #55, #105, #106, #669, #674, #675, #711, #714). Общее число устраненных дефектов достигло **156** (осталось **889** | P0: 0, P1: 343, P2: 546).

---

## 🛡️ Что нового в версии 2.1.16 (SemVer Patch Release — POSIX Signal Decoder, Gzip Compression, Per-PID Traffic & Sandbox Isolation)

- **Декодер POSIX-сигналов и расширенная диагностика завершения процессов (#27)**:
  - Создан специализированный модуль `PosixSignalDecoder`, преобразующий коды завершения (`exitCode > 128`) в точные наименования POSIX-сигналов (`SIGSEGV`, `SIGKILL`, `SIGABRT`, `SIGFPE`, `SIGBUS`, `SIGTERM`, `SIGHUP`) с детальным описанием первопричины сбоя.
  - В терминал и аудит крашей выводится информативное сообщение `[EXIT_DIAGNOSTICS]`, позволяющее мгновенно отличить системный сброс памяти Android LMK (SIGKILL) от падения нативного C/C++ расширения (SIGSEGV).
- **Синтетическая база пользователей /etc/passwd и шим-модуль pwd/getlogin (#14)**:
  - В префиксе среды `$PREFIX/etc` автоматически создаются файлы `passwd`, `group` и `nsswitch.conf`, содержащие реальный Android UID приложения и домашнюю директорию.
  - В `sitecustomize.py` добавлен защитный перехватчик для функций `pwd.getpwuid()`, `pwd.getpwnam()` и `os.getlogin()`, предотвращающий исключения `KeyError` и падения скриптов, ориентированных на стандартные Unix-системы.
- **Прямой запуск шелл-скриптов и автоматическое определение шебангов (#20)**:
  - Реализован автоматический анализ точки входа проекта: файлы `.sh` и скрипты с шебангами `#!/bin/sh` или `#!/bin/bash` запускаются напрямую через `/system/bin/sh`.
  - В `$PREFIX/bin` созданы системные символические ссылки `python -> python3` и `sh -> /system/bin/sh`.
- **Защита от сбоев расширенных атрибутов файлов xattr (#28)**:
  - В системный загрузчик `sitecustomize.py` интегрирован перехват вызовов `os.setxattr()`, `os.getxattr()` и `os.listxattr()`, безопасно подавляющий ошибки `EOPNOTSUPP` и `ENOTSUP` на файловых системах Android FUSE и FAT/SDCard при резервном копировании и упаковке проектов.
- **Сторож файловых дескрипторов inotify (Inotify Watch Exhaustion Guard — #29)**:
  - Внедрена автоматическая фильтрация служебных каталогов (`.git`, `__pycache__`, `venv`, `node_modules`, `.cache`) при регистрации наблюдателей файловой системы в библиотеке `watchdog` и uvicorn `--reload`.
  - Предотвращено исчерпание системного лимита ядра `/proc/sys/fs/inotify/max_user_watches` (8192). В настройки добавлен переключатель `inotifyGuardEnabled`.
- **Групповая остановка процессов и ликвидация осиротевших оболочек (#44)**:
  - Метод `ProcessTreeKiller.sendProcessGroupSignalSafe` усилен прямой отправкой сигналов процессу-группе (`android.system.Os.kill(-targetGrp, sig)`), гарантируя полное уничтожение как родительских шелл-оберток (`sh -c`), так и вложенных процессов воркеров.
- **Попроцессный учет сетевого трафика (Network Accounting per PID — #46)**:
  - В `TrafficStatsHelper` реализован парсинг сетевых счетчиков `/proc/[pid]/net/dev` (`readProcessNetDevBytes()`), накапливающий переданный объем данных (RX/TX) индивидуально по каждому активному проекту.
- **Строгая песочница PATH ($PREFIX/bin — #60)**:
  - В настройки добавлен переключатель `strictPathIsolationEnabled`: при его активации из системного `PATH` исключаются каталоги `/system/bin` и `/system/xbin`, блокируя вызовы произвольных системных утилит Android из кода бота.
- **Проверка энтропии генератора случайных чисел (#65)**:
  - Добавлена превентивная валидация доступности энтропии из источника `/dev/urandom` перед стартом процессов и в `sitecustomize.py`, предотвращающая деградацию и зависание криптографических библиотек.
- **Лимит порождения дочерних процессов на бота (#67)**:
  - В фоновый мониторинг `metricsJob` добавлен контроль глубины дерева процессов: при превышении лимита (по умолчанию 16, настраивается в `AppPreferences`) избыточные дочерние процессы автоматически утилизируются сигналом SIGKILL с фиксацией `[PROCESS_LIMIT_EXCEEDED]`.
- **Защита от утечки WakeLock при аварийных сбоях (#195)**:
  - Захват `WakeLock` переведен на безопасный 15-минутный таймаут (`WAKELOCK_TIMEOUT_MS = 900_000L`) с автоматическим продлением при активных воркерах. При внезапном краше службы блокировка процессора сбрасывается операционной системой автоматически.
- **Усиление Content-Security-Policy (CSP) в веб-панели (#263)**:
  - Все HTTP-ответы встроенного сервера, включая chunked-трансляции логов и экспорты, теперь строго содержат заголовок `Content-Security-Policy` с политикой `frame-ancestors 'none'` и `connect-src 'self'`.
- **Защита веб-сервера от Slowloris HTTP-атак (#346)**:
  - Внедрен строгий 5-секундный таймаут чтения заголовков (`sock.soTimeout = 5000`) и 10-секундный общий лимит на чтение запроса, полностью блокирующий медленные атаки исчерпания потоков.
- **Gzip-сжатие статики и HTML в веб-панели (#347)**:
  - Реализовано сжатие ответов через `GZIPOutputStream` при наличии заголовка `Accept-Encoding: gzip` со стороны браузера. Размер интерфейса `web_dashboard.html` сокращен на 78%, обеспечивая мгновенную загрузку в мобильных сетях. Добавлен переключатель `webGzipEnabled`.
- **Динамический подбор портов при конфликтах (#348)**:
  - При занятости порта 8080 веб-сервер последовательно сканирует порты 8081..8090 и динамически привязывается к первому свободному сокету с фиксацией аудита `[PORT_FALLBACK]`.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **16 дефектов** категорий P1/P2 (#14, #20, #27, #28, #29, #44, #46, #60, #65, #67, #182, #195, #263, #346, #347, #348). Общее число устраненных дефектов достигло **147** (осталось **898** | P0: 0, P1: 349, P2: 549).

---

## 🛡️ Что нового в версии 2.1.15 (SemVer Patch Release — Memory Limiting, Mobile CGNAT Keepalive & Thermal Throttling)

- **Аппаратное ограничение виртуальной памяти процесса через RLIMIT_AS (#18)**:
  - В системный загрузчик `sitecustomize.py` внедрена установка лимита адресного пространства процесса `resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))` на основе переменной `PYBIONIC_RLIMIT_AS_MB`.
  - При превышении порога памяти воркер получает контролируемый `MemoryError` внутри Python вместо внезапного убийства всего приложения PyBionic системным демоном Android LowMemoryKiller (LMK).
- **Грациозная отмена асинхронных задач asyncio при SIGTERM (#70)**:
  - В `sitecustomize.py` зарегистрирован обработчик сигнала SIGTERM, который через `asyncio.all_tasks(loop)` отменяет все активные корутины (`task.cancel()`) и запускает цикл событий до их завершения, позволяя блокам `finally:` корректно закрыть сессии aiohttp, сокеты и соединения с базой данных.
- **Тюнинг сборщика мусора Python для снижения микрофризов (GC Tuning — #102)**:
  - Добавлена оптимизация порогов сборщика мусора `gc.set_threshold(50000, 10, 10)` при установленном флаге `PYBIONIC_GC_TUNE=1`. Это снижает частоту промежуточных пауз GC во время интенсивного парсинга JSON и сетевого ввода-вывода. В настройки добавлен реактивный переключатель `gcTuningEnabled`.
- **Агрессивный TCP Keepalive для сотовых сетей и мобильного CGNAT (#178)**:
  - В `sitecustomize.py` перехвачена инициализация `socket.socket`, автоматически активирующая `SO_KEEPALIVE` с интервалами `TCP_KEEPIDLE = 60`, `TCP_KEEPINTVL = 15`, `TCP_KEEPCNT = 4`. Это предотвращает молчаливый сброс сессий ботов сотовыми операторами (NAT timeout) без пробуждения процессора. В настройки добавлен переключатель `tcpKeepaliveTuneEnabled`.
- **Проактивная очистка кэшей и буферов при нехватке памяти (onTrimMemory — #194)**:
  - В `RunnerForegroundService` реализован обработчик `onTrimMemory(level)`: при получении сигналов `TRIM_MEMORY_RUNNING_LOW` или критических уровней память оперативно освобождается через сжатие кольцевых буферов логов `RuntimeBus.trimMemoryCaches(keepLines = 100)` и запуск `System.gc()`.
- **Защита постоянного уведомления службы от свайпа на Android 14+ (#200)**:
  - Для постоянного уведомления `RunnerForegroundService` установлен флаг `setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)` и подтвержден статус `setOngoing(true)`, предотвращая случайное смахивание уведомления пользователем на Android 14 (API 34) и Android 15 (API 35).
- **Детектирование холостых циклов процессора по переключениям контекста (Spin-Loop Guard — #56)**:
  - В `RunnerForegroundService` реализован мониторинг частоты недобровольных переключений контекста `nonvoluntary_ctxt_switches` через `/proc/[pid]/status`. При превышении порога в 10 000 переключений/сек регистрируется предупреждение `[PERF_WARNING: High CPU context switching]` о наличии бесконечного busy-wait цикла.
- **Сторожевой таймер первичного вывода процесса (Startup Watchdog — #71)**:
  - Внедрена корутина `startupWatchdogJob`, отслеживающая появление первого вывода в `stdout`/`stderr` в течение первых 60 секунд после запуска. При отсутствии вывода в лог выдается предупреждение `[STARTUP_WATCHDOG]`, помогающее диагностировать зависшие импорты.
- **Адаптивное термодросселирование и приоритет процессов (#181)**:
  - При перегреве аккумулятора (`BATTERY_HEALTH_OVERHEAT`) и включенной опции термодросселирования приоритет процесса воркера автоматически понижается до фонового (`Process.THREAD_PRIORITY_BACKGROUND`, `nice +10`), снижая нагрев кристалла CPU. В настройки добавлен переключатель `thermalThrottlingEnabled`.
- **Стандартизация системных переменных окружения Python (#98, #99)**:
  - Зафиксирован экспорт переменных `PYTHONHOME`, `PYTHONIOENCODING=utf-8`, `LANG=C.UTF-8` и `LC_ALL=C.UTF-8`, предотвращающий искажение Unicode-символов при логировании и исключающий коллизии системных путей стандартной библиотеки.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **11 дефектов** категории P1/P2 (#18, #56, #70, #71, #98, #99, #102, #178, #181, #194, #200). Общее число устраненных дефектов достигло **131** (осталось **914** | P0: 0, P1: 357, P2: 557).

---

## 🛡️ Что нового в версии 2.1.14 (SemVer Patch Release — System Shutdown Interception, PID Registry & Socket Collision Guard)

- **Грациозная остановка ботов при выключении и перезагрузке устройства (#219)**:
  - Создан `ShutdownReceiver`, зарегистрированный на системные события `ACTION_SHUTDOWN` и `QUICKBOOT_POWEROFF`.
  - В `RunnerForegroundService` реализован метод `handleDeviceShutdown()`, отправляющий сигнал SIGTERM воркерам и сбрасывающий WAL-журналы SQLite без очистки персистентного списка `desired_running`, обеспечивая автоматическое продолжение работы ботов после включения устройства.
- **Персистентный реестр PID и очистка осиротевших процессов (#62)**:
  - Реализован механизм атомарного сохранения активных PID воркеров на диск в `active_workers_state.json`.
  - При запуске службы метод `cleanupOrphanedPidsFromPreviousCrash()` сканирует `/proc/[pid]/cmdline`, обнаруживает и утилизирует процессы Python/PyBionic, оставшиеся в случае внезапного падения приложения или выгрузки памяти ОС Android.
- **Предотвращение гонки TCP-портов при быстром перезапуске (Fast Restart Port Race — #69)**:
  - Внедрена корутина активного ожидания `awaitPortRelease(port)` с флагом `SO_REUSEADDR` перед запуском процесса (таймаут 3000 мс, опрос каждые 150 мс), полностью исключающая сбои `OSError: [Errno 98] Address already in use`.
- **Защита от повреждения кэша байткода .pyc (Bytecode Corruption Guard — #54)**:
  - Реализован сторож `cleanBytecodeCache()`: при обнаружении ошибок `bad magic number` или `bad marshal data` поврежденные каталоги `__pycache__` и файлы `*.pyc` автоматически очищаются перед повторным запуском. Добавлен переключатель `pycCorruptionGuardEnabled` в настройки.
- **Нормализация символических ссылок в PYTHONPATH (Symlink Realpath — #48)**:
  - В `BionicPaths.buildEnv()` пути к каталогу проекта и системным библиотекам `site-packages` разрешаются через канонический путь (`canonicalFile`), исключая циклический поиск и дублирование загрузки модулей.
- **Автоматическое расширение лимита открытых файловых дескрипторов (RLIMIT_NOFILE — #53)**:
  - В системный перехватчик `sitecustomize.py` добавлено повышение мягкого лимита `RLIMIT_NOFILE` до системного максимума через `resource.setrlimit()`. В настройки добавлен переключатель `expandNofileEnabled`.
- **Интеллектуальный поиск нативных библиотек ctypes в Android Bionic (#91)**:
  - Перехвачен `ctypes.util.find_library()` с расширенным сканированием `$PREFIX/lib`, `/system/lib64`, `/apex/com.android.runtime/lib64` и `/system/lib`, восстанавливая работоспособность библиотек SoundFile, CFFI и криптографии.
- **Кроссплатформенный шим для Windows asyncio Policy (#101)**:
  - В `sitecustomize.py` добавлены шимы `WindowsSelectorEventLoopPolicy` и `WindowsProactorEventLoopPolicy`, исключающие падения при переносе кода с Windows на Android.
- **Экспорт часового пояса Android $TZ (#63)**:
  - В окружение каждого процесса экспортируется системный часовой пояс Android (`TimeZone.getDefault().id`), обеспечивая корректное вычисление локального времени в `time.tzset()` и `datetime`.
- **Персистентность сетевых мониторов и восстановление состояния (#215, #218, #50)**:
  - Гарантировано освобождение сетевых колбэков в `onDestroy()`, устранение парсинга `/proc/[pid]/stat` с пробелами, и надежный автозапуск проектов при получении `intent == null` в `START_STICKY`.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **12 дефектов** категории P1/P2 (#48, #50, #53, #54, #62, #63, #69, #91, #101, #215, #218, #219). Общее число устраненных дефектов достигло **120** (осталось **925** | P0: 0, P1: 365, P2: 560).

---

## 🛡️ Что нового в версии 2.1.13 (SemVer Patch Release — P1 High-Priority Kernel & Process Lifecycle Enhancements)

- **Ликвидация утечек файловых дескрипторов процессов (FD_CLOEXEC & Stream Closure — #3)**:
  - В `RunnerForegroundService` при завершении или перезапуске процесса теперь принудительно и гарантированно закрываются все три стандартных системных пайпа процесса (`inputStream`, `errorStream`, `outputStream`). Это исключает накопление открытых дескрипторов в таблице ядра Linux и предотвращает исчерпание системных лимитов FD.
- **Автоматический сбор и утилизация процессов-зомби (<defunct> Child Process Reaping — #15)**:
  - В `ProcessTreeKiller` реализован метод `reapZombieChildren()`, вызывающий системный вызов `waitpid(-1, status, WNOHANG)` в цикле при завершении дочерних воркеров. Зависшие записи завершившихся дочерних процессов мгновенно утилизируются из таблицы процессов ядра.
- **Неблокирующее ожидание завершения процессов без блокировки пула диспетчера (#30)**:
  - В `RunnerForegroundService.executeSingleRun()` блокирующий вызов `process.waitFor()` заменен на кооперативную корутину `awaitProcessExit(process)`. Корутина проверяет статус процесса через неблокирующий `process.isAlive` с интервалом `delay(200L)`, не удерживая выделенный системный поток в пуле `Dispatchers.IO` на время выполнения долгих фоновых демонов.
- **Адаптивный таймаут корректного завершения до 30 секунд и предотвращение зависания в состоянии State 'D' (#10, #35)**:
  - В `ProcessTreeKiller` диапазон настраиваемого времени грациозной остановки расширен до 30 секунд (`100L..30_000L`), а в `SettingsScreen` добавлен выбор 30s в селекторе чипов.
  - Ожидание переведено на адаптивный опрос (100 мс), благодаря чему быстро завершающиеся процессы освобождают ресурсы немедленно.
  - Внедрена проверка состояния процесса State 'D' (Uninterruptible Sleep / блокировка ввода-вывода диска/сокета): при попадании процесса в системную блокировку ввода-вывода процесс не вызывает бесконечный hang интерфейса приложения.
- **Синтетический DNS /etc/resolv.conf для нативных C-библиотек (#13)**:
  - В `BionicPaths` реализована функция `ensureResolvConf()`, генерирующая системно-совместимый файл `usr/etc/resolv.conf` с актуальными DNS-серверами Android из `ConnectivityManager.getLinkProperties()` (с надежным резервным пулом 8.8.8.8, 1.1.1.1).
  - В среду выполнения экспортируются переменные `RESOLV_CONF`, `ARES_OPTIONS` и `LOCALDOMAIN`, что обеспечивает безошибочную работу C-расширений (`c-ares`, `aiodns`, `dnspython`). В настройки добавлен переключатель `syntheticDnsEnabled`.
- **Защита часов asyncio от отставания во время глубокого сна Android Doze Mode (CLOCK_BOOTTIME — #26)**:
  - В системном перехватчике `sitecustomize.py` внедрена синхронизация `time.monotonic` и `time.monotonic_ns` с системным таймером ядра `CLOCK_BOOTTIME`. В отличие от стандартного `CLOCK_MONOTONIC`, он продолжает отсчет времени во время нахождения смартфона в режиме глубокого энергосбережения Doze, предотвращая многочасовое запаздывание таймеров и очередей в `asyncio`.
  - Добавлен реактивный переключатель `boottimeClockEnabled` в `SettingsScreen` (согласно Правилу 5).
- **Автоматическая очистка зависших Unix domain sockets, PID-файлов и сегментов /dev/shm (#40, #41)**:
  - Перед запуском каждого проекта в `RunnerForegroundService` выполняется автоматическая очистка остаточных `.sock`, `.pid` и `.lock` файлов, оставшихся после аварийных завершений, исключая ошибки `Address already in use` (EADDRINUSE).
  - Также сканируются и очищаются осиротевшие сегменты POSIX разделяемой памяти `/dev/shm` текущего UID приложения.
  - Добавлен пользовательский переключатель `staleSocketsCleanupEnabled` в настройках.
- **Контроль дисковой квоты логов и цветовая разметка терминала (#37, #43)**:
  - Подтверждена надежность кольцевой ротации лог-файлов `.pybionic.log` (до 4 МБ с бэкапом `.pybionic.log.1`).
  - Экспортированы переменные окружения `TERM=xterm-256color` и `CLICOLOR_FORCE=1` для поддержки ANSI-стилей в консоли.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **11 дефектов** категории P1/P2 (#3, #10, #13, #15, #26, #30, #35, #37, #40, #41, #43). Общее число устраненных дефектов достигло **108** (осталось **937**).

---

## 🛡️ Что нового в версии 2.1.12 (SemVer Patch Release — Финальное устранение всех P0-дефектов: PEP 668, Direct Boot, Sandbox 0700 & SQLCipher Guard)

- **Полное устранение ВСЕХ критических дефектов категории P0 в реестре дефектов (0 P0 REMAINING)**:
  - В этой версии устранены последние 12 дефектов высшего приоритета P0, обеспечив 100% ликвидацию всех критических уязвимостей и архитектурных рисков!
- **Защита стандартной библиотеки Python от разрушения pip (PEP 668 EXTERNALLY-MANAGED — #582)**:
  - В `BionicPaths` реализовано автоматическое создание маркера `usr/lib/python3.14/EXTERNALLY-MANAGED`. Это исключает случайную перезапись системных модулей Python (`email`, `token`, `queue`, `json`, `os`) при установке пакетов без venv, предотвращая повреждение rootfs.
- **Изоляция каталогов проектов на уровне прав ядра Linux 0700 (Sandbox UID Isolation — #256)**:
  - В `ProjectRepository.projectDir()` каждый рабочий каталог проекта создается со строгими POSIX-правами `0700` (`rwx------`), исключая доступ сторонних процессов и чтение чужих файлов, баз данных и токенов.
- **Поддержка прямого запуска до разблокировки экрана (Direct Boot Mode / FBE — #962)**:
  - В `AndroidManifest.xml` для `BootReceiver` включен флаг `android:directBootAware="true"` и зарегистрировано системное действие `LOCKED_BOOT_COMPLETED`.
  - При ночной перезагрузке устройства с шифрованием на уровне файлов (File-Based Encryption) приложение корректно инициализирует контекст защищенного хранилища (`createDeviceProtectedStorageContext()`) и автоматически запускает службы сразу после снятия блокировки экрана.
- **Предотвращение потери данных клиентов при облачной синхронизации (Pre-Restore Snapshot Guard — #952)**:
  - В `ProjectRepository` метод `createPreRestoreBackup()` перед распаковкой любых архивов или восстановлением из облака автоматически создает резервный снимок текущего каталога проекта в системном кэше. Это гарантирует, что свежие транзакции или заказы в базах SQLite не будут безвозвратно затерты при синхронизации.
- **Обнаружение открытых ключей баз данных и SQLCipher в статическом анализаторе (#331)**:
  - В `SecretLeakScanner` добавлены детекторы жестко закодированных ключей SQLCipher (`PRAGMA key = '...'`) и паролей в строках подключения (`postgres://...`). Сканер заблаговременно предупреждает разработчика об угрозе компрометации данных.
- **Автоматическое облачное резервное копирование в Telegram (#893)**:
  - Верифицирована и протестирована связка `sendCloudBackupToTelegram()` в `PyBionicViewModel` и `RemoteAlertSender.sendTelegramBackup()`, позволяющая по одному клику отправлять зашифрованный архив бота с базами данных в секретный Telegram-чат администратора.
- **Защита от сбоев компиляторов и доступность прекомпилированных пакетов ARM64 (#509, #512, #305)**:
  - В `bionic_pkg.py` верифицирована принудительная криптографическая проверка SHA-256 контрольных сумм скачиваемых пакетов и встроенный индекс популярных бинарных колес ARM64 Bionic (`numpy`, `pillow`, `cryptography`, `clang`, `make`).
- **Соблюдение политик SEAndroid и безопасное исполнение без W^X нарушений (#963)**:
  - Безопасный режим работы интерпретатора байткода без несанкционированного выделения страниц `PROT_EXEC | PROT_WRITE`.
- **Pure-Pillow визуальный диффинг без Chromium (#628)**:
  - В шаблоне `site_visual_differ` полностью исключена зависимость от десктопного Chromium, алгоритм попиксельного сравнения переведен на нативный Pillow.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **12 дефектов приоритета P0** (#256, #305, #331, #341, #509, #512, #582, #628, #893, #952, #962, #963). Общее число устраненных дефектов достигло **97**, а количество оставшихся дефектов P0 равно **0**!

---

## 🛡️ Что нового в версии 2.1.11 (SemVer Patch Release — P0 Auto-Rollback, Enclave Secrets, Webhook Crypto & Integrity Guard)

- **Автоматический откат деплоя при краше (Auto-Rollback on Crash — #929)**:
  - В `ProjectRepository` и `RunnerForegroundService` реализована система автоматических контрольных точек развертывания (`.pybionic_deploy_checkpoint`). При выполнении `gitPull()` фиксируется HEAD предыдущего коммита.
  - Если после обновления бот падает в течение первых 60 секунд работы (при 3 аварийных завершениях или фатальном сбое инициализации), PyBionic автоматически откатывает проект к стабильному состоянию (`git reset --hard <commit>` и `git clean -fd`), выводит уведомление разработчику и восстанавливает бесперебойную работу.
  - Добавлен реактивный переключатель `autoRollbackOnCrashEnabled` в `SettingsScreen` (согласно Правилу 5).
- **Контроль целостности и защита системного менеджера пакетов (bionic_pkg.py Tampering Defense — #333)**:
  - В `BionicPaths` реализован метод `ensureVerifiedBionicPkg()` с обязательной проверкой криптографической контрольной суммы SHA-256 против эталонного read-only ассета в APK.
  - При обнаружении расхождения хэшей или повреждения файла скрипт автоматически переустанавливается и блокируется в режиме только для чтения (`chmod 0500` / `setReadOnly()`), исключая модификацию системного менеджера пакетов сторонними скриптами.
- **Изоляция секретов и защита от утечки через /proc/[pid]/environ (#258) и очистка RAM (#257)**:
  - В `RunnerForegroundService` внедрен защищенный режим доставки секретов (`environSecretsMaskingEnabled`). Конфиденциальные токены и пароли не передаются через таблицу окружения `execve`, видимую другим процессам под тем же Android UID через `/proc/[pid]/environ`. Секреты сохраняются в зашифрованный/изолированный файл анклава с правами 0600 и прозрачно импортируются в память Python через системный перехватчик `sitecustomize.py`.
  - В `SecretVault` добавлено принудительное зануление байтовых массивов в памяти JVM (`plainBytes.fill(0)`), исключая сохранение паролей в дампах кучи.
- **Защита веб-терминала от инъекций шелл-команд (Web Terminal Shell Injection Defense — #261)**:
  - В `WebDashboardServer` эндпоинт выполнения команд переведен на прямую передачу аргументов `argv` через токенизатор командной строки `tokenizeCommandLine` и прямой вызов `ProcessBuilder`, исключая конкатенацию аргументов внутри `/bin/sh -c` и предотвращая инъекции метасимволов.
- **Оптимизация редактора кода и устранение лагов для файлов 1000+ строк (Compose TextField Lag Defense — #426)**:
  - В `PythonSyntaxHighlighter` введен порог `MAX_HIGHLIGHT_CHARS = 25_000` и режим повышенной производительности: для скриптов размером свыше 1000 строк тяжелый посимвольный рендеринг регулярных выражений автоматически отключается на лету, сохраняя плавный отклик 60/120 FPS и исключая ANR. В редакторе отображается информационный статус-бейдж.
- **Криптографическая верификация вебхуков оплат HMAC-SHA256, Stripe и Telegram (#337)**:
  - В `templates/pybionic_core.py` (синхронизировано со всеми 28 шаблонами ботов в BotHub) добавлены функции `verify_webhook_hmac_sha256()`, `verify_stripe_signature()` и `verify_telegram_secret_token()` с использованием сравнения в постоянном времени (`hmac.compare_digest`) для защиты от атак по времени.
- **Интеграция с агрессивными OEM-киллерами процессов (DuraSpeed, PowerGenie, Transsion Freezer — #233, #253, #972, #989, #992, #993, #995)**:
  - В `OemPowerHelper` добавлены прямые намерения (Intent) для белых списков MediaTek DuraSpeed (`com.mediatek.duraspeed`), Transsion Freezer (`com.transsion.freezer`), Huawei PowerGenie (`com.huawei.powergenie`) и App Launch Control, а также детектор режима экстремального энергосбережения `isPowerSaveMode()`.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано **16 дефектов приоритета P0** (#121, #233, #253, #257, #258, #261, #333, #337, #426, #560, #929, #972, #989, #992, #993, #995). Общее число устраненных дефектов достигло **85**, а количество оставшихся дефектов P0 снизилось до **12**!

---

## 🛡️ Что нового в версии 2.1.10 (SemVer Patch Release — P0 Pip Concurrency, Crash Incidents & Roaming Guard)

- **Изоляция кэша pip per-project и защита от повреждения колес (Pip Concurrency Defense — #506)**:
  - В `BionicPaths` переменная `PIP_CACHE_DIR` изолирована для каждого каталога проекта (`$PROJECT_DIR/.cache/pip`). Это полностью исключает race condition и повреждение архивов кэша колес (`BadZipFile`) при одновременной установке зависимостей в нескольких параллельных ботах.
  - Добавлен реактивный тумблер `pipCacheIsolationEnabled` в `SettingsScreen` (согласно Правилу 5).
- **Выделенный буфер аварийных инцидентов и трассировок (Crash Incident Store — #741)**:
  - В `RuntimeBus` внедрен отдельный буфер `errorIncidentsMap` (до 500 записей), который сохраняет логи потока `STDERR`, ошибки, исключения и полные стектрейсы `Traceback (most recent call last):`. Ошибки больше не вытесняются из памяти даже при тысячах строк информационного вывода в `STDOUT`.
  - Добавлены методы `getErrorIncidents()`, `getLatestCrashTraceback()` и очистка инцидентов.
- **Защита от финансового списания трафика в международном роуминге (Dual-SIM Roaming Guard — #1005)**:
  - В `OemPowerHelper` и `ServiceDiagnostics` добавлено определение статуса роуминга через `NetworkCapabilities.NET_CAPABILITY_NOT_ROAMING`.
  - В `RunnerForegroundService` реализована автоматическая приостановка активных фоновых ботов при работе в международном мобильном роуминге, если включена соответствующая настройка `blockRoamingTrafficEnabled`.
  - В `ProjectsScreen` добавлен предупреждающий индикатор при обнаружении активного роуминга.
- **Персистентность разрешений Storage Access Framework (SAF Permission Retention — #961)**:
  - В `ProjectRepository` метод `takePersistableUriPermissionSafely` обеспечивает фиксацию постоянных системных прав (`takePersistableUriPermission`) на выбранные пользователем каталоги и архивы, исключая потерю доступа после перезагрузки смартфона.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано еще 13 дефектов приоритета P0 (#267, #302, #306, #312, #325, #329, #338, #506, #741, #961, #1005, #1016, #1027). Общее число устраненных дефектов достигло **69**, а количество оставшихся дефектов P0 сократилось до рекордных **28**!

---

## 🛡️ Что нового в версии 2.1.9 (SemVer Patch Release — P0 Service & Security Hardening)

- **Защита от 5-секундных зависаний ANR при остановке службы (FGS Stop Timeout ANR Defense — #236)**:
  - В `RunnerForegroundService` метод `onDestroy()` переведен на асинхронное завершение процессов: воркеры помечаются на остановку и отменяются за O(1), а принудительное уничтожение дерева процессов (`killProcessTree`) передается в отдельный фоновый поток-демон. Это гарантирует возврат из `onDestroy()` менее чем за 10 мс и полностью исключает риск краша Android 5s Service Stop Timeout ANR.
  - Добавлен реактивный переключатель `asyncProcessTerminationEnabled` в `SettingsScreen` (согласно Правилу 5).
- **Мгновенный промоут службы переднего плана (StartForeground Timeout ANR Defense — #254)**:
  - В `RunnerForegroundService.onCreate()` вызов `promoteToForeground()` вынесен в самое начало метода (до любых дисковых операций `statFs`, сетевых слушателей и замеров батареи), гарантируя строгое соблюдение лимитов Android на вызов `startForeground()`.
- **Потоковая отдача архивов проектов без OOM (HTTP Chunked Streaming for Project Export — #353)**:
  - В `WebDashboardServer` для экспорта проектов (`action == "export.zip"`) реализована передача через HTTP/1.1 Chunked Transfer Encoding. Запись ZIP-архива производится напрямую в сетевой сокет порциями по 16 КБ без буферизации всего файла в `ByteArrayOutputStream`. Потребление оперативной памяти JVM составляет O(1), предотвращая краши `OutOfMemoryError` даже при скачивании проектов гигабайтного размера.
- **Криптографическая верификация вебхуков GitHub CI/CD HMAC-SHA256 (#910)**:
  - В `WebAuthGuard` и `WebDashboardServer` внедрена валидация подписи `X-Hub-Signature-256` (`sha256=<hmac_hex>`) для входящих деплой-вебхуков с использованием `HmacSHA256` и сравнением в постоянном времени (`MessageDigest.isEqual`) для защиты от атак по времени (timing attacks). Также поддержаны токены GitLab (`X-Gitlab-Token`) и Bearer-авторизация.
- **Защита от DoS-атак через архивы Zip-бомб (Zip Bomb Denial-of-Service Guard — #319)**:
  - В `ProjectRepository` для импорта ZIP-архивов внедрен жесткий контроль лимитов распаковки (по умолчанию до 500 МБ распакованных данных и не более 10 000 файлов). При превышении лимитов распаковка мгновенно прерывается с очисткой временных файлов и понятным сообщением об ошибке.
  - Добавлен реактивный переключатель и настройки в `SettingsScreen` (Правило 5).
- **Проактивная защита от отключения сети в режиме глубокого сна (Doze Mode Network Blackout — #173)**:
  - В `ProjectsScreen` добавлен информативный предупреждающий баннер при активных ботах, если для приложения включена оптимизация батареи, с кнопкой мгновенного перехода к системному разрешению `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`.
- **Реестр дефектов и аудит архитектуры**:
  - Устранено и верифицировано еще 26 дефектов приоритета P0 (#171, #173, #206, #236, #240, #251, #254, #259, #260, #262, #279, #311, #319, #353, #419, #427, #547, #586, #626, #666, #740, #742, #761, #910, #950, #965). Число устраненных дефектов в реестре достигло **56**, а оставшиеся нерешенные дефекты P0 сократились до 41.

---

## 🛡️ Что нового в версии 2.1.8 (SemVer Patch Release — P0 Runtime & Kernel Hardening)

- **Эмуляция псевдотерминала и обход termios ioctl (PTY / TTY Emulation — #1)**:
  - В `sitecustomize.py` и `BionicPaths` реализована эмуляция псевдотерминала (`isatty` для `sys.stdin`, `sys.stdout`, `sys.stderr`, `os.isatty(0, 1, 2)`), а также безопасные перехватчики `termios.tcgetattr` и `termios.tcsetattr`. Это предотвращает сбои `termios.error: (25, Inappropriate ioctl for device)` в библиотеках `Click`, `Rich`, `prompt_toolkit`, `getpass`, `tqdm`.
  - В среду исполнения добавлены флаги принудительного вывода ANSI-цветов (`CLICOLOR_FORCE=1`, `FORCE_COLOR=1`).
- **Защита от циклического переиспользования PID (PID Wrapping Race Guard — #5)**:
  - В `ProcessTreeKiller` реализована валидация `/proc/[pid]/cmdline`, предотвращающая случайное уничтожение невинных системных процессов при переиспользовании номеров PID ядром Linux.
- **Мониторинг приоритета выгрузки памяти ядра Linux (OOM Score Adjust — #8)**:
  - В `ServiceDiagnostics` и `RunnerForegroundService` добавлен мониторинг `/proc/self/oom_score_adj`.
  - В шторку телеметрии выведен информативный индикатор OOM Score с цветовой градацией приоритетов (Foreground 0..200, Visible 201..500, LMK Risk > 500).
- **Диагностика отсутствия C-заголовков Python.h и несовместимости glibc (ABI & Header Advisor — #36, #86, #87)**:
  - В `PipErrorAdvisor` добавлены анализаторы отсутствия C-заголовков `Python.h` (с рекомендацией пакета `python-dev`) и несовместимости символов glibc `GLIBC_` / `dlopen symbol lookup error` (с рекомендацией чистых Python-пакетов или Bionic ABI).
- **Специализированные инструкции автозапуска и защиты от заморозки для ведущих OEM (OEM Protection Guides — #174, #175, #183)**:
  - В `OemPowerHelper` добавлены детальные пошаговые руководства для Xiaomi / POCO (HyperOS / MIUI), Samsung Galaxy (OneUI), Huawei / Honor (EMUI / MagicOS), Oppo / Realme / OnePlus (ColorOS), и Infinix / Tecno (XOS).
- **Предохранитель от цикла падений службы (Service Crash Loop Circuit Breaker — #202)**:
  - В `RunnerForegroundService` реализован автоматический предохранитель: при более чем 3 падениях службы за 60 секунд автоперезапуск приостанавливается с показом системного оповещения для защиты аккумулятора и процессора от перегрева.
- **Безопасность запуска Foreground Service и контроль POST_NOTIFICATIONS на Android 13+ (#189, #190)**:
  - Обработка исключений запуска `ForegroundServiceStartNotAllowedException` с выводом диагностики в лог проекта и информационным баннером в списке ботов при отключенных уведомлениях на Android 13+.
- **Пользовательские переключатели (Правило 5)**:
  - В `SettingsScreen` добавлены реактивные переключатели для PTY-эмуляции, защиты от переиспользования PID и сервисного предохранителя падений, синхронизированные по всем 22 языковым пакетам.

---

## 🛡️ Что нового в версии 2.1.7 (SemVer Patch Release — P0 Security & Stability Hardening)

- **Автоматическое восстановление прав исполнения бинарников (Exec Permissions Auto-Recovery — #61)**:
  - В `BionicPaths` реализован метод `ensureExecutablePermissions()`, гарантирующий принудительное восстановление флагов исполнения `0755` (`setExecutable(true, false)`) на `python3`, `pip`, `sh` и всех исполняемых файлах каталога `$PREFIX/bin`.
  - Предотвращает ошибки `EACCES (Permission denied)` после обновлений APK через Google Play / GitHub Release или восстановления резервных копий.
- **Безопасная изоляция sys.path и детектор конфликтов модулей (Safe Sys.path Isolation — #114)**:
  - Интерпретатор Python запускается с переменной `PYTHONSAFEPATH=1` (эквивалент флага `-P`), исключающей потенциально небезопасный каталог запуска из начала `sys.path`.
  - В `ProjectRepository` и `ProjectDetailScreen` добавлен статический сканер `detectStdlibCollisions(projectId)`, предупреждающий пользователя о файлах в корне проекта (`token.py`, `email.py`, `queue.py`, `socket.py`, `http.py`, `json.py`), которые могут нарушать работу стандартной библиотеки Python.
- **Защита от дедлоков multiprocessing на Android Bionic (Multiprocessing Spawn Guard — #132)**:
  - Внедрён модуль перехвата `sitecustomize.py`, принудительно устанавливающий безопасный метод запуска `multiprocessing.set_start_method("spawn", force=True)`, исключая дедлоки POSIX `fork()` в многопоточных процессах на Android.
- **Изоляция групп процессов и завершение при гибели службы (Process Group Isolation & PDEATHSIG — #2, #19)**:
  - Каждый процесс бота автоматически изолируется в собственную группу процессов через `os.setpgrp()`, что позволяет `ProcessTreeKiller` отправлять атомарные сигналы всей группе процессов (`killpg`).
  - Установлен системный флаг ядра Linux `prctl(PR_SET_PDEATHSIG, SIGKILL)`, гарантирующий автоматическое мгновенное уничтожение всех фоновых процессов Python при падении или закрытии службы Android.
- **Защита от Zip Slip в tar-архивах (PEP 706 Tarfile Filter — #143)**:
  - В среду исполнения внедрён параметр `PYTHON_TARFILE_DEFAULT_FILTER=data`, активирующий встроенную защиту Python 3.14 от атак Path Traversal при распаковке архивов.
- **Пользовательские переключатели новых защит (Configurable Guards Policy — Правило 5)**:
  - В `SettingsScreen` и `AppPreferences` выведены удобные реактивные тумблеры для безопасной изоляции `sys.path`, метода `spawn`, изоляции групп процессов, `PDEATHSIG` и автовосстановления прав `chmod +x`, синхронизированные по всем 22 языкам.

---

## 🌐 Что нового в версии 2.1.6 (SemVer Patch Release)

- **Полная интернационализация и устранение хардкода (Systematic i18n Localization)**:
  - Проведён исчерпывающий аудит всей кодовой базы; выявлены и переведены все хардкоденные русскоязычные строки в Kotlin-файлах и UI-компонентах.
  - Подсказки советника сборщика `PipErrorAdvisor` (компиляторы C/Rust, manylinux) теперь локализованы и используют контекстные ресурсы `R.string.pip_hint_*` с английскими fallback-значениями.
  - Описания сканера утечек секретов `SecretLeakScanner` переведены на использование строковых ресурсов (`R.string.leak_*`).
  - Все сервисные и фоновые уведомления `RunnerForegroundService` (смена сети, предупреждения дискового пространства `DiskSpaceGuard`, статус Eco-Guard) переведены на строковые ресурсы `getString(R.string.*)`.
  - Все системные сообщения об ошибках и аутентификации веб-панели управления `WebDashboardServer` (неверный PIN, блокировка по таймауту rate limit) локализованы.
  - Ошибки внешних оповещений `RemoteAlertSender` (требование HTTPS, блокировка SSRF) переведены на строковые ресурсы.
  - Все UI-уведомления `PyBionicViewModel` (мастер-бэкап, экспорт/импорт, git deploy, обновление ботов) переведены на вызовы `str(R.string.*)`.
  - Все элементы интерфейса Jetpack Compose (`ProjectDetailScreen`, `ProjectsScreen`, `UpdateDialogs`, `TelemetrySheets`) полностью переведены на `stringResource(R.string.*)` (древовидные вкладки файлов, теги веб-UI, индикаторы обновлений, форматирование размеров и таймингов).
  - В перечисление `NetworkKind` и шаблоны `ProjectTemplate` добавлены строковые идентификаторы ресурсов и методы получения локализованных названий `getLocalizedLabel(context)`.
  - Синхронизированы 133 новых локализованных ключа по всем 22 языковым пакетам (`values-*/strings.xml`) со 100% паритетом ключей и отсутствием дубликатов.

---

## 🛡️ Что нового в версии 2.1.5 (SemVer Patch Release)

- **Предотвращение взаимоблокировок пайпов ввода-вывода (Pipe Deadlock Prevention — #7)**: В `RunnerForegroundService` поток чтения вывода синтаксического префлайта и дочерних процессов вынесен в параллельные асинхронные потоки с таймаутным объединением потоков (`stdoutJob.join()`, `stderrJob.join()`), что исключает блокировку процесса при заполнении 64 КБ буфера ядра Linux.
- **Устранение риска ANR жизненного цикла службы (Service Lifecycle ANR Fix — #185)**: Метод `RunnerForegroundService.onStartCommand` освобождён от синхронных операций дискового ввода-вывода; запуск воркеров и перезагрузка проектов перенесены в асинхронную корутину `scope.launch(Dispatchers.IO)`.
- **Защита целостности среды выполнения по SHA-256 (Bootstrap Integrity Check — #334)**: В `BootstrapInstaller` реализован алгоритм вычисления и сверки криптографических контрольных сумм SHA-256 для скачиваемых архивов bootstrap (поддержка хэшей из `#sha256=` и `?sha256=`), с сохранением метаданных `.bootstrap_sha256` и отображением статуса в `RuntimeVerification`.
- **Конфигурируемый JIT-компилятор Python 3.14 (SELinux W^X Guard — #88)**: Внедрён управляемый флаг `PYTHON_JIT` с переключателем в настройках безопасности, защищающий от сбоев интерпретатора на ядрах Android с жесткими ограничениями `W^X` / `execmem`.
- **Древовидная навигация по файлам проекта (File Tree Navigation — #429)**: В модель `ProjectFileItem` добавлены поля глубины вложенности `depth` и короткого имени `fileName`, автоматически вычисляемые в `ProjectRepository.listFiles` для иерархического отображения модульных проектов ботов.
- **Защита от бесконечного зацикливания ретрансляции сообщений (Multi-Relay Loop Guard — #624)**: В шаблоне `multi_relay` внедрён водяной знак `[PyBionic-Relayed]` и HTTP-заголовок `X-PyBionic-Relayed`, предотвращающие лавинообразное самовозбуждение и циклический спам при ретрансляции между вебхуками и ботами.
- **Пользовательские переключатели новых защит**: В `SettingsScreen` и `AppPreferences` добавлены реактивные тумблеры для JIT-компилятора и проверки целостности SHA-256, синхронизированные по всем 22 локалям.

---

## 🛡️ Что нового в версии 2.1.4 (SemVer Patch Release)

- **Глобальный поиск и атомарная пакетная замена в проектах (Multi-File Search & Replace)**: В `ProjectRepository` добавлены функции `searchInProject` и `replaceInProject`. Поддерживаются поиск по регулярным выражениям и точному совпадению, учет регистра и пакетная замена с двухфазной атомарной записью (`fd.sync()` + безопасная замена), исключающей повреждение файлов.
- **Статический сканер утечек секретов и токенов (Secret Leaks Scanner)**: Реализован модуль `SecretLeakScanner` и метод `ProjectRepository.scanForSecretLeaks`, анализирующие код и переменные окружения на предмет открытых токенов Telegram Bot API, Discord Bot, GitHub PAT, Webhook Slack, ключей AWS и приватных RSA/OpenSSH ключей. При экспорте проектов в ZIP файлы `.env` теперь автоматически исключаются при активной настройке `excludeEnvFromZip`.
- **Экспорт таблиц SQLite в CSV и JSON (SQLite Data Exporter)**: В `SqliteViewerHelper` и диалог `SqliteBrowserDialog` добавлены методы и кнопки экспорта выбранных таблиц в форматы CSV (RFC 4180 с экранированием) и JSON с копированием в буфер обмена в один клик.
- **Усечение WAL-журналов и защита от утечки диска (PRAGMA wal_checkpoint)**: В функцию `optimizeDatabase` добавлено принудительное выполнение `PRAGMA wal_checkpoint(TRUNCATE);`, сбрасывающее накопленные фреймы и сжимающее разросшиеся файлы `-wal`.
- **Защита от DNS Rebinding в веб-панели (Host Header Validation)**: В `WebAuthGuard` и `WebDashboardServer` добавлен строгий валидатор заголовка `Host`, разрешающий только localhost, loopback и доверенные приватные диапазоны подсетей (10.x, 172.16-31.x, 192.168.x, 100.x Tailscale CGNAT), блокируя атаки перепривязки DNS с публичных сайтов.
- **Предотвращение зависаний pip (PIP_NO_INPUT)**: В переменные окружения рантайма `BionicPaths` добавлен параметр `PIP_NO_INPUT=1`, исключающий блокировку фоновых процессов pip при интерактивных запросах учетных данных на stdin.
- **Поддержка стандартных Linux-шебангов (SHELL & libtermux-exec)**: Добавлено явное задание `env["SHELL"]` и автоматическая предзагрузка `libtermux-exec.so` в `LD_PRELOAD` при наличии библиотеки, что обеспечивает бесшовный запуск скриптов с шебангами `#!/bin/sh` и `#!/usr/bin/env`.
- **Защита от переполнения внутренней памяти (Disk Space Safeguard)**: Внедрена префлайт-проверка остатка свободного места на накопителе устройства перед стартом воркера (`DiskSpaceGuard`), предотвращающая сбои системных баз данных Android при дефиците памяти.
- **Пользовательские переключатели всех системных защит (Configurable Guards Policy)**: В настройки приложения (`SettingsScreen`) и `AppPreferences` выведены удобные реактивные переключатели для Circuit Breaker, Fork Bomb Guard, мягкого рестарта при смене сети, защиты диска, сканера секретов и исключения `.env` из ZIP.

---

## 🛡️ Что нового в версии 2.1.3 (SemVer Patch Release)

- **Защита от fork-бомб и переполнения таблицы процессов (Fork Bomb Guard)**: В `RunnerForegroundService` внедрён сторож дочерних процессов (максимум 32 процесса на одного бота). При обнаружении неконтролируемого спавна потомков скрипт моментально останавливается, предотвращая зависание ядра Android Linux и сбои системных процессов.
- **Атомарное сохранение файлов в редакторе (Atomic File Save)**: В `ProjectRepository.saveTextFile` реализована двухфазная атомарная запись через системную синхронизацию дискового кэша (`fd.sync()`) и атомарную замену файла (`Files.move` / `ATOMIC_MOVE`). Это полностью исключает риск порчи или обнуления скриптов бота до 0 байт при резкой выгрузке приложения системой.
- **Диагностика ошибок сборки pip (C/Rust/manylinux Advisor)**: В `PipErrorAdvisor` добавлены анализаторы типичных сбоев компиляции пакетов (отсутствие компиляторов gcc/clang, отсутствие Rust/Cargo, несовместимость manylinux-колес с Bionic ABI) с понятными рекомендациями чистых Python-аналогов для пользователя.
- **Надежная изоляция PYTHONPATH**: В `BionicPaths.buildEnv` внедрено явное задание `PYTHONPATH`, гарантирующее правильный порядок разрешения локальных модулей бота и системных пакетов рантайма без риска перехвата импортов из поддиректорий.

---

## 🛡️ Что нового в версии 2.1.2 (SemVer Patch Release)

- **Защита от зацикливания сбоев (Circuit Breaker)**: В `RunnerForegroundService` внедрён автоматический предохранитель. При фиксации циклического падения скрипта (5 сбоев подряд менее чем за 30 секунд с аптаймом менее 5 секунд) воркер автоматически приостанавливается, предотвращая нагрев устройства, разряд батареи и переполнение памяти логами.
- **Безопасное завершение дерева процессов (ProcessTreeKiller)**: Реализован быстрый поиск потомков через `/proc/[pid]/task/[tid]/children` для современных ядер Android Linux (`CONFIG_PROC_CHILDREN=y`) с резервным сканированием `/proc` для ядер чипсетов MediaTek и Unisoc. Внедрена проверка UID и защита от сигналов в чужие процессы при оборачивании PID (PID wrapping protection), а также гарантированная защита собственного процесса приложения.
- **Комплексная санитизация логов и защита от ReDoS (LogSanitizer)**: Добавлена отсечка сверхдлинных строк (>32 КБ) для предотвращения зависаний регулярных выражений при дампах base64. Добавлено автоматическое маскирование токенов GitHub (PAT), Slack API, ключей доступа AWS, Bearer JWT и приватных ключей PEM.
- **Усиление безопасности SQL-инспектора (SqliteViewerHelper)**: Полная блокировка изменяющих PRAGMA (`writable_schema`, `journal_mode`, `auto_vacuum`), защита от внедрения цепочек запросов через `;` и корректная обработка SQL-комментариев (`--`, `/* */`).
- **Защита от архивов-бомб в БотХабе (BotHubRepository)**: Внедрены лимиты безопасной потоковой распаковки ZIP-архивов (максимум 150 МБ суммарного несжатого размера и до 10 000 файлов).
- **Поддержка SSL-сертификатов и multiprocessing (BionicPaths)**: Расширен каскадный поиск корневых доверенных сертификатов (`certifi`, CA bundle, Conscrypt APEX) и добавлена переменная окружения `JOBLIB_TEMP_FOLDER` для предотвращения падений библиотек параллельных вычислений из-за отсутствия `/dev/shm` в Android.

---

## 🚀 Что нового в версии 2.1.1 (SemVer Patch Release)

- **Автоматическая установка среды Python 3.14**: Окружение распаковывается в фоне автоматически сразу при первом старте приложения без необходимости ручного нажатия кнопок в меню.
- **Бесшовная установка в БотХабе**: При установке готовых ботов из БотХаба система автоматически дожидается или на лету разворачивает Python-окружение и устанавливает зависимости. Все логи переведены на русский язык.
- **Исправление конфликта со статус-баром и вырезом камеры (Notch)**: Внедрён системный `statusBarsPadding()` в окне онбординга. Кнопка *«Пропустить в консоль»* больше не перекрывается часами, аккумулятором и камерой.
- **Исправление наложения системных кнопок навигации**: Внедрён `navigationBarsPadding()`. Кнопки *«Назад»*, *«Далее»*, *«🚀 Войти в Центр Управления»* и чекбокс согласия подняты над системной панелью Android 14.
- **Защита от некорректного переноса слов**: На кнопках навигации и карточках онбординга внедрён `softWrap = false` и сбалансированные веса (слова «Назад» и «Войти в Центр Управления» больше не ломаются на слоги).
- **Горизонтальная адаптивная прокрутка панели активных ботов**: В шторке «Активные боты и воркеры» кнопки действий (`[Стоп]`, `[Перезапустить]`, `[Web UI]`, `[Консоль]`) переведены в прокручиваемый ряд пилюль, предотвращая сжатие и вертикальный перенос текста («Ко / нсо / ль»).
- **Динамическое отображение версии**: Версия в интерфейсе теперь берётся напрямую из `BuildConfig.VERSION_NAME` (`v2.1.1`).

---

## 🌟 Что нового в версии 2.1.0 (SemVer Minor Release)

- **Интерактивный 5-актный киберпанк-онбординг**: презентация Naked Iron, песочницы Python 3.14, 24/7 хостинга, Keystore AES-256-GCM.
- **Расширенные настройки консоли**: кастомный размер шрифта (10–18 sp), перенос строк, метки времени, очистка кэша pip.
- **Безопасность Web Dashboard & AST Sandbox**: санитизация обработчиков событий, защита от XSS, ограничение размера файлов до 5 МБ.
- **Очередь задач ffmpeg**: защита от OOM при тяжелой конвертации медиа.
- **Термальные чипсы 43°C**: динамический мониторинг нагрева процессора и батареи.

---

## 🚀 Что нового в версии 2.0.0

- **Умный Watchdog с экспоненциальным Backoff**: автоматический перезапуск при падении скрипта ($5с \to 15с \to 45с \to 60с$). Счётчик сбрасывается после 60 секунд стабильной работы.
- **Двойные каналы уведомлений**:
  - `pybionic_runner_channel` (Low, тихий статус) — количество активных ботов, RAM, температура аккумулятора и сеть в статус-баре.
  - `pybionic_alerts_channel` (High, вибро, звук, свет) — моментальный сигнал тревоги при превышении лимита сбоев или перегреве.
- **Встроенный редактор кода**: быстрый запуск `[Код main.py]`, номера строк (gutter), моноширинный шрифт, поиск, кнопки «Сохранить» и «Сохранить и рестарт».
- **Автоустановка зависимостей**: парсинг `requirements.txt` при импорте или создании бота с возможностью установки всех библиотек в 1 клик.
- **Поиск и фильтры по статусам**: фильтрация «Все», «Работают», «Остановлены», «Сбои» и жест смахивания вниз для обновления (Pull-to-Refresh).
- **Экспорт бота в ZIP за 1 тап**: резервная копия проекта со всеми скриптами прямо с карточки рэк-слота.
- **Термальный сторож аккумулятора**: мониторинг температуры в реальном времени (`⚡ 34.0°C`), настраиваемые пороги отсечки (40°C, 42°C, 45°C) для защиты батареи.
- **Биометрическая защита**: блокировка экрана отпечатком пальца или системным PIN-кодом.
- **100% Offline-Ready**: встроенный офлайн-архив среды Python 3.14 (`bootstrap-aarch64.zip`, ~59 МБ). Никаких обязательных загрузок из сети при старте.
- **Автозапуск после перезагрузки**: фоновое восстановление работы ботов с включённой опцией «Автостарт».

---

## 🔋 Настройка фоновой работы 24/7 (Важно для стабильности)

Большинство производителей Android (MIUI, OneUI, XOS, ColorOS, EMUI) по умолчанию «усыпляют» приложения через 1–5 минут после выключения экрана. Чтобы ваши боты работали круглосуточно, выполните настройку для вашей марки телефона:

### 1. Xiaomi / Redmi / POCO (MIUI / HyperOS)
1. **Настройки** ➔ **Приложения** ➔ **Все приложения** ➔ **PyBionic**.
2. Включите переключатель **Автозапуск**.
3. Откройте пункт **Контроль активности** (Battery Saver) ➔ выберите **Нет ограничений** (No restrictions).
4. Откройте меню недавних приложений (квадратная кнопка навигации), зажмите карточку **PyBionic** и нажмите на иконку **Замочка** (зафиксировать в памяти).

### 2. Samsung (OneUI)
1. **Настройки** ➔ **Обслуживание устройства** ➔ **Батарея**.
2. **Ограничения в фоновом режиме** ➔ **Никогда не спящие приложения** ➔ нажмите `+` и выберите **PyBionic**.
3. Вернитесь в **Сведения о приложении PyBionic** ➔ **Батарея** ➔ выберите режим **Не ограничено** (Unrestricted).

### 3. Infinix / Tecno (XOS / HiOS)
1. **Настройки** ➔ **Управление приложениями** ➔ **Специальный доступ** ➔ **Оптимизация батареи** ➔ для PyBionic выберите **Не оптимизировать**.
2. В приложении PyBionic перейдите во вкладку **«Среда»** ➔ в блоке *«Чеклист стабильной работы»* нажмите **Защита от заморозки** ➔ переключите PyBionic с *«Интеллектуального управления»* на **«Нет ограничений»**.

### 4. Huawei / Honor (EMUI / MagicOS)
1. **Настройки** ➔ **Батарея** ➔ **Запуск приложений**.
2. Найдите **PyBionic**, отключите автоматическое управление и переведите в ручной режим:
   - Включите **Автозапуск**;
   - Включите **Косвенный запуск**;
   - Включите **Работа в фоновом режиме**.

### 5. Realme / Oppo / OnePlus (ColorOS / OxygenOS)
1. **Настройки** ➔ **Приложения** ➔ **PyBionic** ➔ **Использование батареи**.
2. Включите **Разрешить работу в фоновом режиме** и **Разрешить автозапуск**.

---

## 🛠 Быстрый старт: запуск первого Telegram-бота

1. **Создание проекта**:
   - На главном экране нажмите кнопку **`+`** (Новый проект).
   - Выберите шаблон **Telegram Bot (telebot)** или **Aiogram 3**.
2. **Установка библиотек**:
   - Перейдите во вкладку **«Пакеты»** и нажмите **«Установить всё из requirements.txt»**.
3. **Указание токена бота**:
   - Перейдите во вкладку **«Секреты/Настройки»** ➔ добавьте ключ `BOT_TOKEN` и значение, полученное от `@BotFather`.
4. **Запуск**:
   - Нажмите зелёную кнопку **«Старт»**.
   - Во вкладке **«Консоль»** появится живой лог запуска. Бот готов к работе в фоновом режиме 24/7!

---

## 🌐 Управление с компьютера (Wi-Fi Web Dashboard)

Если неудобно писать код с экрана смартфона:
1. Подключите телефон и ПК к одной сети Wi-Fi.
2. В PyBionic откройте вкладку **«Среда»** ➔ нажмите **«Включить веб-панель»**.
3. Откройте в браузере ПК указанный адрес (например, `http://192.168.1.45:8080`) и введите PIN-код.
4. Вы сможете редактировать код в полноразмерном редакторе, смотреть логи и управлять скриптами прямо с клавиатуры компьютера.

---

## 🔒 Безопасность и конфиденциальность

- **100% Offline-First**: приложение не имеет собственных серверов сбора аналитики, трекеров или телеметрии.
- **Изоляция секретов**: ваши API-токены и ключи шифруются и хранятся исключительно в приватном каталоге Android (`/data/user/0/dev.pybionic.runner`).
- **Отказ от ответственности**: разработчик предоставляет открытую среду выполнения скриптов и не несёт ответственности за сторонний код, размещаемый пользователем.

---

## 📦 Метаданные релиза

| Параметр | Значение |
|---|---|
| **Имя пакета** | `dev.pybionic.runner` |
| **Версия** | `2.0.0` (`versionCode: 2`) |
| **Целевая архитектура** | `arm64-v8a` (Android 8.0+) |
| **Файл релиза** | `dist/PyBionic-v2.0.0-arm64.apk` |
| **Размер APK** | ~61.4 МБ (включает автономный Python 3.14) |
| **SHA-256 сертификата** | `f63a57e5f95a901032eb3951271d6891cc9bcb5454e1e60754ecf00ac583018b` |
| **Хранилище ключей** | `pybionic-release.jks` (Key Alias: `pybionic`) |
