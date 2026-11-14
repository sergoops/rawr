# Rexture latency report

Дата: 2026-11-14

Ветка измерений: `perf/rexture-latency-report` (baseline) → `perf/rexture-dng-fastpath-validation` (вариант 1)

Worktree: `/home/sergoops/dev/rawr-rexture`

База: `aea6422` (`perf/jpeg-capture-latency-main`); baseline-отчёт `ba962a1`

Устройство: vivo S50 Pro mini (`V2527A`), adb `192.168.1.199:45741`

APK: `com.rawr.camera.benchmark`, versionCode 28

Baseline APK SHA-256: `385d070afe64d5416a994662b0e91b9f057d79416a518ad47f0dd7ad57126464`

Вариант 1 APK SHA-256: `5c297df2762f2d2c0a0dc90a45180d70707c1069a11c3becc66fec074b265582`

## 1. Цель и границы

Собрать статистику задержек Rexture на текущей сцене и разложить её по этапам:
от нажатия затвора до публикации JPEG, а для режима DNG+JPEG — до завершения обоих DNG.
Первая часть — измерение baseline без изменения алгоритмов, параметров Rexture, JPEG/UltraHDR
и настроек по умолчанию. Вторая часть — проверка варианта 1: перенос ожидания durable journal
и запуска base-DNG после merge, чтобы `BURST_SAVE` перекрывался с merge. Пиксельная математика
не менялась; менялся только порядок операций. Маркеры и отчёт живут только на ветках измерений;
финальная ветка `perf/jpeg-capture-latency-main` не изменялась.

## 2. Конфигурация

| Параметр | Значение |
|---|---|
| Сцена | одна текущая сцена, слабый свет |
| Объектив | 1x |
| RAW | 4096x3072 (12.6 MP) |
| Rexture | включён, 6 кадров |
| Rexture Native RGB | выключен |
| Chroma Denoise | выключен |
| JPEG | q98, 4:2:0, UltraHDR включён |
| Save Base DNG | включён (для B) |
| A | JPEG-only, DNG выключен |
| B | JPEG + DNG: base DNG + merged `_MF6` DNG |

ISO/SS в парах были стабильны: ISO ~643–651, SS 1/15. Это важно: разница A/B не объясняется
изменением экспозиции.

## 3. Методика и маркеры

Использован benchmark-APK с release-safe маркерами:

- Kotlin: `REXTURE_TIMING stage=press` после `requestedAtNs`, `stage=accepted` после
  `CAPTURE_ACCEPTED`, `stage=publish` после `CAPTURE_JPEG_PUBLISHED`.
- Native: `REXTURE_TIMING` для `merge_start`, `merge_done`, `project_done`,
  `rgb_prep_done`, `demosaic_done`, `render_start`, `render_done`, `jpeg_start`,
  `jpeg_done`, `publish`.
- `REXTURE_CONFIG` фиксирует алгоритм, число кадров, `nativeRgb`, JPEG/DNG-флаги и RAW-размер.
- Все native-маркеры используют `clock_gettime(CLOCK_MONOTONIC)`; Kotlin press/accepted —
  `System.nanoTime()`. End-to-end берётся из `CAPTURE_JPEG_PUBLISHED.elapsedMs`, чтобы не
  зависеть от смещения часов.

Основной датасет: 20 пар A/B, порядок внутри пары чередовался (A→B, затем B→A), по 2
прогревочных кадра на конфигурацию. Приложение не перезапускалось между парами; формат
переключался через topbar. Это даёт 20 измерений на конфигурацию при одинаковом тепловом
дрейфе внутри пары.

Дополнительно были сняты последовательные блоки по 10 кадров (A1/B1/B2/A2/A3). Они
использованы только как cross-check: после B блоки A2/A3 неожиданно замедлились до уровня B
(см. раздел ограничений), поэтому основной вывод построен на paired-датасете.

## 4. Результаты

### 4.1 End-to-end

| Метрика, мс | A: JPEG-only | B: JPEG+DNG | Δ (B−A) |
|---|---:|---:|---:|
| Медиана click→JPEG publish | **2029.4** | **2363.9** | **+334.5** |
| p95 | 2058.2 | 2469.5 | +411.3 |
| min | 1983.7 | 2302.2 | — |
| max | 2080.5 | 2821.4 | — |
| Медиана внутри пар B−A | — | — | **+346.2** |
| Отношение медиан B/A | — | — | **1.165×** |

B медленнее примерно на **0.33–0.35 с** (+16–17%). В среднем B имеет один выброс
2821 мс; медиана устойчивее.

### 4.2 Поэтапный waterfall (медианы)

**A, JPEG-only:**

```
нажатие
  +18.0   press → accepted
  +21.9   accepted → merge_start
 +767.8   merge phase
  +33.6   merge → rgb_prep_done
 +538.4   rgb_prep → demosaic_done
   +0.0   demosaic → render_start
 +289.8   render
   +0.1   render → JPEG writer
 +285.0   JPEG writer
  +67.6   JPEG done → native publish
≈2029    click → JPEG publish
```

**B, JPEG+DNG:**

```
нажатие
  +28.2   press → accepted
 +370.2   accepted → merge_start  ← здесь BURST_SAVE
 +755.9   merge phase
  +65.5   merge → project_done (DNG projection)
   +9.8   project → rgb_prep_done
 +535.1   rgb_prep → demosaic_done
   +0.0   demosaic → render_start
 +290.8   render
   +0.2   render → JPEG writer
 +277.9   JPEG writer
  +48.3   JPEG done → native publish
≈2364    click → JPEG publish
```

Суммы по независимым медианам не сходятся на несколько мс из-за округления и перекрытий;
это нормально для waterfall по медианам.

### 4.3 Основные этапы

| Этап, мс (медиана / p95) | A: JPEG-only | B: JPEG+DNG | Δ медиан |
|---|---:|---:|---:|
| press → accepted | 18.0 / 21.8 | 28.2 / 31.4 | +10.2 |
| accepted → merge_start | 21.9 / 31.4 | 370.2 / 420.6 | **+348.3** |
| merge phase span | 767.8 / 788.8 | 755.9 / 770.6 | −11.9 |
| merge → rgb_prep_done | 33.6 / 34.8 | 75.2 / 88.5 | +41.6 |
| — merge → project_done | — | 65.5 / 75.0 | — |
| — project → rgb_prep_done | — | 9.8 / 16.5 | — |
| rgb_prep → demosaic_done | 538.4 / 563.3 | 535.1 / 548.0 | −3.2 |
| demosaic → render_start | 0.0 / 0.1 | 0.0 / 0.1 | 0.0 |
| render | 289.8 / 307.5 | 290.8 / 300.0 | +1.0 |
| render → JPEG writer | 0.1 / 0.2 | 0.2 / 0.4 | +0.1 |
| JPEG writer → JPEG done | 285.0 / 310.5 | 277.9 / 320.1 | −7.1 |
| JPEG done → native publish | 67.6 / 76.4 | 48.3 / 59.2 | −19.2 |
| accepted → native publish | 2010.5 / 2039.3 | 2337.9 / 2445.3 | +327.4 |

Ключевой вывод: **почти вся разница B−A создаётся до merge, на `BURST_SAVE`**, а не на
DNG-энкодерах после merge.

### 4.4 Merge: внутренняя разбивка

| Компонент merge, мс (медиана / p95) | A: JPEG-only | B: JPEG+DNG |
|---|---:|---:|
| noise | 10.5 / 11.4 | 13.6 / 18.4 |
| reference prepare | 33.2 / 34.0 | 34.1 / 36.0 |
| companion prepare | 111.8 / 112.7 | 109.7 / 111.2 |
| align | 99.6 / 100.9 | 99.1 / 100.9 |
| kernel | 0.0 | 0.0 |
| robustness | 0.0 | 0.0 |
| accumulate | 112.0 / 113.5 | 111.2 / 112.3 |
| finalize | 197.1 / 199.3 | 195.6 / 200.7 |
| merge compute total | 687.0 / 698.2 | 678.9 / 698.1 |

`merge phase span` (767.8 / 755.9 мс) примерно на 80 мс больше `merge compute total`
(687 / 679 мс). Это подготовка/очередь/переходы вокруг `MergeProcessor::run`, а не
дополнительный GPU-счёт.

GPU-wall merge (B, медиана): `wallMs=678.9`, `gpuMs=561.8`, `waitMs=668.9`,
`idleMs=104.6`. То есть GPU занят ~562 мс, но wall-clock merge ~679 мс; заметная часть —
ожидание/простой.

### 4.5 DNG-путь B

| Компонент B | Медиана, мс | p95, мс |
|---|---:|---:|
| BURST_SAVE total | **347.4** | 394.9 |
| — readback | 60.1 | 79.6 |
| — storage + setup | 285.1 | 315.3 |
| base DNG write | 142.8 | 157.5 |
| base DNG fsync | 15.0 | 22.0 |
| merged DNG write | 155.8 | 177.2 |
| merged DNG fsync | 22.4 | 38.2 |
| BURST_FINISHED accepted→finished | 2298.2 | 2399.4 |

`BURST_SAVE` — это сохранение 6 кадров (150 994 944 байт) перед merge. Он есть только в B
и занимает ~347 мс. DNG-писатели base/merged (~143 + ~156 мс записи) идут **параллельно**
render/JPEG и в этих запусках завершаются раньше публикации JPEG (`BURST_FINISHED` 2298 мс
против click→publish 2364 мс). Поэтому их вклад в критический путь мал; основной штраф —
именно предварительный `BURST_SAVE`.

Итоговая атрибуция B−A:

- `accepted → merge_start`: +348.3 мс (внутри — `BURST_SAVE` 347.4 мс);
- DNG projection после merge: +65.5 мс;
- но merge в B на 11.9 мс быстрее, JPEG на 7.1 мс быстрее, publish tail на 19.2 мс короче;
- суммарно click→publish: **+334.5 мс**.

### 4.6 Вариант 1: merge раньше durable journal

Вариант 1 переносит `awaitDurable` и `baseWriter.start` из блока base-DNG (до merge) в точку
после post-merge `awaitDurable`. `BURST_SAVE` остаётся, но перекрывается с merge; base DNG
по-прежнему создаётся, в том числе при ошибке merge (fallback в catch). Пиксельная математика
не менялась.

APK варианта 1: `5c297df2…`; ветка `perf/rexture-dng-fastpath-validation`, коммит `c7ac89c`.
Датасет: те же 20 пар A/B, тот же сценарий и настройки, что в baseline.

**End-to-end, baseline → вариант 1:**

| Метрика, мс | A baseline | A вариант 1 | B baseline | B вариант 1 |
|---|---:|---:|---:|---:|
| Медиана click→JPEG publish | 2029.4 | **2009.0** | 2363.9 | **2022.4** |
| p95 | 2058.2 | **2057.9** | 2469.5 | **2067.2** |
| min | 1983.7 | 1944.9 | 2302.2 | 1960.7 |
| max | 2080.5 | 2059.9 | 2821.4 | 2088.8 |
| B−A по медианам | — | — | **+334.5** | **+13.4** |
| B−A внутри пар, медиана | — | — | +346.2 | **−1.1** |
| B/A по медианам | — | — | 1.165× | **1.007×** |

**Этапы варианта 1 (медиана / p95, мс):**

| Этап | A: JPEG-only | B: JPEG+DNG |
|---|---:|---:|
| press → accepted | 15.5 / 17.8 | 24.5 / 31.8 |
| accepted → merge_start | 21.5 / 26.4 | **52.5 / 62.4** |
| merge phase span | 767.9 / 792.3 | 759.5 / 768.6 |
| merge → project_done | — | 53.9 / 70.8 |
| project → rgb_prep_done | — | 11.7 / 14.5 |
| merge → rgb_prep_done | 34.5 / 48.4 | 66.6 / 77.7 |
| rgb_prep → demosaic_done | 548.9 / 575.9 | 542.1 / 564.8 |
| render | 290.2 / 314.0 | 282.8 / 309.7 |
| JPEG writer | 266.3 / 274.8 | 257.2 / 271.2 |
| JPEG done → native publish | 57.3 / 62.9 | 35.5 / 46.3 |
| accepted → native publish | 1992.1 / 2043.3 | 1995.7 / 2035.4 |

**DNG-путь варианта 1 (B):**

| Компонент | Медиана, мс | p95, мс |
|---|---:|---:|
| `BURST_SAVE` total | 373.5 | 414.7 |
| — readback | 97.2 | 132.0 |
| — storage + setup | 278.2 | 293.1 |
| base DNG write / fsync | 138.3 / 14.2 | 143.3 / 25.0 |
| merged DNG write / fsync | 147.5 / 32.4 | 156.7 / 37.1 |
| `BURST_FINISHED` accepted→finished | 1979.7 | 1999.6 |

`accepted → merge_start` для B упал с 370.2 до 52.5 мс (p95 62.4); это ниже порога плана
120 мс. `BURST_SAVE` (373.5 мс) перекрывается с merge (759.5 мс). DNG-писатели после merge
по-прежнему скрыты за render/JPEG: `BURST_FINISHED` 1979.7 мс раньше публикации JPEG
1995.7 мс (accepted→publish). B практически сравнялся с A: медиана 2022.4 против 2009.0 мс,
разница +13.4 мс (внутри пар медиана −1.1 мс).

Проверка порядка: `tools/phone-performance/rexture_order_check.py` на обоих прогонах B
возвращает 0; baseline с порогом 120 мс падал, вариант 1 проходит. Оба DNG (base и merged
`_MF6`) созданы и валидны как TIFF/DNG: 4096×3072, 16-bit, Compression=7, Photometric=32803
(CFA). JPEG создан; пиксельная математика не менялась.

### 4.7 Soak и память

| Прогон | Медиана, мс | p95, мс | Успех | skin после | Thermal status |
|---|---:|---:|---:|---:|---:|
| 100× A (JPEG-only), 1x Rexture | 2359.5 | 2428.8 | 100/100 | 39.85 °C | 0 |
| 100× B (JPEG+DNG), 1x Rexture | 2397.9 | 2456.3 | 100/100 | **41.90 °C** | **1 (throttling)** |

В 100× B `accepted→merge_start`: p50 68.9 мс, p95 79.6 мс, max 117.9 мс — порядок
выдержан на всех 100 кадрах. Soak-медианы выше paired-результата (2022 мс), потому что
это непрерывная серия из 100 Rexture-кадров: к концу кожа 41.9 °C, thermal status 1.
Это нагрузочный тест, а не сравнение «холодных» A/B.

Память (PSS):

| Точка | 100× A | 100× B |
|---|---:|---:|
| before | 237 070 KB | 239 041 KB |
| after | 340 990 KB | 339 639 KB |
| Δ before→after | +103.9 MB | +100.6 MB |
| Δ vs single-frame baseline after 228 191 KB | +112.8 MB | **+111.4 MB** |

Гейт плана `+100 MB vs baseline` **не выполнен** для 1x Rexture: после 100 кадров PSS
превышает baseline single-frame на ~111 MB. Основной вклад — EGL mtrack (150 324 →
229 088 KB, +78.8 MB); native heap при этом не растёт (35.7 → 30.4 MB), Dalvik +3.4 MB.
Это свойство 1x Rexture/пула EGL, а не добавленных вариантом 1 аллокаций; baseline
Rexture 1x в этой серии не измерялся. `baseFrame` (~25 MB) удерживается до конца merge,
как и в плане; при необходимости fallback — читать base-DNG после merge.

## 5. Интерпретация

1. **JPEG-only критический путь** — merge (~768 мс), demosaic (~538 мс), render (~290 мс),
   JPEG (~285 мс). В merge самые крупные компоненты: finalize ~197 мс, accumulate ~112 мс,
   companion prepare ~112 мс, align ~100 мс.
2. **DNG+JPEG** в baseline добавляет не «ещё один энкод в конец», а **сохранение burst до merge**.
   Это объясняет, почему DNG-писатели выглядят дешёвыми в логах, но общий выигрыш
   JPEG-only всё равно ~0.33–0.35 с.
3. Главный адресат — `BURST_SAVE` (storage+setup ~285 мс, readback ~60 мс), а не
   `BURST_DNG_DONE.writeMs`. Вариант 1 это подтвердил: перенос ожидания durable journal
   и старт base-DNG после merge убрал почти весь штраф B. `BURST_SAVE` теперь перекрывается
   с merge, а не стоит перед ним.
4. Для JPEG-only запас есть в merge (GPU idle ~105 мс, span на ~80 мс больше compute),
   demosaic и хвосте публикации (~68 мс), но это уже вне задачи текущего отчёта.
5. **Итог варианта 1:** B 2363.9 → 2022.4 мс (медиана), B−A 334.5 → 13.4 мс; цель плана
   2.02–2.12 с достигнута, жёсткий предел 2.15 с пройден, B−A < 100 мс. Остаточная
   разница в основном шум/IO; `BURST_SAVE` всё ещё добавляет p95-хвост.

## 6. Ограничения

- Одна сцена, один слабый свет, один объектив 1x; результаты не переносятся автоматически
  на другие сцены/ISO/выдержки.
- Baseline и вариант 1 — по 20 пар A/B в разных сессиях/тепловых состояниях. Сравнение
  baseline→вариант 1 идёт по медианам и p95, а не по одному общему paired-ряду; абсолютные
  значения могут дрейфовать на единицы/десятки мс.
- В последовательных baseline-блоках A1/B1/B2/A2/A3 после B блоки A2/A3 замедлились до
  ~2.36 с (A1 был 2.03 с), хотя ISO/SS не менялись. Причина не установлена: тепло, фоновый
  I/O после DNG-записей или состояние приложения. Поэтому baseline использует paired-порядок.
- К концу baseline paired-прогона skin temp достигал ~39.1 °C (порог 38/40 °C), thermal
  status 0. Абсолютные значения тёплые; сравнение A/B внутри пар остаётся корректным.
- Маркеры добавляют логирование в release; их overhead не выделялся отдельно и входит
  в измеренные значения.
- DNG в B включает base DNG и merged `_MF6` DNG; это соответствует текущим настройкам
  `Save Base DNG = on`, а не «минимальному» DNG-выходу.
- Пиксельная математика варианта 1 не менялась: переставлены только durable-wait и запуск
  base-DNG. Побайтовое сравнение живых JPEG/DNG невозможно из-за шума сенсора между
  кадрами; проверены структура/размеры DNG, наличие обоих файлов и отсутствие ошибок.
- 100× B soak прошёл 100/100, но **не уложился в thermal-гейт** плана: skin 41.9 °C,
  thermal status 1. 100× A также нагрел устройство (39.85 °C). Это ограничение
  продолжительной 1x Rexture-нагрузки; paired-результат 2022 мс получен в более холодном
  состоянии.
- Гейт памяти `+100 MB vs baseline` для 1x Rexture не выполнен: +111.4 MB после 100× B
  (в основном EGL mtrack). Baseline Rexture 1x для прямого сравнения не измерялся;
  single-frame baseline 228 191 KB. Это ограничение режима, не следствие reorder.

## 7. Артефакты

Baseline:

- `tmp/perf-opt/rexture-pairs-stages-baseline.json` — разобранные baseline-этапы.
- `tmp/perf-opt/rexture-pairs-baseline-logcat.txt` — baseline logcat.
- `tmp/perf-opt/rexture-ABBA-A1/…A3`, `…B1/…B2` — последовательные exploratory-блоки.
- Baseline-отчёт — коммит `ba962a1`.

Вариант 1:

- `tmp/perf-opt/rexture-pairs-task2.jsonl` — 40 end-to-end записей (20 A + 20 B).
- `tmp/perf-opt/rexture-pairs-task2-logcat.txt` — полный logcat paired-прогона.
- `tmp/perf-opt/rexture-pairs-stages-task2.json` — разобранные этапы.
- `tmp/perf-opt/rexture-pairs-task2-summary.txt` — сводные статистики.
- `tmp/perf-opt/rexture-task2-base.dng`, `…-merged.dng`, `…-MF6.jpg` — проверенные выходы.
- `tmp/perf-opt/rexture-task2-soak100/` — 100× A soak, summary/logcat/memory/thermal.
- `tmp/perf-opt/rexture-task2-soak100-b/` — 100× B soak, summary/logcat/memory/thermal.
- `tmp/rexture_pairs.py` — драйвер paired-прогона.
- `tmp/parse_rexture.py` — парсер маркеров и сводные статистики.
- `tools/phone-performance/rexture_order_check.py` — проверка `accepted→merge_start`.

Команды воспроизведения:

```sh
cd /home/sergoops/dev/rawr-rexture
JAVA_HOME=/usr/lib/jvm/java-17-openjdk ./gradlew --no-daemon :app:assembleBenchmark
tools/phone-performance/install_benchmark_apk_autotap.sh \
  app/build/outputs/apk/benchmark/app-benchmark.apk

uv run --no-project tmp/rexture_pairs.py
adb logcat -d -v brief > tmp/perf-opt/rexture-pairs-task2-logcat.txt
cp tmp/perf-opt/rexture-pairs-task2.jsonl tmp/perf-opt/rexture-pairs.jsonl
cp tmp/perf-opt/rexture-pairs-task2-logcat.txt tmp/perf-opt/rexture-pairs-logcat.txt
uv run --no-project tmp/parse_rexture.py
uv run --no-project tools/phone-performance/rexture_order_check.py \
  tmp/perf-opt/rexture-pairs-task2-logcat.txt
```
