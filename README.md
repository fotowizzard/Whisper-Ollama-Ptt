# Whisper + Ollama Push‑to‑Talk (Windows)

Локальный офлайн MVP для диктовки: удерживаете клавишу — идёт запись, отпускаете — распознавание и автоматическая вставка текста в активное окно.

## Возможности
- Глобальная клавиша push‑to‑talk (по умолчанию F9)
- ASR: faster‑whisper (Whisper), язык: ru
- Пост‑обработка текста локальной LLM через Ollama (по умолчанию `qwen2.5:7b-instruct`)
- Вставка в активное окно: сначала через буфер обмена (Ctrl+V), при неудаче — по символам
- Трей‑иконка с переключателем авто‑вставки и выходом

## Установка (Windows, Python 3.10+)
1. Установите зависимости:
   ```bash
   pip install -U faster-whisper sounddevice keyboard pyperclip requests pystray pillow
   ```
2. Запустите Ollama и подготовьте модель:
   ```bash
   ollama serve
   ollama pull qwen2.5:7b-instruct
   ```
3. Запуск приложения:
   ```bash
   python whisper_ollama_ptt_windows.py
   ```
4. Автозапуск: создайте ярлык скрипта в `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`.

## Сборка в .exe (опционально)
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile whisper_ollama_ptt_windows.py
```

## Переменные окружения
- `PTT_KEY` — клавиша PTT (по умолчанию `f9`)
- `SAMPLE_RATE` — частота дискретизации, по умолчанию `16000`
- `CHANNELS` — число каналов, по умолчанию `1`
- `AUDIO_DEVICE` — имя/индекс входного аудиоустройства (по умолчанию — системное)
- `WHISPER_MODEL` — модель Whisper (`small`, `medium`, `large-v3`, ...)
- `WHISPER_DEVICE` — `auto`/`cpu`/`cuda`
- `WHISPER_COMPUTE` — `int8` для CPU, `float16` для CUDA
- `OLLAMA_URL` — URL API генерации (`http://127.0.0.1:11434/api/generate`)
- `OLLAMA_MODEL` — модель Ollama (`qwen2.5:7b-instruct`)
- `OLLAMA_TIMEOUT` — таймаут HTTP в секундах (по умолчанию `10`)
- `AUTOPASTE` — `1` включить/`0` отключить автопостинг
- `TYPE_FALLBACK` — `1` включить набор по символам при неудачном Ctrl+V
- `LOG_PATH` — путь к логу (по умолчанию `ptt.log` рядом со скриптом)

## Ограничения MVP
- Нет VAD и оверлея с аудиограммой
- Запись только пока зажата клавиша PTT

## Примечания
- Для работы `sounddevice` могут потребоваться драйверы WASAPI/WDM‑KS и права.
- Убедитесь, что антивирус/политики не блокируют глобальные хуки клавиатуры.