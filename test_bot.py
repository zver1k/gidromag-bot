#!/usr/bin/env python3
"""
Скрипт для тестирования бота локально
"""

import os
import sys
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_environment():
    """Проверяет переменные окружения"""
    print("🔍 Проверка переменных окружения...")
    
    required_vars = ['TELEGRAM_TOKEN', 'YANDEX_DISK_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 10)}...")
        else:
            print(f"❌ {var}: НЕ НАЙДЕН")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ Отсутствуют обязательные переменные: {', '.join(missing_vars)}")
        print("Установите их командой:")
        for var in missing_vars:
            print(f"export {var}='your_token_here'")
        return False
    
    print("\n✅ Все переменные окружения настроены")
    return True

def test_imports():
    """Проверяет импорты модулей"""
    print("\n📦 Проверка импортов...")
    
    try:
        import telegram
        print(f"✅ python-telegram-bot: {telegram.__version__}")
    except ImportError as e:
        print(f"❌ python-telegram-bot: {e}")
        return False
    
    try:
        import yadisk
        print(f"✅ yadisk: {yadisk.__version__}")
    except ImportError as e:
        print(f"❌ yadisk: {e}")
        return False
    
    try:
        import requests
        print(f"✅ requests: {requests.__version__}")
    except ImportError as e:
        print(f"❌ requests: {e}")
        return False
    
    print("\n✅ Все модули успешно импортированы")
    return True

def test_yandex_connection():
    """Тестирует подключение к Яндекс.Диску"""
    print("\n🌐 Тест подключения к Яндекс.Диску...")
    
    try:
        import yadisk
        token = os.environ.get('YANDEX_DISK_TOKEN')
        y = yadisk.YaDisk(token=token)
        
        # Получаем информацию о диске
        disk_info = y.get_disk_info()
        free_gb = disk_info.free // (1024**3)
        total_gb = disk_info.total // (1024**3)
        used_percent = round((disk_info.total - disk_info.free) / disk_info.total * 100, 1)
        
        print(f"✅ Подключение установлено")
        print(f"   💾 Свободно: {free_gb}GB")
        print(f"   💾 Всего: {total_gb}GB")
        print(f"   📊 Использовано: {used_percent}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🧪 Тестирование Telegram бота\n")
    
    # Проверяем переменные окружения
    if not test_environment():
        sys.exit(1)
    
    # Проверяем импорты
    if not test_imports():
        sys.exit(1)
    
    # Тестируем подключение к Яндекс.Диску
    if not test_yandex_connection():
        sys.exit(1)
    
    print("\n🎉 Все тесты пройдены успешно!")
    print("Бот готов к запуску командой: python bot.py")

if __name__ == "__main__":
    main()
