import redis
from config import settings
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_final_diagnostics():
    """
    Выполняет финальную, исправленную диагностику RediSearch.
    """
    logging.info("--- НАЧАЛО ФИНАЛЬНОЙ ДИАГНОСТИКИ REDIS SEARCH ---")

    client_params = {
        'host': settings.REDIS_HOST,
        'port': settings.REDIS_PORT,
        'db': settings.REDIS_DB,
        'password': settings.REDIS_PASSWORD
    }

    try:
        # Для чтения текстовых полей нужен decode_responses=True
        r_text = redis.Redis(**client_params, decode_responses=True)
        r_text.ping()
        logging.info(f"[1/5] Успешное подключение к Redis (Text Mode).")

    except Exception as e:
        logging.error(f"[1/5] НЕ УДАЛОСЬ подключиться к Redis: {e}", exc_info=True)
        return

    index_name = settings.VECTOR_INDEX_NAME

    # --- Шаг 2: Проверка индекса ---
    try:
        index_info = r_text.execute_command("FT.INFO", index_name)
        logging.info(f"[2/5] Индекс '{index_name}' найден.")
        info_dict = {index_info[i]: index_info[i+1] for i in range(0, len(index_info), 2)}
        num_docs = info_dict.get('num_docs', 'N/A')
        logging.info(f"      Количество документов в индексе: {num_docs}")
    except Exception as e:
        logging.error(f"[2/5] НЕ УДАЛОСЬ получить информацию об индексе '{index_name}': {e}")
        return

    # --- Шаг 2.1: Полная информация об индексе ---
    logging.info(f"[2.1/X] Получение полной информации об индексе '{index_name}'...")
    try:
        full_index_info = r_text.execute_command("FT.INFO", index_name)
        logging.info(f"      Полная информация об индексе: {full_index_info}")
    except Exception as e:
        logging.error(f"      Ошибка при получении полной информации об индексе: {e}")

    # --- Шаг 2.2: Широкий поиск по индексу ---
    logging.info(f"[2.2/X] Выполнение широкого поиска по индексу '{index_name}' ('*')...")
    try:
        broad_search_results = r_text.execute_command("FT.SEARCH", index_name, "*")
        if broad_search_results and broad_search_results[0] > 0:
            logging.info(f"      УСПЕХ! Найдено документов (широкий поиск): {broad_search_results[0]}")
            for i in range(1, len(broad_search_results), 2):
                doc_id = broad_search_results[i]
                fields = broad_search_results[i+1]
                logging.info(f"        Документ ID: {doc_id}")
                logging.info(f"        Поля: {fields}")
        else:
            logging.warning("      Широкий поиск не дал результатов.")
    except Exception as e:
        logging.error(f"      Ошибка во время широкого поиска: {e}")

    # --- Шаг 3: Поиск ключей ---
    logging.info("[3/5] Поиск ключей, соответствующих префиксу 'vector:post:*'.")
    indexed_keys = r_text.keys("vector:post:*")
    if not indexed_keys:
        logging.warning("      Не найдено ключей с префиксом 'vector:post:*'.")
    else:
        logging.info(f"      Найдено ключей для индексации: {len(indexed_keys)}")

    # --- Шаг 4: Исправленный анализ содержимого ---
    if indexed_keys:
        logging.info("[4/5] Анализ содержимого ключей (чтение полей по отдельности)...")
        for key in indexed_keys[:3]:
            try:
                # Читаем каждое текстовое поле отдельно, чтобы избежать ошибки с бинарным вектором
                label = r_text.hget(key, 'label')
                title = r_text.hget(key, 'title')
                content_preview = r_text.hget(key, 'content')

                logging.info(f"      Анализ ключа: {key}")
                logging.info(f"        -> label: {label if label else 'НЕ НАЙДЕНО'}")
                logging.info(f"        -> title: {title if title else 'НЕ НАЙДЕНО'}")
                logging.info(f"        -> content: {content_preview[:100] if content_preview else 'НЕ НАЙДЕНО'}...")

            except Exception as e:
                logging.error(f"        Ошибка при чтении полей ключа {key}: {e}")
    else:
        logging.info("[4/5] Пропускаем анализ содержимого, так как ключи не найдены.")

    # --- Шаг 5: Получение содержимого английского поста через HGETALL ---
    english_post_key_hash = "post:ed552ad2-f3ba-4378-b6a6-19bcaf398508"
    logging.info(f"[5/X] Получение содержимого хэша для {english_post_key_hash} через HGETALL...")
    try:
        post_hash_content = r_text.hgetall(english_post_key_hash)
        if post_hash_content:
            logging.info(f"      Содержимое хэша для {english_post_key_hash}: {post_hash_content}")
        else:
            logging.warning(f"      Хэш для {english_post_key_hash} не найден.")
    except Exception as e:
        logging.error(f"      Ошибка при получении содержимого хэша для {english_post_key_hash}: {e}")

    # --- Шаг 6: Очень простой поиск по слову 'RediSearch' без фильтров и подстановочных знаков ---
    logging.info("[6/X] Очень простой поиск по слову 'RediSearch' без фильтров и подстановочных знаков...")
    try:
        query_term = "RediSearch"
        redis_query = f"{query_term}" # No wildcard, no label filter
        logging.info(f"      Выполняем: FT.SEARCH {index_name} '{redis_query}' NOCONTENT")
        search_results = r_text.execute_command(
            "FT.SEARCH",
            index_name,
            redis_query,
            "NOCONTENT"
        )
        if not search_results or search_results[0] == 0:
            logging.warning("      Очень простой поиск по 'RediSearch' не дал результатов.")
        else:
            logging.info(f"      УСПЕХ! Найдено документов: {search_results[0]}")
            logging.info(f"      Найденные ID: {search_results[1:]}")
    except Exception as e:
        logging.error(f"[6/X] Ошибка во время очень простого поиска по 'RediSearch': {e}")

    logging.info("--- ДИАГНОСТИКА ЗАВЕРШЕНА ---")

if __name__ == "__main__":
    run_final_diagnostics()