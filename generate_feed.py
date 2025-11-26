import os
import json
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime

# ==============================================================================
# КОНФИГУРАЦИЯ И СЕКРЕТЫ
# ==============================================================================
API_EMAIL = os.environ.get('API_EMAIL')
API_KEY = os.environ.get('API_KEY')
BASE_URL = "https://prompower.ru/api"
EXTERNAL_FEED_URL = "https://prompower.ru/feed.xml" # Источник картинок

# URL-ы для продуктов
PRODUCTS_API = {
    "Prompower": f"{BASE_URL}/prod/getProducts",
    "Unimat": f"{BASE_URL}/prod/getUnimatProducts"
}

CATEGORIES_API_URL = f"{BASE_URL}/categories"

# ==============================================================================
# ФУНКЦИЯ ДЛЯ ВЫПОЛНЕНИЯ API-ЗАПРОСА
# ==============================================================================
def fetch_data(url, is_post=False, payload=None):
    """
    Выполняет HTTP-запрос (GET или POST) к API Prompower.
    """
    headers = {"Content-Type": "application/json"}
    
    if is_post:
        if not API_EMAIL or not API_KEY:
            print("Ошибка: Секреты API_EMAIL или API_KEY не найдены для POST-запроса.")
            return None
        
        post_payload = {
            "email": API_EMAIL,
            "key": API_KEY,
            "format": "json" 
        }
        if payload:
            post_payload.update(payload)
            
        try:
            response = requests.post(url, headers=headers, data=json.dumps(post_payload))
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при выполнении POST-запроса к {url}: {e}")
            return None
    else: # GET-запрос для категорий
        try:
            response = requests.get(url, headers=headers)
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при выполнении GET-запроса к {url}: {e}")
            return None

    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Ошибка при получении данных от {url}: {e}")
        print(f"Ответ сервера: {response.text}")
        return None
    except json.JSONDecodeError:
        print(f"Ошибка декодирования JSON для {url}. Ответ: {response.text[:200]}...")
        return None

# ==============================================================================
# ФУНКЦИЯ ДЛЯ ЗАГРУЗКИ КАРТИНОК ИЗ ВНЕШНЕГО XML
# ==============================================================================
def fetch_external_images_map():
    """
    Скачивает feed.xml с prompower.ru и создает словарь {offer_id: picture_url}.
    """
    print(f"Загрузка внешнего XML для картинок: {EXTERNAL_FEED_URL}...")
    try:
        response = requests.get(EXTERNAL_FEED_URL)
        response.raise_for_status()
        
        # Парсим XML
        root = ET.fromstring(response.content)
        
        images_map = {}
        # Ищем все теги offer
        for offer in root.findall(".//offer"):
            offer_id = offer.get("id")
            picture_tag = offer.find("picture")
            
            if offer_id and picture_tag is not None and picture_tag.text:
                # Сохраняем в словарь: Ключ - ID, Значение - URL картинки
                images_map[offer_id] = picture_tag.text.strip()
                
        print(f"Успешно загружено {len(images_map)} изображений из внешнего XML.")
        return images_map

    except Exception as e:
        print(f"Ошибка при загрузке или парсинге внешнего XML ({EXTERNAL_FEED_URL}): {e}")
        return {} # Возвращаем пустой словарь, чтобы скрипт не упал

# ==============================================================================
# ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ВСЕХ ПРОДУКТОВ
# ==============================================================================
def fetch_all_products():
    """
    Получает продукты Prompower и UniMAT и добавляет поле 'source_brand'.
    """
    all_products = []
    
    for brand_name, api_url in PRODUCTS_API.items():
        print(f"Загрузка продуктов для бренда: {brand_name}...")
        products_data = fetch_data(api_url, is_post=True)
        
        if not products_data:
            print(f"Не удалось получить продукты для {brand_name}. Пропускаем.")
            continue
            
        product_list = products_data if isinstance(products_data, list) else products_data.get("products", [])
        
        # Добавляем поле для определения бренда/вендора при генерации XML
        for product in product_list:
            product['source_brand'] = brand_name
        
        all_products.extend(product_list)
        print(f"Загружено {len(product_list)} продуктов для {brand_name}.")

    return all_products

# ==============================================================================
# ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ XML-ФИДА
# ==============================================================================
def generate_xml_feed(products_list, categories_data, images_map):
    """
    Преобразует полученные данные в XML-формат.
    """
    # 1. Создание корневого элемента и тега shop
    root = ET.Element("yml_catalog", date=datetime.now().strftime("%Y-%m-%d %H:%M"))
    shop = ET.SubElement(root, "shop")

    # Информация о магазине
    ET.SubElement(shop, "name").text = "Prompower"
    ET.SubElement(shop, "company").text = "Мотрум"
    ET.SubElement(shop, "url").text = "https://brilka.github.io/prompower-feed/" 

    # 2. Создание категорий (Categories)
    categories_element = ET.SubElement(shop, "categories")
    
    if isinstance(categories_data, list):
        for category in categories_data:
            category_id = str(category.get("id"))
            category_title = category.get("title")
            
            if category_id and category_title:
                ET.SubElement(categories_element, "category", id=category_id).text = category_title

    # 3. Создание списка предложений (offers)
    offers = ET.SubElement(shop, "offers")
    
    # Счетчик добавленных товаров
    added_count = 0
    
    for product in products_list:
        
        offer_id_or_article = product.get("article")
        
        if not offer_id_or_article:
            continue
            
        # --- ФИЛЬТРАЦИЯ ПО ЦЕНЕ ---
        try:
            price_value = float(product.get("price", 0))
        except (ValueError, TypeError):
            price_value = 0

        # Если цена 0 или меньше, пропускаем
        if price_value <= 0:
            continue
        # --------------------------

        offer_id = str(offer_id_or_article)
        offer = ET.SubElement(offers, "offer", id=offer_id)
        added_count += 1

        # 3.1. Обязательные поля
        
        ET.SubElement(offer, "vendorCode").text = offer_id
        ET.SubElement(offer, "name").text = product.get("title", f"Продукт {offer_id}")
        ET.SubElement(offer, "categoryId").text = str(product.get("categoryId", "10")) 
        ET.SubElement(offer, "price").text = str(product.get("price", 0))
        ET.SubElement(offer, "vat").text = "7" 
        ET.SubElement(offer, "step-quantity").text = "1"
        ET.SubElement(offer, "preorder").text = "1" 

        # 3.2. Настройка brand и vendor
        source_brand = product.get('source_brand', 'Prompower')
        
        if source_brand == "Unimat":
            brand_name = "Unimat"
            vendor_name = "Unimat"
        else:
            brand_name = "Prompower"
            vendor_name = "Prompower"
            
        ET.SubElement(offer, "brand").text = brand_name
        ET.SubElement(offer, "vendor").text = vendor_name

        # 3.3. Остальные поля
        
        # --- ИЗОБРАЖЕНИЕ (ИЗ ВНЕШНЕГО XML) ---
        # Пытаемся найти URL картинки в словаре images_map по offer_id (артикулу)
        external_image = images_map.get(offer_id)
        
        if external_image:
            # Если нашли во внешнем XML - используем его (приоритет)
            ET.SubElement(offer, "picture").text = external_image
        else:
            # Если не нашли, пробуем взять из API как запасной вариант
            api_image = product.get("picture", product.get("image"))
            if api_image:
                ET.SubElement(offer, "picture").text = api_image
        # -------------------------------------

        # description
        description = product.get("description")
        if description:
            ET.SubElement(offer, "description").text = description 

        # warehouse
        quantity = int(product.get("instock", 0))
        warehouse = ET.SubElement(offer, "warehouse", name="Главный склад Prompower и Unimat", unit="шт")
        warehouse.text = str(quantity)
        
        # param Вес
        weight = product.get("weight")
        if weight:
             ET.SubElement(offer, "param", name="Вес", unit="кг").text = str(weight)
        
        # param Габариты
        height = product.get("height")
        width = product.get("width")
        depth = product.get("depth")
        
        if height and width and depth:
             dimensions = f"{height}x{width}x{depth}"
             ET.SubElement(offer, "param", name="Габариты", unit="мм").text = dimensions
        
    # 4. Форматирование и запись
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml_as_string = reparsed.toprettyxml(indent="  ", encoding="utf-8").decode('utf-8')
    
    pretty_xml_as_string = '\n'.join([line for line in pretty_xml_as_string.split('\n') if line.strip()])

    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(pretty_xml_as_string)
    
    print(f"Файл feed.xml успешно сгенерирован. Добавлено товаров: {added_count}")

# ==============================================================================
# ОСНОВНАЯ ЛОГИКА ЗАПУСКА
# ==============================================================================
if __name__ == "__main__":
    # 1. Получаем список категорий
    categories = fetch_data(CATEGORIES_API_URL, is_post=False)
    if not categories:
        print("Не удалось получить категории. Завершение.")
        exit(1)

    # 2. Получаем словарь картинок из внешнего XML (Prompower feed)
    images_map = fetch_external_images_map()
        
    # 3. Получаем список всех товаров (API)
    all_products = fetch_all_products()
    if not all_products:
        print("Не удалось получить ни одного продукта. Завершение.")
        exit(1)
        
    # 4. Генерируем XML (передаем и продукты, и категории, и словарь картинок)
    generate_xml_feed(all_products, categories, images_map)
