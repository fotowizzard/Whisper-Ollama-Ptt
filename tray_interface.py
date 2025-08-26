#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Улучшенный трей-интерфейс для PTT приложения
"""

import pystray
import threading
import time
from typing import Optional, Dict, Any, Callable
from PIL import Image, ImageDraw, ImageFont
from config import AppConfig
from logging_config import get_logger


class TrayIcon:
    """Улучшенная иконка в трее с расширенным функционалом"""
    
    def __init__(self, config: AppConfig, logger=None):
        self.config = config
        self.logger = logger or get_logger("tray")
        
        # Состояние
        self._icon: Optional[pystray.Icon] = None
        self._active = True
        self._recording = False
        self._processing = False
        
        # Callbacks
        self._status_callbacks = {}
        self._menu_callbacks = {}
        
        # Статистика
        self._stats = {
            "total_recordings": 0,
            "total_transcriptions": 0,
            "total_injections": 0,
            "uptime": 0.0,
            "last_activity": None
        }
        
        # Время запуска
        self._start_time = time.time()
        
        self.logger.info("Tray interface initialized")
        self._setup_icon()
    
    def _setup_icon(self):
        """Настройка иконки трея"""
        # Создаем иконку
        icon_image = self._create_icon(active=True)
        
        # Создаем меню
        menu = self._create_menu()
        
        # Создаем иконку трея
        self._icon = pystray.Icon(
            "PTT",
            icon_image,
            "PTT Whisper+Ollama",
            menu
        )
        
        # Запускаем в отдельном потоке
        threading.Thread(target=self._icon.run, daemon=True).start()
        
        self.logger.info("Tray icon started")
    
    def _create_icon(self, active: bool = True, recording: bool = False, 
                     processing: bool = False) -> Image.Image:
        """Создать иконку с учетом состояния"""
        size = (64, 64)
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        
        # Определяем цвет в зависимости от состояния
        if processing:
            color = (255, 165, 0, 255)  # Оранжевый - обработка
        elif recording:
            color = (255, 0, 0, 255)    # Красный - запись
        elif active:
            color = (60, 200, 60, 255)  # Зеленый - активно
        else:
            color = (160, 160, 160, 255)  # Серый - неактивно
        
        # Рисуем основной круг
        d.ellipse([8, 8, 56, 56], fill=color)
        
        # Добавляем индикаторы состояния
        if recording:
            # Пульсирующий эффект для записи
            pulse_alpha = int(128 + 127 * (time.time() % 1.0))
            d.ellipse([16, 16, 48, 48], fill=(255, 255, 255, pulse_alpha))
        elif processing:
            # Индикатор обработки
            d.ellipse([16, 16, 48, 48], fill=(255, 255, 255, 100))
            # Рисуем стрелку
            d.polygon([(32, 20), (28, 28), (36, 28)], fill=(0, 0, 0, 200))
        
        return img
    
    def _create_menu(self) -> pystray.Menu:
        """Создать меню трея"""
        menu_items = []
        
        # Статус
        status_item = pystray.MenuItem(
            lambda item: f"Статус: {'Активно' if self._active else 'Неактивно'}",
            None,
            enabled=False
        )
        menu_items.append(status_item)
        
        # Разделитель
        menu_items.append(pystray.Menu.SEPARATOR)
        
        # Основные функции
        menu_items.extend([
            pystray.MenuItem(
                lambda item: f"Авто-вставка: {'ВКЛ' if self.config.text_injection.autopaste else 'ВЫКЛ'}",
                self._toggle_autopaste
            ),
            pystray.MenuItem(
                "Тест вставки",
                self._test_injection
            ),
            pystray.MenuItem(
                "Тест аудио",
                self._test_audio
            )
        ])
        
        # Разделитель
        menu_items.append(pystray.Menu.SEPARATOR)
        
        # Статистика
        menu_items.extend([
            pystray.MenuItem(
                lambda item: f"Записей: {self._stats['total_recordings']}",
                None,
                enabled=False
            ),
            pystray.MenuItem(
                lambda item: f"Транскрипций: {self._stats['total_transcriptions']}",
                None,
                enabled=False
            ),
            pystray.MenuItem(
                lambda item: f"Вставок: {self._stats['total_injections']}",
                None,
                enabled=False
            ),
            pystray.MenuItem(
                lambda item: f"Время работы: {self._get_uptime_str()}",
                None,
                enabled=False
            )
        ])
        
        # Разделитель
        menu_items.append(pystray.Menu.SEPARATOR)
        
        # Настройки
        menu_items.extend([
            pystray.MenuItem(
                "Настройки",
                self._show_settings
            ),
            pystray.MenuItem(
                "О программе",
                self._show_about
            )
        ])
        
        # Разделитель
        menu_items.append(pystray.Menu.SEPARATOR)
        
        # Выход
        menu_items.append(
            pystray.MenuItem("Выход", self._on_exit)
        )
        
        return pystray.Menu(*menu_items)
    
    def _get_uptime_str(self) -> str:
        """Получить строку времени работы"""
        uptime = time.time() - self._start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        
        if hours > 0:
            return f"{hours}ч {minutes}м"
        else:
            return f"{minutes}м"
    
    def _toggle_autopaste(self, icon, item):
        """Переключить авто-вставку"""
        try:
            self.config.text_injection.autopaste = not self.config.text_injection.autopaste
            status = "ВКЛ" if self.config.text_injection.autopaste else "ВЫКЛ"
            
            self.logger.info(f"Autopaste toggled to {status}")
            self._update_title()
            
            # Уведомляем callback
            if "autopaste_toggle" in self._status_callbacks:
                self._status_callbacks["autopaste_toggle"](self.config.text_injection.autopaste)
                
        except Exception as e:
            self.logger.error(f"Failed to toggle autopaste: {e}")
    
    def _test_injection(self, icon, item):
        """Тест вставки текста"""
        try:
            self.logger.info("Testing text injection from tray menu")
            
            # Уведомляем callback
            if "test_injection" in self._menu_callbacks:
                self._menu_callbacks["test_injection"]()
                
        except Exception as e:
            self.logger.error(f"Test injection failed: {e}")
    
    def _test_audio(self, icon, item):
        """Тест аудио"""
        try:
            self.logger.info("Testing audio from tray menu")
            
            # Уведомляем callback
            if "test_audio" in self._menu_callbacks:
                self._menu_callbacks["test_audio"]()
                
        except Exception as e:
            self.logger.error(f"Test audio failed: {e}")
    
    def _show_settings(self, icon, item):
        """Показать настройки"""
        try:
            self.logger.info("Settings requested from tray menu")
            
            # Уведомляем callback
            if "show_settings" in self._menu_callbacks:
                self._menu_callbacks["show_settings"]()
                
        except Exception as e:
            self.logger.error(f"Show settings failed: {e}")
    
    def _show_about(self, icon, item):
        """Показать информацию о программе"""
        try:
            about_text = f"""
PTT Whisper+Ollama v1.0

Push-to-Talk приложение для диктовки
с использованием Whisper и Ollama.

Время работы: {self._get_uptime_str()}
Записей: {self._stats['total_recordings']}
Транскрипций: {self._stats['total_transcriptions']}
Вставок: {self._stats['total_injections']}

Автор: AI Assistant
            """.strip()
            
            # Уведомляем callback
            if "show_about" in self._menu_callbacks:
                self._menu_callbacks["show_about"](about_text)
                
        except Exception as e:
            self.logger.error(f"Show about failed: {e}")
    
    def _on_exit(self, icon, item):
        """Обработка выхода"""
        try:
            self.logger.info("Exit requested from tray menu")
            
            # Уведомляем callback
            if "exit" in self._menu_callbacks:
                self._menu_callbacks["exit"]()
            else:
                # Fallback - принудительный выход
                import os
                os._exit(0)
                
        except Exception as e:
            self.logger.error(f"Exit failed: {e}")
            import os
            os._exit(1)
    
    def _update_title(self):
        """Обновить заголовок иконки"""
        if not self._icon:
            return
        
        try:
            # Формируем заголовок
            title_parts = ["PTT Whisper+Ollama"]
            
            if self._recording:
                title_parts.append("🔴 Запись...")
            elif self._processing:
                title_parts.append("🟠 Обработка...")
            else:
                title_parts.append("🟢 Готов")
            
            if not self.config.text_injection.autopaste:
                title_parts.append("(Авто-вставка ВЫКЛ)")
            
            title = " | ".join(title_parts)
            self._icon.title = title
            
        except Exception as e:
            self.logger.error(f"Failed to update title: {e}")
    
    def _update_icon(self):
        """Обновить иконку"""
        if not self._icon:
            return
        
        try:
            # Создаем новую иконку
            new_icon = self._create_icon(
                active=self._active,
                recording=self._recording,
                processing=self._processing
            )
            
            # Обновляем иконку
            self._icon.icon = new_icon
            
        except Exception as e:
            self.logger.error(f"Failed to update icon: {e}")
    
    def set_status(self, status: str):
        """Установить статус"""
        try:
            old_recording = self._recording
            old_processing = self._processing
            
            # Обновляем состояние
            if status == "recording":
                self._recording = True
                self._processing = False
            elif status == "processing":
                self._recording = False
                self._processing = True
            elif status in ["ready", "injected", "no_audio"]:
                self._recording = False
                self._processing = False
            elif status == "error":
                self._recording = False
                self._processing = False
            
            # Обновляем интерфейс если состояние изменилось
            if old_recording != self._recording or old_processing != self._processing:
                self._update_icon()
                self._update_title()
            
            self.logger.debug(f"Status updated: {status}")
            
        except Exception as e:
            self.logger.error(f"Failed to set status: {e}")
    
    def update_stats(self, stats: Dict[str, Any]):
        """Обновить статистику"""
        try:
            # Обновляем статистику
            for key, value in stats.items():
                if key in self._stats:
                    self._stats[key] = value
            
            # Обновляем время последней активности
            self._stats["last_activity"] = time.time()
            
            # Обновляем время работы
            self._stats["uptime"] = time.time() - self._start_time
            
            self.logger.debug("Stats updated")
            
        except Exception as e:
            self.logger.error(f"Failed to update stats: {e}")
    
    def register_status_callback(self, event: str, callback: Callable):
        """Зарегистрировать callback для статуса"""
        self._status_callbacks[event] = callback
        self.logger.debug(f"Status callback registered for: {event}")
    
    def register_menu_callback(self, action: str, callback: Callable):
        """Зарегистрировать callback для действий меню"""
        self._menu_callbacks[action] = callback
        self.logger.debug(f"Menu callback registered for: {action}")
    
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
    
    def set_active(self, active: bool):
        """Установить активность"""
        try:
            self._active = active
            self._update_icon()
            self._update_title()
            self.logger.info(f"Active state set to: {active}")
        except Exception as e:
            self.logger.error(f"Failed to set active state: {e}")
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if self._icon:
                self._icon.stop()
                self._icon = None
            self.logger.info("Tray interface cleaned up")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def __del__(self):
        """Деструктор для автоматической очистки"""
        self.cleanup()
