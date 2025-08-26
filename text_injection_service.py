#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис для вставки текста в активное окно
"""

import time
import threading
import pyperclip
import keyboard
import win32gui
import win32con
import win32api
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from config import TextInjectionConfig
from logging_config import get_logger


@dataclass
class InjectionResult:
    """Результат вставки текста"""
    success: bool
    method: str
    processing_time: float
    error_message: Optional[str] = None


class TextInjectionService:
    """Сервис для вставки текста в активное окно"""
    
    def __init__(self, config: TextInjectionConfig, logger=None):
        self.config = config
        self.logger = logger or get_logger("text_injection")
        
        # Статистика
        self._stats = {
            "total_injections": 0,
            "successful_injections": 0,
            "failed_injections": 0,
            "clipboard_method_count": 0,
            "typing_method_count": 0,
            "total_processing_time": 0.0,
            "last_injection_time": None
        }
        
        # Callback для уведомлений
        self._status_callback: Optional[Callable[[str], None]] = None
        
        # Блокировка для предотвращения одновременных вставок
        self._injection_lock = threading.Lock()
        
        self.logger.info("Text injection service initialized")
    
    def set_status_callback(self, callback: Callable[[str], None]):
        """Установить callback для уведомлений о статусе"""
        self._status_callback = callback
    
    def _notify_status(self, status: str):
        """Уведомить о изменении статуса"""
        if self._status_callback:
            try:
                self._status_callback(status)
            except Exception as e:
                self.logger.error(f"Status callback error: {e}")
    
    def _get_active_window_info(self) -> Dict[str, Any]:
        """Получить информацию об активном окне"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            
            return {
                "hwnd": hwnd,
                "title": title,
                "class_name": class_name,
                "is_editable": self._is_editable_window(class_name, title)
            }
        except Exception as e:
            self.logger.error(f"Failed to get active window info: {e}")
            return {"hwnd": None, "title": "Unknown", "class_name": "Unknown", "is_editable": False}
    
    def _is_editable_window(self, class_name: str, title: str) -> bool:
        """Проверить, является ли окно редактируемым"""
        # Список известных редактируемых окон
        editable_classes = [
            "Edit", "RichEdit", "TextBox", "TextField",
            "Chrome_RenderWidgetHostHWND", "MozillaWindowClass",
            "Notepad", "WordPad", "Microsoft Word",
            "Visual Studio", "PyCharm", "VSCode"
        ]
        
        # Проверяем по классу
        for editable_class in editable_classes:
            if editable_class.lower() in class_name.lower():
                return True
        
        # Проверяем по заголовку
        editable_titles = [
            "notepad", "wordpad", "word", "excel", "powerpoint",
            "chrome", "firefox", "edge", "visual studio", "pycharm", "vscode"
        ]
        
        for editable_title in editable_titles:
            if editable_title.lower() in title.lower():
                return True
        
        return False
    
    def _inject_via_clipboard(self, text: str) -> bool:
        """Вставить текст через буфер обмена"""
        try:
            # Сохраняем текущее содержимое буфера
            old_clipboard = None
            if self.config.restore_clipboard:
                try:
                    old_clipboard = pyperclip.paste()
                except Exception as e:
                    self.logger.warning(f"Failed to save clipboard: {e}")
            
            # Копируем новый текст
            pyperclip.copy(text)
            time.sleep(self.config.paste_delay)
            
            # Вставляем через Ctrl+V
            keyboard.send("ctrl+v")
            time.sleep(self.config.paste_delay)
            
            # Восстанавливаем буфер обмена
            if self.config.restore_clipboard and old_clipboard is not None:
                try:
                    pyperclip.copy(old_clipboard)
                except Exception as e:
                    self.logger.warning(f"Failed to restore clipboard: {e}")
            
            self.logger.debug("Text injected via clipboard successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Clipboard injection failed: {e}")
            return False
    
    def _inject_via_typing(self, text: str) -> bool:
        """Вставить текст посимвольно"""
        try:
            # Фокусируемся на активном окне
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.1)  # Небольшая пауза для фокусировки
            
            # Вводим текст
            keyboard.write(text, delay=self.config.type_delay)
            
            self.logger.debug("Text injected via typing successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Typing injection failed: {e}")
            return False
    
    def inject_text(self, text: str, force_method: Optional[str] = None) -> InjectionResult:
        """Вставить текст в активное окно"""
        start_time = time.time()
        
        # Проверяем блокировку
        if not self._injection_lock.acquire(blocking=False):
            self.logger.warning("Another injection in progress, skipping")
            return InjectionResult(
                success=False,
                method="none",
                processing_time=0.0,
                error_message="Another injection in progress"
            )
        
        try:
            # Валидация текста
            if not text or not text.strip():
                return InjectionResult(
                    success=False,
                    method="none",
                    processing_time=0.0,
                    error_message="Empty text"
                )
            
            # Получаем информацию об активном окне
            window_info = self._get_active_window_info()
            self.logger.info(f"Injecting text into: {window_info['title']} ({window_info['class_name']})")
            
            # Определяем метод вставки
            method = force_method
            if method is None:
                if self.config.restore_clipboard:
                    method = "clipboard"
                else:
                    method = "typing"
            
            success = False
            error_message = None
            
            # Пробуем выбранный метод
            if method == "clipboard":
                success = self._inject_via_clipboard(text)
                if success:
                    self._stats["clipboard_method_count"] += 1
                else:
                    error_message = "Clipboard method failed"
            
            elif method == "typing":
                success = self._inject_via_typing(text)
                if success:
                    self._stats["typing_method_count"] += 1
                else:
                    error_message = "Typing method failed"
            
            # Если основной метод не сработал, пробуем fallback
            if not success and self.config.type_fallback and method != "typing":
                self.logger.info("Primary method failed, trying typing fallback")
                success = self._inject_via_typing(text)
                if success:
                    method = "typing_fallback"
                    self._stats["typing_method_count"] += 1
                    error_message = None
            
            # Вычисляем время обработки
            processing_time = time.time() - start_time
            
            # Обновляем статистику
            self._stats["total_injections"] += 1
            if success:
                self._stats["successful_injections"] += 1
                self._notify_status("injected")
            else:
                self._stats["failed_injections"] += 1
                self._notify_status("injection_failed")
            
            self._stats["total_processing_time"] += processing_time
            self._stats["last_injection_time"] = time.time()
            
            # Создаем результат
            result = InjectionResult(
                success=success,
                method=method,
                processing_time=processing_time,
                error_message=error_message
            )
            
            if success:
                self.logger.info(f"Text injected successfully via {method}: {len(text)} chars, "
                               f"processing: {processing_time:.3f}s")
            else:
                self.logger.error(f"Text injection failed via {method}: {error_message}")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Unexpected error during text injection: {e}")
            
            self._stats["total_injections"] += 1
            self._stats["failed_injections"] += 1
            self._stats["total_processing_time"] += processing_time
            
            return InjectionResult(
                success=False,
                method="error",
                processing_time=processing_time,
                error_message=str(e)
            )
        
        finally:
            # Освобождаем блокировку
            self._injection_lock.release()
    
    def inject_text_async(self, text: str, force_method: Optional[str] = None, 
                          callback: Optional[Callable[[InjectionResult], None]] = None):
        """Асинхронная вставка текста"""
        def _async_injection():
            result = self.inject_text(text, force_method)
            if callback:
                try:
                    callback(result)
                except Exception as e:
                    self.logger.error(f"Async injection callback error: {e}")
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=_async_injection, daemon=True)
        thread.start()
        
        self.logger.debug("Async text injection started")
    
    def copy_to_clipboard(self, text: str) -> bool:
        """Скопировать текст в буфер обмена"""
        try:
            pyperclip.copy(text)
            self.logger.info(f"Text copied to clipboard: {len(text)} chars")
            return True
        except Exception as e:
            self.logger.error(f"Failed to copy to clipboard: {e}")
            return False
    
    def get_active_window_text(self) -> Optional[str]:
        """Получить текст из активного окна (если возможно)"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            
            # Пробуем получить текст через WM_GETTEXT
            length = win32gui.SendMessage(hwnd, win32con.WM_GETTEXTLENGTH, 0, 0)
            if length > 0:
                buffer = win32gui.PyMakeBuffer(length + 1)
                win32gui.SendMessage(hwnd, win32con.WM_GETTEXT, length + 1, buffer)
                return buffer.tobytes().decode('utf-8', errors='ignore').rstrip('\0')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get active window text: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику вставки"""
        stats = self._stats.copy()
        if stats["total_injections"] > 0:
            stats["success_rate"] = stats["successful_injections"] / stats["total_injections"]
            stats["avg_processing_time"] = stats["total_processing_time"] / stats["total_injections"]
        else:
            stats["success_rate"] = 0.0
            stats["avg_processing_time"] = 0.0
        
        return stats
    
    def clear_stats(self):
        """Очистить статистику"""
        self._stats = {
            "total_injections": 0,
            "successful_injections": 0,
            "failed_injections": 0,
            "clipboard_method_count": 0,
            "typing_method_count": 0,
            "total_processing_time": 0.0,
            "last_injection_time": None
        }
    
    def test_injection(self, test_text: str = "Test") -> bool:
        """Протестировать вставку текста"""
        try:
            self.logger.info("Testing text injection")
            result = self.inject_text(test_text, force_method="typing")
            return result.success
        except Exception as e:
            self.logger.error(f"Injection test failed: {e}")
            return False
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            # Ожидаем завершения текущих операций
            if self._injection_lock.locked():
                self.logger.info("Waiting for current injection to complete...")
                # Даем небольшую паузу для завершения
                time.sleep(0.5)
            
            self.logger.info("Text injection service cleaned up")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def __del__(self):
        """Деструктор для автоматической очистки"""
        self.cleanup()
