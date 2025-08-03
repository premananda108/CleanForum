import redis
import json
import time

# Подключение к Redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)


def check_redis_connection():
    """Проверяем подключение к Redis"""
    try:
        r.ping()
        print("Подключение к Redis работает")
        return True
    except Exception as e:
        print(f"Ошибка подключения к Redis: {e}")
        return False


def find_search_indexes():
    """Находим все поисковые индексы"""
    try:
        indexes = r.execute_command("FT._LIST")
        print(f"Найдено индексов: {len(indexes)}")
        for i, idx in enumerate(indexes):
            index_name = idx.decode('utf-8') if isinstance(idx, bytes) else str(idx)
            print(f"  {i + 1}. {index_name}")
        return [idx.decode('utf-8') if isinstance(idx, bytes) else str(idx) for idx in indexes]
    except Exception as e:
        print(f"Ошибка получения списка индексов: {e}")
        print("Возможно, RediSearch не установлен или не загружен")
        return []


def check_post_data():
    """Проверяем, есть ли посты в Redis"""
    try:
        post_keys = r.keys("post:*")
        print(f"Найдено ключей постов: {len(post_keys)}")

        if post_keys:
            for i, key in enumerate(post_keys[:3]):
                print(f"  {i + 1}. {key}")
                post_data = r.hgetall(key)
                if post_data:
                    title = post_data.get('title', 'Без названия')[:50]
                    status = post_data.get('status', 'unknown')
                    print(f"     Заголовок: {title}...")
                    print(f"     Статус: {status}")
                print()

        return len(post_keys)
    except Exception as e:
        print(f"Ошибка проверки постов: {e}")
        return 0


def simple_search_any_index(query="*"):
    """Пробуем поиск в любом найденном индексе"""
    indexes = find_search_indexes()

    if not indexes:
        print("Индексы для поиска не найдены")
        return None

    for index_name in indexes:
        print(f"\nПробуем поиск в индексе: {index_name}")
        try:
            result = r.execute_command("FT.SEARCH", index_name, query, "LIMIT", 0, 5)

            if result and result[0] > 0:
                print(f"Найдено результатов: {result[0]}")

                for i in range(1, len(result), 2):
                    if i + 1 < len(result):
                        doc_id = result[i]
                        if isinstance(doc_id, bytes):
                            doc_id = doc_id.decode('utf-8')

                        print(f"  Документ: {doc_id}")

                        if i + 1 < len(result):
                            doc_fields = result[i + 1]
                            if doc_fields:
                                for j in range(0, min(len(doc_fields), 6), 2):
                                    if j + 1 < len(doc_fields):
                                        field_name = doc_fields[j]
                                        field_value = doc_fields[j + 1]

                                        if isinstance(field_name, bytes):
                                            field_name = field_name.decode('utf-8')
                                        if isinstance(field_value, bytes):
                                            field_value = field_value.decode('utf-8')

                                        if len(str(field_value)) > 100:
                                            field_value = str(field_value)[:100] + "..."

                                        print(f"    {field_name}: {field_value}")
                        print()

                return result
            else:
                print(f"В индексе {index_name} ничего не найдено")

        except Exception as e:
            print(f"Ошибка поиска в индексе {index_name}: {e}")

    return None


def search_posts_direct(query="*"):
    """Прямой поиск постов без индекса"""
    print(f"\nПрямой поиск постов по запросу: '{query}'")

    try:
        post_keys = r.keys("post:*")

        if not post_keys:
            print("Посты не найдены")
            return []

        found_posts = []

        for key in post_keys:
            post_data = r.hgetall(key)
            if not post_data:
                continue

            title = post_data.get('title', '')
            content = post_data.get('content', '')
            status = post_data.get('status', '')

            if query == "*" or query.lower() in title.lower() or query.lower() in content.lower():
                found_posts.append({
                    'key': key,
                    'title': title,
                    'content': content[:200] + "..." if len(content) > 200 else content,
                    'status': status
                })

        print(f"Найдено постов: {len(found_posts)}")

        for i, post in enumerate(found_posts[:5]):
            print(f"\n  {i + 1}. {post['key']}")
            print(f"     Заголовок: {post['title']}")
            print(f"     Статус: {post['status']}")
            if post['content']:
                print(f"     Содержимое: {post['content']}")

        if len(found_posts) > 5:
            print(f"     ... и еще {len(found_posts) - 5} постов")

        return found_posts

    except Exception as e:
        print(f"Ошибка прямого поиска: {e}")
        return []


def create_simple_test_index():
    """Создаем простой тестовый индекс"""
    print("\nСоздаем тестовый индекс...")

    try:
        try:
            r.execute_command('FT.DROPINDEX', 'test_posts')
        except:
            pass

        r.execute_command(
            'FT.CREATE', 'test_posts',
            'ON', 'HASH',
            'PREFIX', '1', 'testpost:',
            'SCHEMA',
            'title', 'TEXT',
            'content', 'TEXT'
        )

        print("Тестовый индекс создан")

        test_posts = [
            {"title": "Python программирование", "content": "Изучаем Python для начинающих"},
            {"title": "Redis поиск", "content": "Как настроить поиск в Redis"},
            {"title": "JavaScript основы", "content": "Основы веб-разработки"}
        ]

        for i, post in enumerate(test_posts):
            r.hset(f"testpost:{i}", mapping=post)

        print(f"Добавлено {len(test_posts)} тестовых постов")

        time.sleep(1)

        print("\nТестируем поиск в новом индексе:")
        result = r.execute_command("FT.SEARCH", "test_posts", "Python", "LIMIT", 0, 3)

        if result and result[0] > 0:
            print(f"Поиск работает! Найдено: {result[0]}")
            return True
        else:
            print("Поиск не работает")
            return False

    except Exception as e:
        print(f"Ошибка создания тестового индекса: {e}")
        return False


def main():
    """Главная функция - проверяем все по порядку"""
    print("ДИАГНОСТИКА REDIS SEARCH")
    print("=" * 50)

    if not check_redis_connection():
        return

    post_count = check_post_data()

    print(f"\nПоиск существующих индексов:")
    indexes = find_search_indexes()

    if indexes:
        print(f"\nПробуем поиск во всех индексах:")
        simple_search_any_index("*")

        if post_count > 0:
            simple_search_any_index("Python")

    if post_count > 0:
        search_posts_direct("*")
        search_posts_direct("Python")

    if not indexes or post_count == 0:
        print(f"\nИндексов нет или постов нет. Создаем тестовый пример:")
        create_simple_test_index()


if __name__ == "__main__":
    main()


def quick_search(query="*", index_name=None):
    """Быстрый поиск для ручного вызова"""
    if not index_name:
        indexes = find_search_indexes()
        if not indexes:
            print("Индексы не найдены")
            return None
        index_name = indexes[0]

    try:
        result = r.execute_command("FT.SEARCH", index_name, query, "LIMIT", 0, 5)
        print(f"Найдено в {index_name}: {result[0] if result else 0}")
        return result
    except Exception as e:
        print(f"Ошибка: {e}")
        return None


def list_all_keys():
    """Показать все ключи в Redis"""
    try:
        keys = r.keys("*")
        print(f"Всего ключей в Redis: {len(keys)}")

        types = {}
        for key in keys[:50]:
            key_type = r.type(key)
            if key_type not in types:
                types[key_type] = []
            types[key_type].append(key)

        for key_type, key_list in types.items():
            print(f"\n{key_type.upper()} ({len(key_list)}):")
            for key in key_list[:10]:
                print(f"  {key}")
            if len(key_list) > 10:
                print(f"  ... и еще {len(key_list) - 10}")

    except Exception as e:
        print(f"Ошибка: {e}")


print("""
КАК ИСПОЛЬЗОВАТЬ:

1. Запустите весь скрипт:
   python script.py

2. Или вызывайте функции вручную:
   quick_search("Python")
   search_posts_direct("Redis")
   list_all_keys()
   find_search_indexes()

3. Если ничего не работает:
   create_simple_test_index()
""")