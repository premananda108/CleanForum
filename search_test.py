import redis
from config import settings
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def drop_search_index():
    """
    Удаляет поисковый индекс для его последующего полного пересоздания.
    """
    logging.info("--- НАЧАЛО ОПЕРАЦИИ ПО УДАЛЕНИЮ ИНДЕКСА ---")
    
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD
        )
        r.ping()
        logging.info("Успешное подключение к Redis.")

    except Exception as e:
        logging.error(f"НЕ УДАЛОСЬ подключиться к Redis: {e}")
        return

    index_name = settings.VECTOR_INDEX_NAME

    try:
        logging.warning(f"Попытка удалить индекс: {index_name}...")
        r.execute_command("FT.DROPINDEX", index_name, "DD")
        logging.info(f"ИНДЕКС '{index_name}' УСПЕШНО УДАЛЕН.")
        logging.info("Теперь необходимо перезапустить основное приложение, чтобы оно создало новый, чистый индекс.")
    except Exception as e:
        # Если индекс не существует, Redis вернет ошибку, это нормально.
        logging.error(f"Не удалось удалить индекс '{index_name}' (возможно, он уже не существует): {e}")

    logging.info("--- ОПЕРАЦИЯ ЗАВЕРШЕНА ---")

if __name__ == "__main__":
    if input("Вы уверены, что хотите НАВСЕГДА удалить поисковый индекс '{}'? (yes/no): ".format(settings.VECTOR_INDEX_NAME)).lower() == 'yes':
        drop_search_index()
    else:
        print("Операция отменена.")