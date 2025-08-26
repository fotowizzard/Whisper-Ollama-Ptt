# Руководство по миграции

## Переход с старой версии на новую архитектуру

Этот документ поможет вам перейти с оригинального `whisper_ollama_ptt_windows.py` на новую модульную архитектуру.

## 🆕 Что изменилось

### Структура проекта
```
Старая версия:
├── whisper_ollama_ptt_windows.py (монолитный файл)

Новая версия:
├── ptt_app.py (основное приложение)
├── config.py (конфигурация)
├── logging_config.py (логирование)
├── audio_manager.py (управление аудио)
├── transcription_service.py (Whisper)
├── llm_service.py (Ollama)
├── text_injection_service.py (вставка текста)
├── tray_interface.py (трей интерфейс)
└── test_modules.py (тестирование)
```

### Основные изменения

1. **Разделение ответственности** - каждый модуль отвечает за свою область
2. **Конфигурация** - поддержка YAML/JSON файлов и переменных окружения
3. **Логирование** - структурированные логи с уровнями и ротацией
4. **Обработка ошибок** - специфические обработчики и retry логика
5. **Трей интерфейс** - расширенное меню с статистикой и тестами

## 📋 Пошаговая миграция

### Шаг 1: Установка новых зависимостей

```bash
# Удалите старые зависимости (опционально)
pip uninstall faster-whisper sounddevice keyboard pyperclip requests pystray pillow numpy

# Установите новые зависимости
pip install -r requirements.txt
```

### Шаг 2: Настройка конфигурации

1. **Скопируйте пример конфигурации:**
   ```bash
   cp config_example.yaml config.yaml
   ```

2. **Отредактируйте `config.yaml` под свои нужды:**
   ```yaml
   ptt_key: "f9"  # Ваша клавиша PTT
   whisper:
     model: "small"  # Ваша модель Whisper
   ollama:
     model: "qwen2.5:7b-instruct"  # Ваша модель Ollama
   ```

3. **Или используйте переменные окружения:**
   ```bash
   set PTT_KEY=f9
   set WHISPER_MODEL=small
   set OLLAMA_MODEL=qwen2.5:7b-instruct
   ```

### Шаг 3: Запуск нового приложения

```bash
# Вместо старого файла
# python whisper_ollama_ptt_windows.py

# Используйте новый
python ptt_app.py
```

### Шаг 4: Тестирование

```bash
# Запустите тесты для проверки работы модулей
python test_modules.py
```

## 🔄 Сопоставление функций

| Старая версия | Новая версия | Примечания |
|---------------|--------------|------------|
| `CFG.PTT_KEY` | `config.ptt_key` | Конфигурация через класс |
| `log()` | `logger.info()` | Структурированное логирование |
| `_audio_buf` | `AudioManager` | Управляемый буфер с ограничениями |
| `_whisper` | `WhisperService` | Сервис с retry логикой |
| `_postprocess_with_ollama()` | `LLMService` | Отдельный сервис для LLM |
| `_inject_text()` | `TextInjectionService` | Улучшенная вставка с fallback |
| `_setup_tray()` | `TrayIcon` | Расширенный трей интерфейс |

## ⚠️ Важные изменения

### 1. Импорты
```python
# Старая версия
from faster_whisper import WhisperModel
import sounddevice as sd

# Новая версия
from transcription_service import WhisperService
from audio_manager import AudioManager
```

### 2. Конфигурация
```python
# Старая версия
CFG = Config()

# Новая версия
from config import CONFIG
# или
config = AppConfig.from_file("config.yaml")
```

### 3. Логирование
```python
# Старая версия
log("message")

# Новая версия
logger = get_logger("module_name")
logger.info("message")
```

### 4. Обработка ошибок
```python
# Старая версия
except Exception as e:
    log(f"Error: {e}")

# Новая версия
except SpecificError as e:
    logger.error(f"Specific error: {e}")
except Exception as e:
    logger.exception("Unexpected error")
```

## 🧪 Тестирование миграции

### 1. Проверка модулей
```bash
python test_modules.py
```

### 2. Проверка конфигурации
```python
from config import CONFIG
print(CONFIG.validate())  # Должно вернуть True
```

### 3. Проверка логирования
```python
from logging_config import setup_logging, get_logger
logger = setup_logging(CONFIG.logging)
logger.info("Test message")
```

### 4. Проверка сервисов
```python
from audio_manager import AudioManager
from transcription_service import WhisperService

audio_manager = AudioManager(CONFIG.audio)
whisper_service = WhisperService(CONFIG.whisper)

# Проверяем доступные устройства
devices = audio_manager.get_available_devices()
print(f"Audio devices: {len(devices)}")

# Проверяем статус Whisper
model_info = whisper_service.get_model_info()
print(f"Whisper status: {model_info['status']}")
```

## 🚨 Потенциальные проблемы

### 1. Отсутствующие зависимости
```bash
# Установите недостающие пакеты
pip install pyyaml pywin32
```

### 2. Проблемы с правами доступа
- Запустите PowerShell от имени администратора
- Проверьте настройки антивируса

### 3. Проблемы с аудио
- Убедитесь, что драйверы WASAPI/WDM-KS установлены
- Проверьте доступные аудио устройства

### 4. Проблемы с Ollama
- Убедитесь, что Ollama запущен: `ollama serve`
- Проверьте доступность модели: `ollama list`

## 🔧 Отладка

### 1. Логи
- Проверьте файл `ptt.log`
- Установите уровень логирования в `DEBUG`

### 2. Тесты
```bash
# Запустите тесты с подробным выводом
python test_modules.py 2>&1 | tee test_output.log
```

### 3. Проверка конфигурации
```python
from config import CONFIG
print(CONFIG.to_dict())  # Выведет всю конфигурацию
```

## 📚 Дополнительные возможности

После миграции вы получите доступ к:

1. **Расширенному трей-меню** с статистикой
2. **Тестированию компонентов** прямо из интерфейса
3. **Детальному логированию** с уровнями
4. **Гибкой конфигурации** через файлы
5. **Мониторингу производительности**
6. **Retry логике** для надежности

## 🆘 Получение помощи

Если у вас возникли проблемы с миграцией:

1. Проверьте логи в `ptt.log`
2. Запустите `python test_modules.py`
3. Убедитесь, что все зависимости установлены
4. Проверьте права доступа
5. Создайте issue в репозитории

## 🎯 Следующие шаги

После успешной миграции:

1. Настройте конфигурацию под свои нужды
2. Изучите новые возможности трей-меню
3. Настройте логирование для отладки
4. Рассмотрите возможность создания собственных конфигураций
5. Внесите свой вклад в развитие проекта
