import requests
import xml.etree.ElementTree as ET
import time
import os
import sys
import datetime
import glob
import urllib.parse
import math
import concurrent.futures
import re

BASE_API_URL = "https://api.rule34.xxx/index.php"
REQUEST_TIMEOUT = 15
HEAD_REQUEST_TIMEOUT = 10
SLEEP_BETWEEN_API_PAGES = 0.5
MAX_HEAD_THREADS = 20
VIDEO_EXTENSIONS_FOR_SORTING = ['.mp4', '.webm', '.avi', '.mov', '.flv', '.wmv']
PHOTO_EXTENSIONS_FOR_SORTING = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff']
GIF_EXTENSION = '.gif'

COUNT_DIR = "вычислитель количества"
SIZE_DIR = "вычислитель размера"
DOWNLOAD_DIR = "загрузчик"

PRESETS_SUBDIR = "пресеты"
REPORTS_SUBDIR = "отчёты"
CONFIG_SUBDIR = "конфигурация"
BLACKLIST_FILENAME = "blacklist.txt"
MEDIA_SUBDIR = "медиа"
GIF_SUBDIR = "гифки"

def format_bytes(byte_count):
    if byte_count is None:
        return "N/A"
    if byte_count == 0:
        return "0 Bytes"

    size_name = ("Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(byte_count, 1024)))
    p = math.pow(1024, i)
    s = round(byte_count / p, 2)
    return f"{s} {size_name[i]}"

def safe_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def sanitize_filename(query):
    s = re.sub(r'[<>:"/\\|?* ]', '_', query)
    return s[:50]

def sanitize_folder_name(name):
    name = name.replace('+', '_')
    name = name.replace(' ', '_')
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = name.strip(' .')
    if not name:
        return "invalid_tag_name"
    return name

def read_lines_from_file(filepath):
    lines = []
    if not os.path.exists(filepath):
        return lines
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    lines.append(line)
    except Exception as e:
        print(f"Ошибка при чтении файла {filepath}: {e}")
    return lines

def setup_module_directories(base_dir, subdirs, blacklist_filename=None):
    os.makedirs(base_dir, exist_ok=True)
    for subdir in subdirs:
        subdir_path = os.path.join(base_dir, subdir)
        os.makedirs(subdir_path, exist_ok=True)
        if subdir == CONFIG_SUBDIR and blacklist_filename:
            blacklist_filepath = os.path.join(subdir_path, blacklist_filename)
            if not os.path.exists(blacklist_filepath):
                try:
                    with open(blacklist_filepath, 'w', encoding='utf-8') as f:
                        pass
                    print(f"Создан файл черного списка: {blacklist_filepath}")
                except Exception as e:
                    print(f"Ошибка при создании файла черного списка: {e}")


def load_blacklist_for_module(module_base_dir):
    blacklist_filepath = os.path.join(module_base_dir, CONFIG_SUBDIR, BLACKLIST_FILENAME)
    return read_lines_from_file(blacklist_filepath)

def get_rule34_post_count_api(tag_string_with_spaces, timeout=REQUEST_TIMEOUT):
    if not tag_string_with_spaces or not tag_string_with_spaces.strip():
        return 0

    params = {
        'page': 'dapi',
        's': 'post',
        'q': 'index',
        'tags': tag_string_with_spaces.strip(),
        'limit': 1
    }
    url = BASE_API_URL

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()

        if not response.content or not response.content.strip():
             return -1

        root = ET.fromstring(response.content)
        count_str = root.get('count')

        if count_str is not None:
            try:
                count = int(count_str)
                return count
            except ValueError:
                 return -1
        else:
             posts = root.findall('post')
             if len(posts) > 0:
                 return len(posts)
             else:
                 return 0

    except requests.exceptions.RequestException as e:
        return -1
    except ET.ParseError as e:
        return -1
    except Exception as e:
        return -1

def format_query_with_blacklist(raw_tag_string, blacklist_tags):
    query_parts = []
    stripped_raw_tag_string = raw_tag_string.strip()
    if stripped_raw_tag_string:
        query_parts.append(stripped_raw_tag_string)

    for bt in blacklist_tags:
        stripped_bt = bt.strip()
        if stripped_bt:
            query_parts.append(f"-{stripped_bt}")

    final_query_string = " ".join(part for part in query_parts if part)
    return final_query_string.strip()

def select_preset_file(presets_dir):
    preset_files = sorted(glob.glob(os.path.join(presets_dir, '*.txt')))

    if not preset_files:
        print(f"В папке '{os.path.basename(presets_dir)}' не найдено файлов пресетов (.txt).")
        return None

    print("\nДоступные файлы пресетов:")
    for i, file_path in enumerate(preset_files):
        print(f"[{i+1}] {os.path.basename(file_path)}")

    while True:
        choice = input(f"Выберите файл пресета (номер или имя файла): ").strip()

        if not choice:
            print("Выбор не может быть пустым.")
            continue

        try:
            index = int(choice) - 1
            if 0 <= index < len(preset_files):
                return preset_files[index]
            else:
                print("Некорректный номер файла.")
        except ValueError:
            chosen_file_path = os.path.join(presets_dir, choice)
            if os.path.exists(chosen_file_path) and chosen_file_path in preset_files:
                 return chosen_file_path
            else:
                 print(f"Файл '{choice}' не найден в папке '{os.path.basename(presets_dir)}'.")

def run_counter_module():
    print("\n" + "=" * 50)
    print("ЗАПУЩЕН МОДУЛЬ: СЧЕТЧИК ПОСТОВ")
    print("-" * 50)

    module_base_dir = COUNT_DIR
    setup_module_directories(module_base_dir, [PRESETS_SUBDIR, REPORTS_SUBDIR, CONFIG_SUBDIR], BLACKLIST_FILENAME)
    presets_dir_path = os.path.join(module_base_dir, PRESETS_SUBDIR)
    reports_dir_path = os.path.join(module_base_dir, REPORTS_SUBDIR)

    global_blacklist_tags = load_blacklist_for_module(module_base_dir)
    is_blacklist_active = bool(global_blacklist_tags)

    requested_tags_list = []
    report_query_string = "N/A"

    while True:
        print("\nВыберите способ ввода тегов:")
        print("[1] Ручной ввод (один или несколько тегов через пробел)")
        print("[2] Загрузить из файла пресета")
        print("[0] Назад в главное меню")
        input_choice = input("Ваш выбор (1, 2 или 0): ").strip()

        if input_choice == '0':
            return
        elif input_choice == '1':
            manual_input = input("Введите тег(и) через пробел: ").strip()
            if manual_input:
                requested_tags_list = [manual_input]
                report_query_string = manual_input
            else:
                print("Ввод тегов не может быть пустым.")
                continue
            break

        elif input_choice == '2':
            chosen_preset_path = select_preset_file(presets_dir_path)
            if chosen_preset_path:
                try:
                    with open(chosen_preset_path, 'r', encoding='utf-8') as f:
                        requested_tags_list = [line.strip() for line in f if line.strip()]
                    if not requested_tags_list:
                        print(f"В файле пресета '{os.path.basename(chosen_preset_path)}' нет тегов. Выберите другой файл.")
                        continue
                    if requested_tags_list:
                         report_query_string = requested_tags_list[0]
                    else:
                         report_query_string = "empty_preset"

                    print(f"Успешно загружено {len(requested_tags_list)} тегов из файла: {os.path.basename(chosen_preset_path)}")
                    break
                except Exception as e:
                    print(f"Произошла ошибка при чтении файла пресета: {e}")
                    continue
            else:
                 continue
        else:
            print("Некорректный выбор.")

    if not requested_tags_list and input_choice != '0':
        print("Список тегов для проверки пуст после выбора способа ввода.")
        return

    print("\n" + "=" * 50)
    print("СТАТУС ЧЕРНОГО СПИСКА")
    print("-" * 50)
    if is_blacklist_active:
        print(f"В черном списке находится {len(global_blacklist_tags)} тег(ов):")
        print(", ".join([f"'{tag}'" for tag in global_blacklist_tags]))
        print("Эти теги будут исключены из КАЖДОГО запроса (добавляются с минусом и разделяются пробелами).")
    else:
        print("Черный список пуст.")
    print("=" * 50 + "\n")

    input("\nНажмите Enter, чтобы начать проверку тегов...")

    print("-" * 50)
    print("Начало сбора данных...")

    results_with_blacklist = {}
    results_without_blacklist = {}

    total_tags_to_check = len(requested_tags_list)
    tag_separator_used = "пробел"

    for i, raw_tag_string in enumerate(requested_tags_list):
        query_string_with_bl = format_query_with_blacklist(raw_tag_string, global_blacklist_tags)

        print(f"[{i+1}/{total_tags_to_check}] Проверка тега: '{raw_tag_string}'...")

        count_with_bl = get_rule34_post_count_api(query_string_with_bl)
        results_with_blacklist[raw_tag_string] = count_with_bl

        query_string_without_bl = raw_tag_string.strip()
        count_without_bl = get_rule34_post_count_api(query_string_without_bl)
        results_without_blacklist[raw_tag_string] = count_without_bl

        print(f"  Общее количество постов для '{raw_tag_string}' (без блеклиста): ", end="")
        if count_without_bl != -1:
             print(count_without_bl)
        else:
             print("Не удалось получить данные")

        if is_blacklist_active:
             print(f"  Фактически найдено для '{raw_tag_string}' (с учетом -блеклиста): ", end="")
             if count_with_bl != -1:
                 print(count_with_bl)
             else:
                 print("Не удалось получить данные")

        time.sleep(0.7)

        print("-" * 10)

    print("-" * 50)
    print("Сбор данных завершен.")

    total_sum_without_bl = sum(count for count in results_without_blacklist.values() if count != -1)
    total_sum_with_blacklist_operator = sum(count for count in results_with_blacklist.values() if count != -1)

    global_count_only_blacklist = -1
    if is_blacklist_active:
         print("\n" + "=" * 50)
         print("Получение данных для финального отчета:")
         print("-" * 50)
         print("Выполняется запрос для определения общего количества постов только с тегами черного списка...")
         blacklist_only_query = " ".join(global_blacklist_tags)
         global_count_only_blacklist = get_rule34_post_count_api(blacklist_only_query)
         if global_count_only_blacklist != -1:
             print("Количество постов только с тегами черного списка получено.")
         else:
             print("Не удалось получить количество постов только с тегами черного списка.")
         time.sleep(0.7)
         print("=" * 50 + "\n")

    posts_removed_by_blacklist_operator = 0
    if total_sum_without_bl != -1 and total_sum_with_blacklist_operator != -1:
        posts_removed_by_blacklist_operator = total_sum_without_bl - total_sum_with_blacklist_operator
        if posts_removed_by_blacklist_operator < 0 or total_sum_without_bl == 0:
            posts_removed_by_blacklist_operator = 0

    sorted_items_for_report = []
    for tag, count in results_with_blacklist.items():
         if count != -1:
             sorted_items_for_report.append((count, tag))

    sorted_items_for_report.sort(reverse=True)

    now = datetime.datetime.now()
    timestamp_str = now.strftime('%d-%m-%Y_%H-%M-%S')

    report_filename_base = sanitize_filename(report_query_string)
    if not report_filename_base:
        report_filename_base = "empty_query"

    report_filename = f"{timestamp_str}_{report_filename_base}.txt"
    report_file_path = os.path.join(reports_dir_path, report_filename)

    print(f"\nПопытка сохранить результаты в файл: {report_file_path}")

    try:
        with open(report_file_path, 'w', encoding='utf-8') as f:
            if sorted_items_for_report:
                 f.write("--- Результаты по тегам (фактически найдено с учетом блеклиста) ---\n")
                 for count, tag in sorted_items_for_report:
                     f.write(f"{tag}: {count}\n")
            else:
                 f.write("Нет данных с учетом оператора -блеклиста для сохранения в основном списке отчета (все результаты были 0 или -1).\n")

            f.write("\n" + "=" * 40 + "\n")
            f.write("ИТОГОВЫЙ ОБЩИЙ ОТЧЕТ ПО ВСЕМ ЗАПРОСАМ\n")
            f.write("-" * 40 + "\n")
            f.write(f"Используемый разделитель тегов в запросах: '{tag_separator_used}'\n")
            f.write("-" * 40 + "\n")

            f.write(f"1. Сумма постов по всем запросам (без блеклиста): {total_sum_without_bl}\n")

            if is_blacklist_active:
                 f.write(f"2. Общее количество постов только с тегами блеклиста: ")
                 if global_count_only_blacklist != -1:
                     f.write(f"{global_count_only_blacklist}\n")
                 else:
                     f.write("Не удалось получить данные\n")

                 f.write("-" * 40 + "\n")
                 f.write(f"Фактически подсчитано постов (с учетом оператора -блеклиста): {total_sum_with_blacklist_operator}\n")
                 f.write(f"Примерное количество постов, отфильтрованных оператором -блеклиста: {posts_removed_by_blacklist_operator}\n")
                 f.write(f"Активные теги в блеклисте: {', '.join(global_blacklist_tags)}\n")
            else:
                 f.write("Черный список не использовался.\n")
                 f.write("-" * 40 + "\n")
                 f.write(f"Фактически подсчитано постов (блеклист не использовался): {total_sum_with_blacklist_operator}\n")

            f.write("=" * 40 + "\n")

        print(f"Результаты успешно сохранены в файл: {report_file_path}")
        if sorted_items_for_report:
            print(f"Файл отсортирован по количеству постов (от большего к меньшему) с учетом оператора -блеклиста.")
        else:
             print("В основном списке отчета нет данных с количеством постов (все результаты были 0 или -1).")
        print(f"Отчет находится в папке '{os.path.basename(reports_dir_path)}'.")

        print("\n" + "=" * 40)
        print("ИТОГОВЫЙ ОБЩИЙ ОТЧЕТ ПО ВСЕМ ЗАПРОСАМ:")
        print("-" * 40)
        print(f"Используемый разделитель тегов в запросах: '{tag_separator_used}'")
        print("-" * 40)

        print(f"1. Сумма постов по всем запросам (без блеклиста): {total_sum_without_bl}")

        if is_blacklist_active:
             print(f"2. Общее количество постов только с тегами блеклиста: ", end="")
             if global_count_only_blacklist != -1:
                 print(global_count_only_blacklist)
             else:
                 print("Не удалось получить данные")

             print("-" * 40)
             print(f"Фактически подсчитано постов (с учетом оператора -блеклиста): {total_sum_with_blacklist_operator}")
             print(f"Примерное количество постов, отфильтрованных оператором -блеклиста: {posts_removed_by_blacklist_operator}")
             print(f"Активные теги в блеклисте: {', '.join(global_blacklist_tags)}")
        else:
             print("Черный список не использовался.\n")
             print("-" * 40)
             print(f"Фактически подсчитано постов (блеклист не использовался): {total_sum_with_blacklist_operator}")

        print("=" * 40)

    except Exception as e:
        print(f"\nОШИБКА СОХРАНЕНИЯ: Произошла ошибка при сохранении файла: {e}")
        print(f"Не удалось сохранить файл по пути: {report_file_path}")

def run_size_calculator_module():
    print("\n" + "=" * 50)
    print("ЗАПУЩЕН МОДУЛЬ: ВЫЧИСЛИТЕЛЬ РАЗМЕРА")
    print("-" * 50)

    module_base_dir = SIZE_DIR
    setup_module_directories(module_base_dir, [CONFIG_SUBDIR, PRESETS_SUBDIR, REPORTS_SUBDIR], BLACKLIST_FILENAME)
    presets_dir_path = os.path.join(module_base_dir, PRESETS_SUBDIR)
    reports_dir_path = os.path.join(module_base_dir, REPORTS_SUBDIR)

    blacklisted_tag_strings = load_blacklist_for_module(module_base_dir)
    blacklist_api_string = " " + " ".join([f"-{tag.strip()}" for line in blacklisted_tag_strings for tag in line.split()]) if blacklisted_tag_strings else ""

    if blacklisted_tag_strings:
         print("\nБлеклист активен. Исключаемые теги:")
         for line in blacklisted_tag_strings:
             print(f"  - {line}")
    else:
         print("\nБлеклист неактивен (файл пуст или не найден).")

    def get_file_size_from_head(file_url):
        if not file_url or not isinstance(file_url, str):
            return None

        try:
            response = requests.head(file_url, timeout=HEAD_REQUEST_TIMEOUT)
            response.raise_for_status()
            content_length_str = response.headers.get('Content-Length')
            return safe_int(content_length_str, None)
        except (requests.exceptions.Timeout, requests.exceptions.RequestException, Exception):
             return None

    def get_initial_post_count(query):
        params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "tags": query,
            "limit": 0
        }
        try:
            response = requests.get(BASE_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            count_str = root.get('count')
            return safe_int(count_str, 0)
        except Exception as e:
             return 0

    def process_query_size(query, blacklist_api_string):
        query_with_blacklist = query + blacklist_api_string
        current_processed_posts = 0
        current_total_size_bytes = 0
        page = 0

        print(f"\n--- Обработка запроса: '{query}' (с учетом блеклиста) ---")

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_HEAD_THREADS) as executor:
            while True:
                params = {
                    "page": "dapi",
                    "s": "post",
                    "q": "index",
                    "tags": query_with_blacklist,
                    "limit": 1000,
                    "pid": page
                }

                try:
                    print(f"  Запрос страницы {page + 1} списка постов...")
                    response = requests.get(BASE_API_URL, params=params, timeout=REQUEST_TIMEOUT)
                    response.raise_for_status()

                    if not response.text.strip():
                         print(f"  Получен пустой ответ от API для страницы {page + 1}. Переход к следующему запросу (если есть).")
                         break

                    root = ET.fromstring(response.text)
                    posts_elements = root.findall('post')

                    if not posts_elements:
                        print(f"  Нет постов с учетом блеклиста на странице {page + 1}. Все посты для этого запроса обработаны.")
                        break

                    print(f"  Получено {len(posts_elements)} постов на странице {page + 1}.")

                    file_urls = []
                    for post_element in posts_elements:
                        file_url = post_element.get('file_url')
                        if file_url and isinstance(file_url, str):
                            file_urls.append(file_url)

                    if not file_urls:
                         print(f"  На странице {page + 1} нет постов с действительными URL файлов после фильтрации.")
                         page += 1
                         time.sleep(SLEEP_BETWEEN_API_PAGES)
                         continue

                    print(f"  Получение размера для {len(file_urls)} файлов...")
                    results = list(executor.map(get_file_size_from_head, file_urls))

                    successful_head_count_on_page = 0
                    for size in results:
                        if size is not None:
                            current_total_size_bytes += size
                            current_processed_posts += 1
                            successful_head_count_on_page += 1

                    print(f"  Получено размеров на странице {page + 1}: {successful_head_count_on_page} из {len(file_urls)}.")

                    page += 1
                    time.sleep(SLEEP_BETWEEN_API_PAGES)

                except requests.exceptions.Timeout:
                     print(f"\n  Ошибка таймаута при запросе страницы API {page + 1}. Прерывание обработки запроса '{query}'.")
                     break
                except requests.exceptions.RequestException as e:
                    print(f"\n  Ошибка при запросе страницы API {page + 1}: {e}. Прерывание обработки запроса '{query}'.")
                    break
                except ET.ParseError as e:
                     print(f"\n  Ошибка парсинга XML на странице API {page + 1}: {e}. Прерывание обработки запроса '{query}'.")
                     break
                except Exception as e:
                    print(f"\n  Произошла непредвиденная ошибка при обработке страницы API {page + 1}: {e}. Прерывание обработки запроса '{query}'.")
                    break

        return current_processed_posts, current_total_size_bytes

    def generate_report_size(results, overall_initial, overall_blacklisted_estimate, overall_processed, overall_total_size, total_duration):
        if not results:
            print("\nНет результатов для создания отчета.")
            return

        results_to_sort = sorted(results, key=lambda item: item[4], reverse=True)

        timestamp = datetime.datetime.now().strftime('%Y.%m.%d-%H.%M.%S')
        first_query_for_filename = sanitize_filename(results_to_sort[0][0]) if results_to_sort else "report"
        report_filename = f"{timestamp}-{first_query_for_filename}.txt"
        report_filepath = os.path.join(reports_dir_path, report_filename)

        print(f"\n--- Создание файла отчета: {report_filepath} ---")

        try:
            with open(report_filepath, 'w', encoding='utf-8') as f:
                f.write("==================================================\n")
                f.write(f"Отчет о подсчете размера файлов на Rule34.net\n")
                f.write(f"Дата и время запуска: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("Метод: HEAD-запросы к файлам с параллелизмом\n")
                f.write(f"Макс. потоков для HEAD запросов: {MAX_HEAD_THREADS}\n")
                f.write("==================================================\n\n")

                f.write("--- Результаты по каждому запросу (отсортировано по размеру) ---\n")
                if not results_to_sort:
                     f.write("Нет результатов по запросам.\n")
                else:
                    for query, initial_count, estimated_blacklisted, processed_count, total_size in results_to_sort:
                        f.write(f"Запрос: '{query}'\n")
                        f.write(f"  По API (без блеклиста): {initial_count} постов.\n")
                        f.write(f"  Предполагаемо отфильтровано блеклистом (оценка): {estimated_blacklisted} постов.\n")
                        f.write(f"  Фактически обработано (получен размер): {processed_count} постов.\n")
                        f.write(f"  Суммарный размер обработанных постов: {format_bytes(total_size)}\n")
                        f.write("-" * 20 + "\n")

                f.write("\n=== Общие результаты за весь запуск ===")
                f.write(f"\n  Общее по API (без блеклиста): {overall_initial} постов.")
                f.write(f"\n  Общая предполагаемая оценка постов в блеклисте: {overall_blacklisted_estimate} постов.")
                f.write(f"\n  Общее фактически обработано: {overall_processed} постов.")
                f.write(f"\n  Общий суммарный размер обработанных постов: {format_bytes(overall_total_size)}\n")

                f.write("\n--- Статистика производительности ---\n")
                f.write(f"  Общее время выполнения: {total_duration:.2f} секунд\n")
                if total_duration > 0 and overall_processed > 0:
                     avg_speed = overall_processed / total_duration
                     f.write(f"  Средняя скорость обработки: {avg_speed:.2f} постов в секунду\n")
                elif overall_processed == 0:
                     f.write("  Средняя скорость обработки: N/A (0 постов обработано)")
                else:
                     f.write("  Средняя скорость обработки: N/A (слишком быстро)\n")

                f.write("========================================")

            print(f"Отчет успешно создан: {report_filepath}")

        except Exception as e:
            print(f"Ошибка при записи файла отчета {report_filepath}: {e}")

    queries_to_process = []
    while True:
        print("\nВыберите метод ввода запроса:")
        print("1: Ввести вручную")
        print(f"2: Загрузить из файла в папке '{os.path.join(module_base_dir, PRESETS_SUBDIR)}'")
        print("0: Назад в главное меню")

        choice = input("Ваш выбор: ")

        if choice == '0':
            return
        elif choice == '1':
            user_query = input("Введите теги (разделяйте пробелами): ")
            if user_query:
                queries_to_process.append(user_query.strip())
            break
        elif choice == '2':
            preset_files = [f for f in os.listdir(presets_dir_path) if os.path.isfile(os.path.join(presets_dir_path, f)) and f.endswith('.txt')]

            if not preset_files:
                print(f"В папке '{os.path.basename(presets_dir_path)}' нет файлов пресетов (.txt).")
                continue
            print(f"\nДоступные файлы пресетов в '{os.path.basename(presets_dir_path)}':")
            for i, fname in enumerate(preset_files):
                print(f"{i + 1}: {fname}")

            while True:
                try:
                    file_choice = input(f"Выберите номер файла пресета (1-{len(preset_files)}): ")
                    file_index = int(file_choice) - 1
                    if 0 <= file_index < len(preset_files):
                        selected_file = preset_files[file_index]
                        preset_queries = read_lines_from_file(os.path.join(presets_dir_path, selected_file))
                        if not preset_queries:
                            print(f"Файл '{selected_file}' пуст или не содержит корректных строк запросов.")
                            continue
                        queries_to_process.extend(preset_queries)
                        print(f"\nЗагружено {len(preset_queries)} запросов из '{selected_file}'.")
                        break
                    else:
                        print("Неверный номер файла.")
                except ValueError:
                    print("Неверный ввод. Введите номер.")
            break
        else:
            print("Неверный выбор. Попробуйте снова.")

    if queries_to_process:
        overall_initial_api_posts = 0
        overall_processed_posts = 0
        overall_total_size_bytes = 0
        query_results = []

        print("\n--- Начало обработки запросов ---")
        start_time = time.time()

        for i, query in enumerate(queries_to_process):
            print(f"\n>>> Обработка запроса {i + 1}/{len(queries_to_process)}: '{query}'")

            initial_count_for_query = get_initial_post_count(query)
            overall_initial_api_posts += initial_count_for_query
            print(f"  По API (без блеклиста) найдено: {initial_count_for_query} постов.")

            processed_count, total_size_bytes = process_query_size(query, blacklist_api_string)

            overall_processed_posts += processed_count
            overall_total_size_bytes += total_size_bytes

            estimated_blacklisted_for_query = initial_count_for_query - processed_count
            estimated_blacklisted_for_query = max(0, estimated_blacklisted_for_query)

            query_results.append((query, initial_count_for_query, estimated_blacklisted_for_query, processed_count, total_size_bytes))

            print(f"\n--- Результаты для запроса '{query}': ---")
            print(f"  По API (без блеклиста): {initial_count_for_query} постов.")
            print(f"  Предполагаемо отфильтровано блеклистом (оценка): {estimated_blacklisted_for_query} постов.")
            print(f"  Фактически обработано (получен размер): {processed_count} постов.")
            print(f"  Суммарный размер обработанных постов: {format_bytes(total_size_bytes)}")
            print("-" * 20)

        end_time = time.time()
        total_duration = end_time - start_time

        print("\n=== Общие результаты за весь запуск ===")
        overall_blacklisted_estimate = overall_initial_api_posts - overall_processed_posts
        overall_blacklisted_estimate = max(0, overall_blacklisted_estimate)

        print(f"  Общее по API (без блеклиста): {overall_initial_api_posts} постов.")
        print(f"  Общая предполагаемая оценка постов в блеклисте: {overall_blacklisted_estimate} постов.")
        print(f"  Общее фактически обработано: {overall_processed_posts} постов.")
        print(f"  Общий суммарный размер обработанных постов: {format_bytes(overall_total_size_bytes)}")

        print("\n--- Статистика производительности ---")
        print(f"  Общее время выполнения: {total_duration:.2f} секунд")
        if total_duration > 0 and overall_processed_posts > 0:
             average_speed = overall_processed_posts / total_duration
             print(f"  Средняя скорость обработки: {average_speed:.2f} постов в секунду")
        elif overall_processed_posts == 0:
             print("  Средняя скорость обработки: N/A (0 постов обработано)")
        else:
             print("  Средняя скорость обработки: N/A (слишком быстро)")
        print("========================================")

        generate_report_size(query_results, overall_initial_api_posts, overall_blacklisted_estimate, overall_processed_posts, overall_total_size_bytes, total_duration)


def run_downloader_module():
    print("\n" + "=" * 50)
    print("ЗАПУЩЕН МОДУЛЬ: АВТО-ЗАГРУЗЧИК")
    print("-" * 50)

    LIMIT_PER_PAGE = 100
    DELAY_SECONDS = 1

    module_base_dir = DOWNLOAD_DIR
    setup_module_directories(module_base_dir, [PRESETS_SUBDIR, CONFIG_SUBDIR, MEDIA_SUBDIR], BLACKLIST_FILENAME)
    presets_dir_path = os.path.join(module_base_dir, PRESETS_SUBDIR)
    config_dir_path = os.path.join(module_base_dir, CONFIG_SUBDIR)
    main_download_dir_path = os.path.join(module_base_dir, MEDIA_SUBDIR)

    blacklist_filepath = os.path.join(config_dir_path, BLACKLIST_FILENAME)
    blacklist_tags = load_blacklist_for_module(module_base_dir)
    is_blacklist_active = bool(blacklist_tags)

    if is_blacklist_active:
        print(f"\nАктивен черный список. Исключаются теги: {', '.join(blacklist_tags)}")
    else:
        print("\nЧерный список не активен (файл не найден или пуст).")

    def get_post_count_dl(tags_query):
        count_params = {
            'page': 'dapi',
            's': 'post',
            'q': 'index',
            'tags': tags_query,
            'limit': 1
        }
        try:
            response = requests.get(BASE_API_URL, params=count_params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            count_str = root.get('count')
            if count_str is not None:
                return int(count_str)
            else:
                posts = root.findall('post')
                if len(posts) > 0:
                    return len(posts)
                else:
                    return 0
        except requests.exceptions.RequestException as e:
            return 0
        except ET.ParseError as e:
            return 0
        except ValueError:
            return 0
        except Exception as e:
            return 0

    tag_queries = []
    choice = None
    while choice not in ['1', '2', '0']:
        print("\nВыберите режим работы:")
        print("1. Ручной ввод тегов")
        print(f"2. Использование пресетов из файлов в папке '{os.path.join(module_base_dir, PRESETS_SUBDIR)}'")
        print("0. Назад в главное меню")
        choice = input("Введите 1, 2 или 0: ").strip()
        if choice not in ['1', '2', '0']:
            print("Неверный ввод.")

    if choice == '0':
        return
    elif choice == '1':
        user_input_tags = input("Введите теги для поиска (несколько тегов через пробел): ").strip()
        if not user_input_tags:
            print("Теги не введены.")
            return
        tag_queries = [user_input_tags]
        print(f"\nВыбран ручной поиск по тегу: '{user_input_tags}'")

    elif choice == '2':
        preset_files = [f for f in os.listdir(presets_dir_path) if f.endswith('.txt') and os.path.isfile(os.path.join(presets_dir_path, f))]

        if not preset_files:
            print(f"\nВ папке '{os.path.basename(presets_dir_path)}' не найдено файлов с пресетами (.txt).")
            print("Пожалуйста, создайте текстовые файлы (с расширением .txt) с тегами (один тег/запрос на строку) в этой папке.")
            return

        print(f"\nДоступные файлы пресетов в папке '{os.path.basename(presets_dir_path)}':")
        for i, filename in enumerate(preset_files):
            print(f"{i + 1}. {filename}")

        selected_index = -1
        while selected_index < 0 or selected_index >= len(preset_files):
            try:
                user_input_index = input(f"Выберите номер файла пресета (1-{len(preset_files)}): ").strip()
                selected_index = int(user_input_index) - 1
                if 0 <= selected_index < len(preset_files):
                     pass
                else:
                     print("Неверный номер.")
                     selected_index = -1 # Сброс для повторного запроса
            except ValueError:
                print("Неверный ввод. Пожалуйста, введите число.")
                selected_index = -1 # Сброс для повторного запроса


        selected_filename = preset_files[selected_index]
        selected_filepath = os.path.join(presets_dir_path, selected_filename)

        tag_queries = read_lines_from_file(selected_filepath)

        if tag_queries is None:
            return
        if not tag_queries:
            print(f"В файле пресета '{selected_filename}' не найдено действительных тегов после фильтрации.")
            return

        if len(tag_queries) > 1:
            print(f"\nВ файле '{selected_filename}' найдено {len(tag_queries)} поисковых запросов.")
            confirmation = input("Начать скачивание для всех запросов? (да/нет): ").lower().strip()
            if confirmation != 'да' and confirmation != 'yes':
                 print("Скачивание отменено.")
                 return
        elif len(tag_queries) == 1:
            print(f"\nВ файле '{selected_filename}' найден 1 поисковый запрос.")

        print(f"\nВыбран поиск по пресету '{selected_filename}'. Будет обработано запросов: {len(tag_queries)}")
        if len(tag_queries) > 1:
            print("Скачивание для каждого запроса начнется автоматически без пауз между ними.")

    total_downloaded = 0
    total_skipped = 0
    total_errors = False
    total_blacklist_eliminated = 0

    try:
        for query_index, current_tag_query in enumerate(tag_queries):
            print(f"\n\n--- Начинаем обработку запроса {query_index + 1}/{len(tag_queries)}: '{current_tag_query}' ---")

            TAGS_FOR_COUNT_BEFORE_BLACKLIST = current_tag_query
            TAGS_FOR_API = current_tag_query

            query_blacklist_eliminated_count = 0

            if is_blacklist_active:
                blacklist_api_string = " ".join(f"-{bt}" for bt in blacklist_tags)
                TAGS_FOR_API = f"{current_tag_query} {blacklist_api_string}"

                count_before_blacklist = get_post_count_dl(TAGS_FOR_COUNT_BEFORE_BLACKLIST)
                print(f"  Общее количество постов для тега '{current_tag_query}' (без черного списка): {count_before_blacklist}")

                count_after_blacklist = get_post_count_dl(TAGS_FOR_API)
                print(f"  Общее количество постов для тега '{current_tag_query}' (с учетом черного списка): {count_after_blacklist}")

                query_blacklist_eliminated_count = max(0, count_before_blacklist - count_after_blacklist)
                print(f"  Количество постов, отфильтрованных черным списком для этого запроса: {query_blacklist_eliminated_count}")

            else:
                print("  Черный список не активен для этого запроса.")
                total_count_for_info = get_post_count_dl(TAGS_FOR_API)
                print(f"  Общее количество постов для тега '{current_tag_query}': {total_count_for_info}")

            sanitized_folder_name = sanitize_folder_name(current_tag_query)
            if not sanitized_folder_name:
                 sanitized_folder_name = f"invalid_tag_{query_index}"
                 print(f"Внимание: Не удалось создать имя папки из тега '{current_tag_query}'. Используется: '{sanitized_folder_name}'")

            tag_download_base_path = os.path.join(main_download_dir_path, sanitized_folder_name)

            should_use_subfolders = not ("video" in current_tag_query.lower() or "gif" in current_tag_query.lower())

            if not should_use_subfolders:
                 destination_for_all_files = tag_download_base_path
                 photo_dir = None
                 video_dir = None
                 gif_dir = None
                 print(f"Запрос содержит 'video' или 'gif'. Все файлы будут сохранены напрямую в папку: '{tag_download_base_path}'")
                 os.makedirs(tag_download_base_path, exist_ok=True)
            else:
                 photo_dir = os.path.join(tag_download_base_path, "фото")
                 video_dir = os.path.join(tag_download_base_path, "видео")
                 gif_dir = os.path.join(tag_download_base_path, GIF_SUBDIR)

                 print(f"Запрос не содержит 'video' или 'gif'. Файлы будут сохранены в подпапки 'фото'/'видео'/'{GIF_SUBDIR}' в: '{tag_download_base_path}'")
                 os.makedirs(photo_dir, exist_ok=True)
                 os.makedirs(video_dir, exist_ok=True)
                 os.makedirs(gif_dir, exist_ok=True)
                 destination_for_all_files = None

            query_downloaded_count = 0
            query_skipped_count = 0
            query_had_error = False

            try:
                page_number = 0

                while True:
                    params = {
                        'page': 'dapi',
                        's': 'post',
                        'q': 'index',
                        'tags': TAGS_FOR_API,
                        'limit': LIMIT_PER_PAGE,
                        'pid': page_number
                    }

                    response_text = None

                    try:
                        print(f"  Загружаем страницу {page_number} для тега '{current_tag_query}'...")
                        response = requests.get(BASE_API_URL, params=params, timeout=REQUEST_TIMEOUT)
                        response.raise_for_status()

                        response_text = response.text
                        if not response_text.strip():
                             print(f"  Получен пустой ответ от API на странице {page_number}. Вероятно, достигнут конец результатов для тега '{current_tag_query}'.")
                             break

                        if not response_text.strip().startswith('<'):
                            print(f"  Получен ответ, не похожий на XML, на странице {page_number} для тега '{current_tag_query}'.")
                            query_had_error = True
                            break

                        try:
                            root = ET.fromstring(response_text)
                            posts = root.findall('post')

                        except ET.ParseError as e:
                            query_had_error = True
                            print(f"  Ошибка парсинга XML на странице {page_number} для тега '{current_tag_query}': {e}")
                            break

                        if not posts:
                            print(f"  API вернул XML без элементов 'post' на странице {page_number}. Результаты закончились для тега '{current_tag_query}'.")
                            break

                        for post_element in posts:
                            file_url = post_element.get('file_url')
                            post_id = post_element.get('id')
                            if post_id is None:
                                continue

                            if not file_url:
                                continue

                            original_file_name = os.path.basename(file_url)
                            file_extension = os.path.splitext(original_file_name)[1].lower()

                            file_name = f"{post_id}{file_extension}"

                            if not should_use_subfolders:
                                 destination_dir = destination_for_all_files
                                 folder_display_name = os.path.basename(destination_dir)
                            else:
                                 if file_extension == GIF_EXTENSION:
                                     destination_dir = gif_dir
                                     folder_display_name = GIF_SUBDIR
                                 elif file_extension in VIDEO_EXTENSIONS_FOR_SORTING:
                                     destination_dir = video_dir
                                     folder_display_name = os.path.basename(video_dir)
                                 else:
                                     destination_dir = photo_dir
                                     folder_display_name = os.path.basename(photo_dir)

                            local_path = os.path.join(destination_dir, file_name)

                            if os.path.exists(local_path):
                                print(f"  Файл '{file_name}' (пост {post_id}) уже существует в папке '{folder_display_name}'. Пропускаем скачивание.")
                                query_skipped_count += 1
                                continue

                            print(f"  Скачиваем: {file_name} (пост {post_id}) (ориг. '{original_file_name}') в папку '{folder_display_name}'")

                            try:
                                with requests.get(file_url, stream=True, timeout=REQUEST_TIMEOUT) as download_response:
                                     download_response.raise_for_status()
                                     with open(local_path, 'wb') as f:
                                         for chunk in download_response.iter_content(chunk_size=8192):
                                             f.write(chunk)

                                query_downloaded_count += 1

                            except requests.exceptions.RequestException as e:
                                query_had_error = True
                                print(f"  Ошибка при скачивании файла '{file_name}' (пост {post_id}): {e}")
                                if os.path.exists(local_path):
                                    try:
                                         os.remove(local_path)
                                    except OSError as cleanup_error:
                                         print(f"  Ошибка при удалении неполного файла '{file_name}': {cleanup_error}")
                            except Exception as e:
                                query_had_error = True
                                print(f"  Неожиданная ошибка при обработке поста {post_id} и файла '{file_name}': {e}")

                    except requests.exceptions.RequestException as e:
                         query_had_error = True
                         print(f"Ошибка при запросе страницы {page_number} для тега '{current_tag_query}': {e}")
                         break

                    except ET.ParseError as e:
                         query_had_error = True
                         print(f"Ошибка парсинга XML на странице {page_number} для тега '{current_tag_query}': {e}")
                         break

                    except Exception as e:
                         query_had_error = True
                         print(f"Произошла непредвиденная ошибка на странице {page_number} для тега '{current_tag_query}': {e}")
                         break

                    page_number += 1
                    time.sleep(DELAY_SECONDS)

            except Exception as e:
                query_had_error = True
                print(f"\nКритическая ошибка при обработке тега '{current_tag_query}': {e}")

            finally:
                print(f"\n--- Отчет по запросу '{current_tag_query}' ---")
                print(f"Скачано новых файлов: {query_downloaded_count}")
                print(f"Пропущено (уже существует): {query_skipped_count}")
                if is_blacklist_active:
                    print(f"Отфильтровано черным списком: {query_blacklist_eliminated_count}")
                if query_had_error:
                     print(f"ВНИМАНИЕ: При обработке запроса '{current_tag_query}' произошли ошибки.")

                total_downloaded += query_downloaded_count
                total_skipped += query_skipped_count
                total_blacklist_eliminated += query_blacklist_eliminated_count
                if query_had_error:
                     total_errors = True

    except Exception as e:
        total_errors = True
        print(f"\n=== КРИТИЧЕСКАЯ ОШИБКА ВЫПОЛНЕНИЯ СКРИПТА: {e} ===")

    finally:
        print("\n\n=== ОБЩИЙ ОТЧЕТ О СКАЧИВАНИИ ===")
        print(f"Всего скачано новых файлов за все запросы: {total_downloaded}")
        print(f"Всего пропущено (файлы уже существуют) за все запросы: {total_skipped}")
        if is_blacklist_active:
             print(f"Всего отфильтровано черным списком: {total_blacklist_eliminated}")
        print(f"Файлы сохранены в папку: '{os.path.abspath(main_download_dir_path)}'")

        if total_errors:
             print("\nВНИМАНИЕ: Во время выполнения скрипта или обработки некоторых запросов произошли ошибки (см. выше).")
        elif total_downloaded == 0 and total_skipped == 0 and (not is_blacklist_active or total_blacklist_eliminated == 0) and tag_queries:
            print("\nПоиск завершен. По указанному(ым) тегу(ам) не найдено подходящих постов или все посты были отфильтрованы блеклистом.")
        elif not tag_queries:
             print("\nНе было запросов для обработки в этом модуле.")
        else:
             print("\nВсе запросы обработаны без критических ошибок.")

def main_menu():
    while True:
        print("\n" + "=" * 50)
        print("ГЛАВНОЕ МЕНЮ")
        print("Выберите программу для запуска:")
        print("-" * 50)
        print(f"1. Модуль: Счетчик количества постов ({COUNT_DIR}/)")
        print(f"2. Модуль: Вычислитель размера медиа файлов ({SIZE_DIR}/)")
        print(f"3. Модуль: Авто-загрузчик медиа файлов ({DOWNLOAD_DIR}/)")
        print("0. Выход")
        print("=" * 50)

        choice = input("Ваш выбор: ").strip()

        if choice == '1':
            run_counter_module()
        elif choice == '2':
            run_size_calculator_module()
        elif choice == '3':
            run_downloader_module()
        elif choice == '0':
            print("Выход из программы.")
            sys.exit()
        else:
            print("Неверный выбор. Пожалуйста, введите 1, 2, 3 или 0.")

if __name__ == "__main__":
    os.makedirs(COUNT_DIR, exist_ok=True)
    os.makedirs(SIZE_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print("Базовые папки модулей готовы.")

    main_menu()