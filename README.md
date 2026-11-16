# To-Do Manager

Настольный менеджер задач на Python и PyQt6. Задачи можно просматривать в таблице, в карточках и на канбан-доске. В приложении есть проекты, поиск, подзадачи, вложения и рисунки, повторения, таймер, история изменений и обмен через CSV.

## Запуск на Windows

Откройте PowerShell в корне проекта и выполните:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\Source\main.py
```

При первом запуске создайте локальный аккаунт. Приложение хранит задачи в `todo.db` в рабочей папке.

## Проверка интерфейса

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Тест использует базу SQLite в памяти и отдельный файл настроек.
