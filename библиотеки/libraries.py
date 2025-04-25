import subprocess
import sys
import time

required_libraries = ["requests"]

print("=== Установка необходимых библиотек ===")
print("Эта программа попытается установить следующие библиотеки, которых может не быть в стандартной сборке Python:")
for lib in required_libraries:
    print(f"- {lib}")
print("-" * 50)

all_installed_successfully = True

for library in required_libraries:
    print(f"\nПопытка установки библиотеки: {library}...")
    try:
        # Используем sys.executable и -m pip для более надежного вызова pip, связанного с текущим интерпретатором Python
        process = subprocess.run([sys.executable, "-m", "pip", "install", library], check=True, capture_output=True, text=True, encoding='utf-8')
        print(f"Успешно установлена библиотека: {library}")
        # Если нужна подробная информация от pip, можно раскомментировать следующую строку:
        # print("Вывод pip:\n", process.stdout)

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке библиотеки {library}. Код ошибки: {e.returncode}")
        print("Стандартный вывод ошибки:")
        print(e.stderr)
        print("Возможно, у вас нет прав для установки или есть проблемы с подключением.")
        all_installed_successfully = False
    except FileNotFoundError:
         print(f"Ошибка: Команда 'pip' или интерпретатор Python '{sys.executable}' не найдены.")
         print("Убедитесь, что Python и pip установлены и доступны в переменной PATH.")
         all_installed_successfully = False
         break # Нет смысла продолжать, если pip не найден
    except Exception as e:
        print(f"Произошла непредвиденная ошибка при установке {library}: {e}")
        all_installed_successfully = False

print("\n" + "=" * 50)
if all_installed_successfully:
    print("Процесс установки завершен.")
    print("Все необходимые библиотеки успешно установлены.")
else:
    print("Процесс установки завершен, но произошли ошибки при установке некоторых библиотек.")
    print("Пожалуйста, проверьте сообщения выше на наличие деталей ошибок.")
print("=" * 50)

# Пауза перед закрытием консоли
input("\nНажмите Enter для выхода...")