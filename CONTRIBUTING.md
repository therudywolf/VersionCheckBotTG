# Contributing / Руководство по вкладу

Contributions are welcome! Below are the guidelines in Russian (primary) and English.

---

## Как внести вклад

### Сообщения об ошибках

1. Проверьте [Issues](https://github.com/therudywolf/VersionCheckBotTG/issues) — возможно, баг уже зарегистрирован.
2. Создайте новый Issue с подробным описанием, шагами для воспроизведения и логами.

### Предложения функций

Создайте Issue с меткой `enhancement`, объясните зачем функция нужна и как должна работать.

### Pull Requests

1. Fork репозитория
2. Создайте ветку: `git checkout -b feature/my-feature`
3. Внесите изменения
4. Убедитесь, что тесты проходят: `pytest`
5. Закоммитьте с понятным сообщением: `git commit -m 'feat: add my feature'`
6. Push: `git push origin feature/my-feature`
7. Откройте Pull Request

## Стандарты кода

- **PEP 8** — основной стиль
- **Type hints** — для всех публичных функций
- **Docstrings** — для классов и функций
- **Максимум 100 символов** в строке

### Префиксы коммитов

| Префикс | Назначение |
|---------|------------|
| `feat:` | Новая функциональность |
| `fix:` | Исправление бага |
| `docs:` | Документация |
| `refactor:` | Рефакторинг без изменения поведения |
| `test:` | Тесты |
| `chore:` | Сборка, CI, зависимости |

### Тестирование

```bash
pytest                         # Все тесты
pytest --cov=bot               # С покрытием
pytest -k test_parser          # Конкретный тест
```

## Структура проекта

```
bot/
├── handlers/      # Telegram-обработчики (commands, callbacks, inline, messages)
├── services/      # Бизнес-логика (version, cve, monitoring, notification)
├── models/        # SQLAlchemy-модели
├── utils/         # Утилиты (cache, parser, fuzzy, rate_limiter, retry, ...)
├── database/      # Engine + Session
└── scheduler/     # Фоновые задачи
```

## Процесс

1. Обсудите крупные изменения в Issue перед началом работы.
2. Один PR = одна логическая задача.
3. Обновите документацию и CHANGELOG при необходимости.
4. Убедитесь, что CI проходит.

---

## English

### Bug Reports

Check existing [Issues](https://github.com/therudywolf/VersionCheckBotTG/issues) first.
Include reproduction steps and logs.

### Pull Requests

1. Fork, branch (`feature/my-feature`), implement, test (`pytest`), commit, push, open PR.
2. Follow PEP 8, add type hints and docstrings.
3. Use [Conventional Commits](https://www.conventionalcommits.org/) prefixes.

Thank you for contributing!
