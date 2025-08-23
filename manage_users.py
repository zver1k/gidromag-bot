#!/usr/bin/env python3
"""
Скрипт для управления пользователями бота через командную строку
"""

import os
import sys
import argparse

def load_users():
    """Загружает список пользователей из файла"""
    users_file = "allowed_users.txt"
    if os.path.exists(users_file):
        with open(users_file, 'r', encoding='utf-8') as f:
            return [int(line.strip()) for line in f if line.strip().isdigit()]
    return []

def save_users(users):
    """Сохраняет список пользователей в файл"""
    users_file = "allowed_users.txt"
    with open(users_file, 'w', encoding='utf-8') as f:
        for user_id in sorted(users):
            f.write(f"{user_id}\n")

def add_user(user_id):
    """Добавляет пользователя"""
    users = load_users()
    if user_id in users:
        print(f"❌ Пользователь {user_id} уже существует")
        return False
    
    users.append(user_id)
    save_users(users)
    print(f"✅ Пользователь {user_id} добавлен")
    return True

def remove_user(user_id):
    """Удаляет пользователя"""
    users = load_users()
    if user_id not in users:
        print(f"❌ Пользователь {user_id} не найден")
        return False
    
    users.remove(user_id)
    save_users(users)
    print(f"✅ Пользователь {user_id} удален")
    return True

def list_users():
    """Показывает список пользователей"""
    users = load_users()
    if not users:
        print("📋 Список пользователей пуст")
        return
    
    print(f"📋 Список пользователей ({len(users)}):")
    for i, user_id in enumerate(users, 1):
        print(f"  {i}. {user_id}")

def main():
    parser = argparse.ArgumentParser(description="Управление пользователями бота")
    parser.add_argument("action", choices=["add", "remove", "list"], help="Действие")
    parser.add_argument("user_id", nargs="?", type=int, help="ID пользователя")
    
    args = parser.parse_args()
    
    if args.action in ["add", "remove"] and args.user_id is None:
        print("❌ Для действий 'add' и 'remove' требуется указать ID пользователя")
        sys.exit(1)
    
    if args.action == "add":
        add_user(args.user_id)
    elif args.action == "remove":
        remove_user(args.user_id)
    elif args.action == "list":
        list_users()

if __name__ == "__main__":
    main()
