# Исправление проблемы с уведомлениями

## 🐛 Описание проблемы

При попытке показать настройки через трей-меню возникала ошибка:
```
Failed to show notification: string too long (148, maximum length 64)
```

**Причина**: Метод `pystray.Icon.notify()` имеет ограничение на длину сообщения - максимум 64 символа.

## 🔧 Решение

### 1. Автоматическая обрезка в `tray_interface.py`

Добавлена логика автоматической обрезки длинных сообщений:

```python
def show_notification(self, title: str, message: str, duration: int = 3):
    """Показать уведомление"""
    try:
        if self._icon:
            # Ограничиваем длину сообщения для pystray (максимум 64 символа)
            if len(message) > 64:
                truncated_message = message[:61] + "..."
                self.logger.warning(f"Message truncated from {len(message)} to 64 characters")
            else:
                truncated_message = message
            
            self._icon.notify(title, truncated_message)
            self.logger.info(f"Notification shown: {title} - {truncated_message}")
    except Exception as e:
        self.logger.error(f"Failed to show notification: {e}")
```

### 2. Оптимизация в `ptt_app.py`

Изменен метод `_show_settings()` для отправки кратких уведомлений:

```python
def _show_settings(self):
    """Показать настройки"""
    try:
        self.logger.info("Showing settings...")
        
        # Краткое уведомление для трея (ограничение 64 символа)
        short_settings = f"PTT: {self.config.ptt_key.upper()}, Whisper: {self.config.whisper.model}"
        
        # Полная информация для лога
        full_settings = f"""
Основные настройки:
• Клавиша PTT: {self.config.ptt_key.upper()}
• Модель Whisper: {self.config.whisper.model}
• Модель LLM: {self.config.ollama.model}
• Авто-вставка: {'ВКЛ' if self.config.text_injection.autopaste else 'ВЫКЛ'}
• Частота дискретизации: {self.config.audio.sample_rate}Hz
        """.strip()
        
        # Логируем полную информацию
        self.logger.info(f"Current settings: {full_settings}")
        
        # Показываем краткое уведомление в трее
        if self.tray_interface:
            self.tray_interface.show_notification(
                "Настройки",
                short_settings,
                8
            )
        
    except Exception as e:
        self.logger.error(f"Show settings failed: {e}")
```

## ✅ Результат

- **Краткие уведомления** в трее (до 64 символов)
- **Полная информация** в логах
- **Автоматическая обрезка** с предупреждением
- **Логирование** всех операций

## 🧪 Тестирование

Создан и успешно выполнен тест `test_notifications.py`, который проверяет:
- Короткие сообщения (отправляются как есть)
- Длинные сообщения (автоматически обрезаются)
- Граничные случаи (64 и 65 символов)

## 📝 Логи

При обрезке сообщения в логах появляется предупреждение:
```
WARNING: Message truncated from 101 to 64 characters
```

При успешной отправке:
```
INFO: Notification shown: Настройки - PTT: F9, Whisper: base
```

## 🔮 Дальнейшие улучшения

- Добавить настройку максимальной длины уведомлений
- Реализовать многострочные уведомления
- Создать fallback для длинных сообщений (например, всплывающее окно)
