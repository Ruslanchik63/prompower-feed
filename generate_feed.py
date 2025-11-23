import os
import json
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime

# 1. Получение секретов из переменных окружения GitHub Actions
# Переменные окружения безопасно передаются из GitHub Secrets
API_EMAIL = os.environ.get('API_EMAIL')
API_KEY = os.environ.get('API_KEY')
API_URL = "https://prompower.ru/api/prod/getProducts"

# 2. Определение функции для получения данных
def fetch_product_data():
    """
    Выполняет HTTP POST-запрос к API Prompower для получения каталога товаров.
    """
    if not API_EMAIL or not API_KEY:
        print("Ошибка: Секреты API_EMAIL или API_KEY не найдены.")
        return None

    headers = {
        "Content-Type": "application/json"
    }
    # Обязательные параметры API Prompower
    payload = {
        "email": API_EMAIL,
        "key": API_KEY,
        "format": "json" # Просим данные в формате JSON
    }

    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Вызовет исключение для ошибок HTTP (4xx или 5xx)
        return response.json() # Возвращаем данные в виде Python-объекта (словаря/списка)
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении данных от Prompower API: {e}")
        return None

# 3. Определение функции для генерации XML-фида
def generate_xml_feed(data):
    """
    Преобразует полученные данные в XML-формат, требуемый Industrial.Market (YML).
    """
    # 3.1. Создание корневого элемента
    root = ET.Element("yml_catalog", date=datetime.now().strftime("%Y-%m-%d %H:%M"))
    shop = ET.SubElement(root, "shop")

    # Информация о магазине (замените на свои данные)
    ET.SubElement(shop, "name").text = "Prompower"
    ET.SubElement(shop, "company").text = "Мотрум"
    # Это будет URL вашего GitHub Pages, который будет раздавать сам фид
    ET.SubElement(shop, "url").text = "https://ruslanchik63.github.io/prompower-feed/" 

    # 3.2. Создание категорий (Обычно берется из отдельного GET-запроса, 
    # но для простоты добавим одну фиктивную категорию)
    categories = ET.SubElement(shop, "categories")
    # Предполагаем, что у вас есть одна категория с ID 10
    ET.SubElement(categories, "category", id="10").text = "Оборудование PROMPOWER"
    
    # 3.3. Создание списка предложений (offers)
    offers = ET.SubElement(shop, "offers")
    
    # Предполагаем, что 'data' является словарем с ключом 'products' (или подобным),
    # который содержит список продуктов. Вам может потребоваться изменить 'data.get("products", [])'
    # в зависимости от реальной структуры ответа Prompower API.
    product_list = data.get("products", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    for product in product_list:
        # 3.3.1. Создание тега offer
        # Предполагаем, что у каждого продукта есть 'id' и 'vendorCode'
        offer_id = str(product.get("id", "NO_ID"))
        offer = ET.SubElement(offers, "offer", id=offer_id)

        # 3.3.2. Обязательные поля
        # Используем <vendorCode> для артикула поставщика
        ET.SubElement(offer, "vendorCode").text = product.get("vendorCode", offer_id) 
        
        # Предполагаем, что 'name' - это название продукта
        ET.SubElement(offer, "name").text = product.get("title", "Нет названия")
        
        # Предполагаем, что 'category_id' - это ID категории (числовое)
        # Обязательно сопоставьте это с ID из Industrial.Market (см. Шаг 5)
        ET.SubElement(offer, "categoryId").text = str(product.get("categoryId", "10")) 
        
        # Предполагаем, что 'price' - это цена (числовое значение)
        ET.SubElement(offer, "price").text = str(product.get("price", 0))
        
        # НДС 7% (согласно документации Industrial.Market, это значение '7')
        ET.SubElement(offer, "vat").text = "7" 

        # 3.3.3. Изображение
        # Используйте прямую ссылку! (например, product.get("image_url"))
        ET.SubElement(offer, "picture").text = product.get("image_url", "https://example.com/default.jpg") 

        # 3.3.4. Описание (используем description или full_description)
        ET.SubElement(offer, "description").text = product.get("description", "Описание отсутствует.") 

        # 3.3.5. Остатки на складе (<warehouse>)
        # В Prompower API могут быть только общие остатки (например, 'quantity').
        # В Industrial.Market нужны отдельные теги для складов.
        # Если API дает только общее количество (например, product.get("quantity", 0)):
        quantity = int(product.get("quantity", 0)) 
        
        # Склад 1: Главный
        warehouse1 = ET.SubElement(offer, "warehouse", name="Главный склад", unit="шт")
        warehouse1.text = str(quantity) # Используем все остатки
        
        # Склад 2: Например, "Склад Москва" (если нет данных, ставим 0)
        warehouse2 = ET.SubElement(offer, "warehouse", name="Склад Москва", unit="шт")
        warehouse2.text = "0"

        # 3.3.6. Характеристики (<param>)
        # Предполагаем, что характеристики хранятся в 'params' (список или словарь)
        # Если Prompower API возвращает характеристики (например, Вес, Габариты):
        weight = product.get("weight_kg") # Пример: 14
        if weight:
             ET.SubElement(offer, "param", name="Вес", unit="кг").text = str(weight)
        
        dimensions = product.get("dimensions_mm") # Пример: 940x230x520
        if dimensions:
             ET.SubElement(offer, "param", name="Габариты", unit="мм").text = str(dimensions)
        
        # 3.3.7. Под заказ (<preorder>)
        # 1 - доступно под заказ, 0 - нет
        # Предполагаем, что 'available' = False, если остатки < 1, но можно заказать
        preorder_status = "1" if quantity < 1 and product.get("can_preorder", True) else "0"
        ET.SubElement(offer, "preorder").text = preorder_status

    # 3.4. Форматирование и запись XML-файла
    rough_string = ET.tostring(root, 'utf-8')
    # Добавляем красивое форматирование и XML-декларацию
    reparsed = minidom.parseString(rough_string)
    pretty_xml_as_string = reparsed.toprettyxml(indent="  ", encoding="utf-8").decode('utf-8')
    
    # Удаляем лишние пустые строки, которые иногда добавляет minidom
    pretty_xml_as_string = '\n'.join([line for line in pretty_xml_as_string.split('\n') if line.strip()])

    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(pretty_xml_as_string)
    
    print("Файл feed.xml успешно сгенерирован.")

# 4. Основная логика
if __name__ == "__main__":
    product_data = fetch_product_data()
    if product_data:
        generate_xml_feed(product_data)
