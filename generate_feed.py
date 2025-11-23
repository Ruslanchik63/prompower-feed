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
# ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ XML-ФИДА
# ==============================================================================
def generate_xml_feed(products_data, categories_data):
    """
    Преобразует полученные данные в XML-формат, требуемый Industrial.Market (YML).
    """
    # 1. Создание корневого элемента и тега shop
    root = ET.Element("yml_catalog", date=datetime.now().strftime("%Y-%m-%d %H:%M"))
    shop = ET.SubElement(root, "shop")

    # УТОЧНЕНИЕ: Информация о магазине
    ET.SubElement(shop, "name").text = "Prompower" # Требование: Prompower
    ET.SubElement(shop, "company").text = "Мотрум" # Требование: Мотрум
    # Требование: Полный URL вашего GitHub Pages
    ET.SubElement(shop, "url").text = "https://Ruslanchik63.github.io/prompower-feed/" 

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
    
    product_list = products_data if isinstance(products_data, list) else products_data.get("products", [])

    for product in product_list:
        
        # КОРРЕКТИРОВКА: offer id и vendorCode берем из "article"
        offer_id_or_article = product.get("article") # Используем article в качестве уникального ID
        
        if not offer_id_or_article:
            # Если article нет, то продукт пропустить не можем, но выведем предупреждение
            print(f"Внимание: Продукт без 'article' пропущен.")
            continue
            
        offer_id = str(offer_id_or_article)
        offer = ET.SubElement(offers, "offer", id=offer_id)

        # vendorCode - также article
        ET.SubElement(offer, "vendorCode").text = offer_id

        # Название продукта
        ET.SubElement(offer, "name").text = product.get("title", f"Продукт {offer_id}")
        
        # ID категории
        ET.SubElement(offer, "categoryId").text = str(product.get("categoryId", "10")) 
        
        # Цена (предполагаем ключ "price")
        ET.SubElement(offer, "price").text = str(product.get("price", 0))
        
        # НДС 7% (фиксированное значение)
        ET.SubElement(offer, "vat").text = "7" 

        # step-quantity всегда "1"
        ET.SubElement(offer, "step-quantity").text = "1"
        
        # brand всегда "Prompower"
        ET.SubElement(offer, "brand").text = "Prompower"
        
        # vendor всегда "Prompower"
        ET.SubElement(offer, "vendor").text = "Prompower"

        # picture берем из "picture"
        picture_url = product.get("picture", product.get("image"))
        if picture_url:
             ET.SubElement(offer, "picture").text = picture_url 

        # description берем из "description"
        description = product.get("description")
        if description:
            ET.SubElement(offer, "description").text = description 

        # warehouse name "Склад Самара Prompower и Unimat", значение из "instock"
        quantity = int(product.get("instock", 0))
        
        warehouse = ET.SubElement(offer, "warehouse", name="Склад Самара Prompower и Unimat", unit="шт")
        warehouse.text = str(quantity)
        
        # Под заказ (<preorder>)
        preorder_status = "1" if quantity < 1 and product.get("can_preorder", True) else "0"
        ET.SubElement(offer, "preorder").text = preorder_status

        # param Вес из "weight"
        weight = product.get("weight")
        if weight:
             ET.SubElement(offer, "param", name="Вес", unit="кг").text = str(weight)
        
        # param Габариты из height x width x depth
        height = product.get("height")
        width = product.get("width")
        depth = product.get("depth")
        
        if height and width and depth:
             # Формат: 940x230x520
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
    products = fetch_data(PRODUCTS_API_URL, is_post=True)
    if not products:
        print("Не удалось получить продукты. Завершение.")
        exit(1)
        
    # 3. Генерируем XML
    generate_xml_feed(products, categories)
