import os
import json
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime

# ==============================================================================
# КОНФИГУРАЦИЯ
# ==============================================================================
API_EMAIL = os.environ.get('API_EMAIL')
API_KEY = os.environ.get('API_KEY')
BASE_URL = "https://prompower.ru/api"
PRODUCTS_API_URL = f"{BASE_URL}/prod/getProducts"
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
        
        # Добавляем обязательные параметры аутентификации для метода getProducts
        post_payload = {
            "email": API_EMAIL,
            "key": API_KEY,
            "format": "json" 
        }
        if payload:
            post_payload.update(payload) # Если нужны дополнительные параметры
            
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
# ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ XML-ФИДА
# ==============================================================================
def generate_xml_feed(products_data, categories_data):
    """
    Преобразует полученные данные в XML-формат, требуемый Industrial.Market (YML).
    """
    # 1. Создание корневого элемента
    root = ET.Element("yml_catalog", date=datetime.now().strftime("%Y-%m-%d %H:%M"))
    shop = ET.SubElement(root, "shop")

    # Информация о магазине (замените на свои данные)
    ET.SubElement(shop, "name").text = "Prompower"
    ET.SubElement(shop, "company").text = "Мотрум"
    # URL, по которому будет доступен фид
    ET.SubElement(shop, "url").text = "https://Ruslanchik63.github.io/prompower-feed/" 

    # 2. Создание категорий (Categories)
    categories_element = ET.SubElement(shop, "categories")
    
    # Предполагаем, что categories_data - это список объектов категорий
    # Проверка, что categories_data является списком
    if isinstance(categories_data, list):
        for category in categories_data:
            # Требование 1: Прописать все категории из API Prompower
            category_id = str(category.get("id"))
            category_title = category.get("title")
            
            if category_id and category_title:
                ET.SubElement(categories_element, "category", id=category_id).text = category_title

    # 3. Создание списка предложений (offers)
    offers = ET.SubElement(shop, "offers")
    
    # Проверка, что products_data является списком (или словарем с нужным ключом)
    product_list = products_data if isinstance(products_data, list) else products_data.get("products", [])

    for product in product_list:
        
        # Требование 2: offer id берем из "id" продукта
        offer_id = str(product.get("id", "NO_ID"))
        
        # Пропускаем товар, если нет ID (серьезная проблема)
        if offer_id == "NO_ID":
            print(f"Внимание: Продукт без ID пропущен.")
            continue
            
        offer = ET.SubElement(offers, "offer", id=offer_id)

        # Требование 3: vendorCode соответствует "article" (арт. производителя)
        vendor_code = product.get("article", offer_id) # Предполагаем ключ "article" в API
        ET.SubElement(offer, "vendorCode").text = vendor_code
        
        # Название продукта
        ET.SubElement(offer, "name").text = product.get("title", f"Продукт {offer_id}")
        
        # ID категории
        ET.SubElement(offer, "categoryId").text = str(product.get("categoryId", "10")) 
        
        # Цена (предполагаем ключ "price")
        ET.SubElement(offer, "price").text = str(product.get("price", 0))
        
        # НДС 7% (согласно документации Industrial.Market, это значение '7')
        ET.SubElement(offer, "vat").text = "7" 

        # Требование 4: step-quantity всегда "1"
        ET.SubElement(offer, "step-quantity").text = "1"
        
        # Требование 5: brand всегда "Prompower"
        ET.SubElement(offer, "brand").text = "Prompower"
        
        # Требование 6: vendor всегда "Prompower"
        ET.SubElement(offer, "vendor").text = "Prompower"

        # Требование 7: picture берем из "picture"
        picture_url = product.get("picture", product.get("image")) # Пробуем "picture", если нет - "image"
        if picture_url:
             # Проверяем, что это полный URL, иначе добавляем BASE_URL, если нужно
             # (В Prompower XML указаны полные URL, так что используем как есть)
             ET.SubElement(offer, "picture").text = picture_url 

        # Требование 11: description берем из "description"
        description = product.get("description", "Описание отсутствует.") 
        if description:
            ET.SubElement(offer, "description").text = description 

        # Требование 8: warehouse name "Склад Самара Prompower и Unimat", значение из "instock"
        quantity = int(product.get("instock", 0)) # Предполагаем ключ "instock" в API
        
        warehouse = ET.SubElement(offer, "warehouse", name="Склад Самара Prompower и Unimat", unit="шт")
        warehouse.text = str(quantity)
        
        # Под заказ (<preorder>) - логика остается прежней (под заказ, если 0 на складе)
        preorder_status = "1" if quantity < 1 else "0"
        ET.SubElement(offer, "preorder").text = preorder_status

        # Требование 9: param Вес из "weight"
        weight = product.get("weight") # Предполагаем ключ "weight" в API
        if weight:
             ET.SubElement(offer, "param", name="Вес", unit="кг").text = str(weight)
        
        # Требование 10: param Габариты из height x width x depth
        height = product.get("height")
        width = product.get("width")
        depth = product.get("depth")
        
        if height and width and depth:
             dimensions = f"{height}x{width}x{depth}"
             ET.SubElement(offer, "param", name="Габариты", unit="мм").text = dimensions
        
    # 4. Форматирование и запись XML-файла
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml_as_string = reparsed.toprettyxml(indent="  ", encoding="utf-8").decode('utf-8')
    
    pretty_xml_as_string = '\n'.join([line for line in pretty_xml_as_string.split('\n') if line.strip()])

    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(pretty_xml_as_string)
    
    print("Файл feed.xml успешно сгенерирован.")

# ==============================================================================
# ОСНОВНАЯ ЛОГИКА ЗАПУСКА
# ==============================================================================
if __name__ == "__main__":
    # 1. Получаем список категорий
    categories = fetch_data(CATEGORIES_API_URL, is_post=False)
    if not categories:
        print("Не удалось получить категории. Завершение.")
        exit(1)
        
    # 2. Получаем список товаров
    # Запрос POST, использует API_EMAIL и API_KEY
    products = fetch_data(PRODUCTS_API_URL, is_post=True)
    if not products:
        print("Не удалось получить продукты. Завершение.")
        exit(1)
        
    # 3. Генерируем XML
    generate_xml_feed(products, categories)
